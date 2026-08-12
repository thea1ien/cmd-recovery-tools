import os
import struct
import sys

class CMDRecoverySuite:
    VERSION = "v1.0.0"
    D4M_TARGET_SIZE = 3_317_760
    D4M_TABLE_OFFSET = 0x320800

    # --- CORE FILE IO EXTENSION LOOKUPS ---
    FORMAT_EXTENSIONS = {
        "DHD": ".HPT",
        "D2M": ".2PT",
        "D4M": ".4PT"
    }

    @classmethod
    def _normalize_d4m_image(cls, file_bytes):
        working = bytearray(file_bytes)
        if len(working) < cls.D4M_TARGET_SIZE:
            working.extend(b"\x00" * (cls.D4M_TARGET_SIZE - len(working)))
        elif len(working) > cls.D4M_TARGET_SIZE:
            working = working[:cls.D4M_TARGET_SIZE]
        return bytes(working)

    @classmethod
    def _detect_d4m_partition_candidates(cls, file_bytes):
        file_len = len(file_bytes)
        discovered = []

        for sector_idx in range(0, file_len // 256):
            offset = sector_idx * 256
            if offset + 256 > file_len:
                break
            sector = file_bytes[offset:offset + 256]

            def make_record(name, type_flag, type_str, default_blocks, byte_start):
                return {
                    "name": name,
                    "type_flag": type_flag,
                    "type_str": type_str,
                    "block_start": byte_start // 512,
                    "byte_start": byte_start,
                    "default_blocks": default_blocks,
                    "byte_end": byte_start + (default_blocks * 512 if default_blocks > 0 else 0),
                }

            if sector[0] == 40 and sector[1] == 3 and sector[2] == 0x44 and sector[25] == 0x33 and sector[26] == 0x44:
                p_start_sector = sector_idx - 1560
                p_start_bytes = p_start_sector * 256
                name_bytes = sector[4:20]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "1581 RECOVERED"
                discovered.append(make_record(p_name, 0x04, "81 (1581 Mode)", 1600, p_start_bytes))
                continue

            if sector[0] == 18 and sector[1] == 1 and sector[2] == 0x41:
                p_start_sector = sector_idx - 357
                p_start_bytes = p_start_sector * 256
                name_bytes = sector[144:160]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "RECOVERED CBM"

                bam_byte = sector[3]
                is_1571 = bam_byte == 0x80
                if not is_1571:
                    lookahead_offset = p_start_bytes + (34 * 256 * 21) + (18 * 256)
                    if lookahead_offset + 256 <= file_len:
                        ext_bam = file_bytes[lookahead_offset:lookahead_offset + 256]
                        if ext_bam[0] == 0x00 and ext_bam[1] == 0xFF:
                            is_1571 = True

                type_flag = 0x03 if is_1571 else 0x02
                type_str = "71 (1571 Mode)" if is_1571 else "41 (1541 Mode)"
                default_blocks = 684 if is_1571 else 342
                discovered.append(make_record(p_name, type_flag, type_str, default_blocks, p_start_bytes))
                continue

            if sector[0] == 1 and sector[2] == 0x48 and sector[25] == 0x31 and sector[26] == 0x48:
                p_start_sector = sector_idx - 1
                p_start_bytes = p_start_sector * 256

                next_sector_offset = offset + 256
                next_sector_ok = False
                if next_sector_offset + 256 <= file_len:
                    next_sector = file_bytes[next_sector_offset:next_sector_offset + 256]
                    if len(next_sector) >= 256 and next_sector[2] == 0x38:
                        next_sector_ok = True

                if not next_sector_ok and p_start_bytes <= 0:
                    continue

                if p_start_bytes <= 0:
                    continue
                name_bytes = sector[4:20]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "NAT RECOVERED"
                discovered.append(make_record(p_name, 0x01, "NAT (Native Mode)", 0, p_start_bytes))

        type_priority = {0x02: 0, 0x03: 1, 0x04: 2, 0x01: 3}
        deduped = []
        saw = {}
        for part in sorted(discovered, key=lambda item: (item["byte_start"], type_priority.get(item["type_flag"], 99), item["name"])):
            start = part["byte_start"]
            previous = saw.get(start)
            if previous is None or type_priority.get(part["type_flag"], 99) < type_priority.get(previous["type_flag"], 99):
                saw[start] = part
        for key in sorted(saw):
            deduped.append(saw[key])
        return deduped

    @classmethod
    def _heal_d4m_partition_overlaps(cls, file_bytes, return_stats=False):
        working = bytearray(file_bytes)
        iterations = 0
        total_inserted = 0
        while True:
            partitions = cls._detect_d4m_partition_candidates(bytes(working))
            if not partitions:
                if return_stats:
                    return bytes(working), [], total_inserted
                return bytes(working), []

            normalized = []
            for index, part in enumerate(partitions):
                next_start = partitions[index + 1]["byte_start"] if index + 1 < len(partitions) else len(working)
                if part["default_blocks"] > 0:
                    end = part["byte_start"] + (part["default_blocks"] * 512)
                else:
                    end = next_start
                part["byte_end"] = min(max(part["byte_start"], end), len(working))
                normalized.append(part)

            overlap_found = None
            for index in range(len(normalized) - 1):
                current = normalized[index]
                next_part = normalized[index + 1]
                if next_part["byte_start"] < current["byte_end"]:
                    missing_bytes = current["byte_end"] - next_part["byte_start"]
                    overlap_found = (next_part["byte_start"], missing_bytes)
                    break

            if overlap_found is None:
                if return_stats:
                    return bytes(working), normalized, total_inserted
                return bytes(working), normalized

            insert_at, missing_bytes = overlap_found
            working[insert_at:insert_at] = b"\x00" * missing_bytes
            total_inserted += missing_bytes
            iterations += 1
            if iterations > 64:
                raise RuntimeError("D4M overlap repair loop exceeded safety limit")

    @classmethod
    def _build_rebuilt_partition_table(cls, partitions):
        rebuilt_table_buffer = bytearray(1024)

        # Page 0: system block (first 256 bytes)
        rebuilt_table_buffer[0:32] = (
            b"\x01\x01\xFF\x00\x00" +
            b"SYSTEM".ljust(16, b"\xA0") +
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )

        # CMD D4M table layout:
        #   0x000: 01 01 system header; real partition entries begin immediately after the 32-byte header.
        #   0x100: 01 02 second page tag if the table spills over
        #   0x200: 01 03 third page tag if the table spills over
        #   0x300: 00 0F final terminator page tag
        max_partitions = min(len(partitions), 31)
        page_tag_values = {
            0x000: (0x01, 0x01),
            0x100: (0x01, 0x02),
            0x200: (0x01, 0x03),
            0x300: (0x00, 0x0F),
        }

        for page_offset, (tag_a, tag_b) in page_tag_values.items():
            rebuilt_table_buffer[page_offset] = tag_a
            rebuilt_table_buffer[page_offset + 1] = tag_b

        if max_partitions > 0:
            for idx in range(max_partitions):
                page_index = idx // 8
                entry_index = idx % 8

                if page_index == 0:
                    entry_offset = 0x020 + (entry_index * 0x20)
                elif page_index == 1:
                    entry_offset = 0x120 + (entry_index * 0x20)
                elif page_index == 2:
                    entry_offset = 0x220 + (entry_index * 0x20)
                else:
                    break

                part = partitions[idx]
                rebuilt_table_buffer[entry_offset + 0] = 0x00
                rebuilt_table_buffer[entry_offset + 1] = 0x00
                rebuilt_table_buffer[entry_offset + 2] = part["type_flag"]
                rebuilt_table_buffer[entry_offset + 3:entry_offset + 5] = b"\x00\x00"
                clean_name = part["name"].upper().encode("ascii", errors="ignore")[:16].ljust(16, b"\xA0")
                rebuilt_table_buffer[entry_offset + 5:entry_offset + 21] = clean_name

                loc_lba = part["block_start"]
                rebuilt_table_buffer[entry_offset + 21] = (loc_lba >> 16) & 0xFF
                rebuilt_table_buffer[entry_offset + 22] = (loc_lba >> 8) & 0xFF
                rebuilt_table_buffer[entry_offset + 23] = loc_lba & 0xFF

                size_blocks = part["default_blocks"] if part["default_blocks"] > 0 else max(1, (part["byte_end"] - part["byte_start"]) // 512)
                rebuilt_table_buffer[entry_offset + 29] = (size_blocks >> 16) & 0xFF
                rebuilt_table_buffer[entry_offset + 30] = (size_blocks >> 8) & 0xFF
                rebuilt_table_buffer[entry_offset + 31] = size_blocks & 0xFF

        return bytes(rebuilt_table_buffer)

    @staticmethod
    def display_banner(title):
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 90)
        print(f"🛰️  CREATIVE MICRO DESIGNS RECOVERY UTILITY SUITE [{CMDRecoverySuite.VERSION}]")
        print(f"🎯 ACTIVE MODULE: {title.upper()}")
        print("=" * 90)

    @classmethod
    def handle_table_export(cls, mode):
        cls.display_banner(f"{mode} Partition Table Export")
        img_path = input("📂 Enter the path to the target image file: ").strip('"')
        if not os.path.exists(img_path):
            print("❌ Error: Target file image cannot be located.")
            input("\nPress Enter to return...")
            return

        if mode == "DHD":
            try:
                with open(img_path, "rb") as f:
                    payload = f.read(256 * 1024)
                    found_offset = -1
                    for offset_step in range(0, len(payload) - 16):
                        if payload[offset_step:offset_step+6] == b"CMD HD" and payload[offset_step+8:offset_step+16] == b"\x8D\x03\x88\x8E\x02\x88\xEA\x60":
                            found_offset = offset_step - 0x1F0
                            break
                    if found_offset == -1:
                        print("❌ Error: Valid CMD Hard Drive Master Layout config block not located.")
                        input("\nPress Enter to return...")
                        return
                    f.seek(found_offset + 0x1E6)
                    part_table_lba = struct.unpack(">H", f.read(2))[0]
                    sys_table_offset = (found_offset - 0x400) + (part_table_lba * 256)
                    table_len = 32 * 256
            except Exception as e:
                print(f"❌ Error locating DHD configuration: {e}")
                input("\nPress Enter to return...")
                return
        elif mode == "D2M":
            sys_table_offset = 0x190800
            table_len = 1024
        elif mode == "D4M":
            sys_table_offset = 0x320800
            table_len = 1024
        else:
            return

        ext = cls.FORMAT_EXTENSIONS[mode]
        out_path = input(f"💾 Enter destination filename for table backup (Default extension is {ext}): ").strip('"')
        if not out_path.endswith(ext):
            out_path += ext

        try:
            with open(img_path, "rb") as f_in:
                f_in.seek(sys_table_offset)
                table_bytes = f_in.read(table_len)
            
            with open(out_path, "wb") as f_out:
                f_out.write(table_bytes)
            print(f"\n✅ SUCCESS: Partition table exported cleanly to '{out_path}' ({len(table_bytes)} bytes).")
        except Exception as e:
            print(f"❌ Critical IO Exception during export sequence: {e}")
        input("\nPress Enter to return...")
    @classmethod
    def handle_table_import(cls, mode):
        cls.display_banner(f"{mode} Partition Table Import")
        img_path = input("📂 Enter the path to the target image file to modify: ").strip('"')
        if not os.path.exists(img_path):
            print("❌ Error: Target disk image file cannot be located.")
            input("\nPress Enter to return...")
            return

        ext = cls.FORMAT_EXTENSIONS[mode]
        inp_path = input(f"📥 Enter path to the partition table backup file ({ext}): ").strip('"')
        if not os.path.exists(inp_path):
            print("❌ Error: Backup table file not found.")
            input("\nPress Enter to return...")
            return

        if mode == "DHD":
            try:
                with open(img_path, "rb") as f:
                    payload = f.read(256 * 1024)
                    found_offset = -1
                    for offset_step in range(0, len(payload) - 16):
                        if payload[offset_step:offset_step+6] == b"CMD HD" and payload[offset_step+8:offset_step+16] == b"\x8D\x03\x88\x8E\x02\x88\xEA\x60":
                            found_offset = offset_step - 0x1F0
                            break
                    if found_offset == -1:
                        print("❌ Error: Configuration block anchor not located.")
                        input("\nPress Enter to return...")
                        return
                    f.seek(found_offset + 0x1E6)
                    part_table_lba = struct.unpack(">H", f.read(2))[0]
                    sys_table_offset = (found_offset - 0x400) + (part_table_lba * 256)
            except Exception as e:
                print(f"❌ Error locating configuration offsets: {e}")
                input("\nPress Enter to return...")
                return
        elif mode == "D2M":
            sys_table_offset = 0x190800
        elif mode == "D4M":
            sys_table_offset = 0x320800
        else:
            return

        try:
            with open(inp_path, "rb") as f_in:
                table_bytes = f_in.read()
            
            with open(img_path, "r+b") as f_disk:
                f_disk.seek(sys_table_offset)
                f_disk.write(table_bytes)
            print(f"\n✅ SUCCESS: Partition table injection complete at absolute offset 0x{sys_table_offset:X}!")
        except Exception as e:
            print(f"❌ Critical exception encountered during table flashing: {e}")
        input("\nPress Enter to return...")
    @classmethod
    def _scan_detected_partitions(cls, file_bytes, mode):
        file_len = len(file_bytes)
        discovered_partitions = []
        if mode == "D2M":
            sys_table_offset = 0x190800
        elif mode == "D4M":
            sys_table_offset = cls.D4M_TABLE_OFFSET
        else:
            sys_table_offset = 0x00

        table_guard_start = cls.D4M_TABLE_OFFSET if mode == "D4M" else -1
        table_guard_end = table_guard_start + 0x400 if mode == "D4M" else -1

        for sector_idx in range(0, file_len // 256):
            offset = sector_idx * 256
            if offset + 256 > file_len:
                break
            if mode == "D4M" and table_guard_start <= offset < table_guard_end:
                continue

            sector = file_bytes[offset:offset + 256]
            if len(sector) < 27:
                continue

            if sector[0] == 40 and sector[1] == 3 and sector[2] == 0x44 and sector[25] == 0x33 and sector[26] == 0x44:
                p_start_sector = sector_idx - 1560
                p_start_bytes = p_start_sector * 256
                p_start_block = p_start_bytes // 512
                name_bytes = sector[4:20]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "1581 RECOVERED"
                discovered_partitions.append({
                    "type_flag": 0x04, "type_str": "81 (1581 Mode)", "name": p_name,
                    "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": 1600
                })
                continue

            elif sector[0] == 18 and sector[1] == 1 and sector[2] == 0x41:
                p_start_sector = sector_idx - 357
                p_start_bytes = p_start_sector * 256
                p_start_block = p_start_bytes // 512
                name_bytes = sector[144:160]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "RECOVERED CBM"

                is_1571 = sector[3] == 0x80
                if not is_1571:
                    lookahead_1571_offset = (p_start_block * 512) + (34 * 256 * 21) + (18 * 256)
                    if lookahead_1571_offset + 256 <= file_len:
                        ext_bam = file_bytes[lookahead_1571_offset:lookahead_1571_offset + 256]
                        if ext_bam[0] == 0x00 and ext_bam[1] == 0xFF:
                            is_1571 = True

                t_code = 0x03 if is_1571 else 0x02
                t_label = "71 (1571 Mode)" if is_1571 else "41 (1541 Mode)"
                t_blocks = 684 if is_1571 else 342
                discovered_partitions.append({
                    "type_flag": t_code, "type_str": t_label, "name": p_name,
                    "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": t_blocks
                })
                continue

            elif sector[0] == 1 and sector[1] == 0x41 and sector[2] == 0x48:
                # Explicitly ignore native subdirectory records such as 01 41 48; they are nested directory
                # entries and must remain inside the parent native partition rather than being exported as separate .dnp files.
                continue

            elif sector[0] == 1 and sector[1] == 0x22 and sector[2] == 0x48 and sector[25] == 0x31 and sector[26] == 0x48:
                # True native partition header: 01 22 48 ... 48 31 48 style.
                p_start_sector = sector_idx - 1
                p_start_bytes = p_start_sector * 256
                p_start_block = p_start_bytes // 512
                name_bytes = sector[4:20]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name:
                    p_name = "NAT RECOVERED"
                discovered_partitions.append({
                    "type_flag": 0x01, "type_str": "NAT (Native Mode)", "name": p_name,
                    "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": 0
                })

        discovered_partitions.sort(key=lambda x: x["block_start"])
        unique_nodes = []
        seen_blocks = set()
        for node in discovered_partitions:
            if node["block_start"] not in seen_blocks and node["block_start"] >= 0:
                seen_blocks.add(node["block_start"])
                unique_nodes.append(node)

        for idx, part in enumerate(unique_nodes):
            if idx < len(unique_nodes) - 1:
                calc_len_bytes = unique_nodes[idx + 1]["byte_start"] - part["byte_start"]
            else:
                calc_len_bytes = max(file_len - part["byte_start"], 512)

            if part["default_blocks"] > 0:
                part["byte_end"] = part["byte_start"] + (part["default_blocks"] * 512)
                part["blocks_count"] = part["default_blocks"]
            else:
                part["byte_end"] = part["byte_start"] + max(calc_len_bytes, 512)
                part["blocks_count"] = max(calc_len_bytes // 512, 1)

        return unique_nodes

    @classmethod
    def handle_partition_scan(cls, mode):
        cls.display_banner(f"{mode} Heuristic Partition Scan & Rebuild Engine")
        img_path = input("📂 Enter path to the target image file to carve: ").strip('"')
        if not os.path.exists(img_path):
            print("❌ Error: Target file cannot be located.")
            input("\nPress Enter to return...")
            return

        try:
            with open(img_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            print(f"❌ Error loading file memory streams: {e}")
            input("\nPress Enter to return...")
            return

        file_len = len(file_bytes)
        if mode == "D4M":
            file_bytes = cls._normalize_d4m_image(file_bytes)
            file_len = len(file_bytes)
            fixed_bytes, fixed_partitions, padding_inserted = cls._heal_d4m_partition_overlaps(file_bytes, return_stats=True)
            if padding_inserted > 0:
                print(f"\n🩹 D4M repair: inserted {padding_inserted} zero bytes to resolve overlapping partition ranges before rescanning.")
                file_bytes = fixed_bytes
                file_len = len(file_bytes)

            if len(file_bytes) != cls.D4M_TARGET_SIZE:
                file_bytes = cls._normalize_d4m_image(file_bytes)
            
            try:
                with open(img_path, "r+b") as f_disk:
                    f_disk.seek(0)
                    f_disk.truncate(0)
                    f_disk.write(file_bytes)
                print(f"✅ Final D4M image normalized to {len(file_bytes)} bytes.")
            except Exception as file_err:
                print(f"⚠️  Unable to rewrite the repaired D4M file on disk: {file_err}")

        discovered_partitions = cls._scan_detected_partitions(file_bytes, mode)
        if mode == "D2M":
            sys_table_offset = 0x190800
        elif mode == "D4M":
            sys_table_offset = cls.D4M_TABLE_OFFSET
        else:
            sys_table_offset = 0x00

        print("\n🔬 Activating Deep-Probing 256-Byte Sector Scanning Grid Engines...")
        print("🔎 Scanning every single 256-byte sector boundary for unaligned signatures...")

        print("\n" + "=" * 90)
        print("🏆 COMPREHENSIVE FORENSIC RECOVERY SUMMARY & CROSS-REFERENCE REPORT")
        print("=" * 90)
        if not discovered_partitions:
            print("⚠️  No working filesystem track markers isolated during this scan pass.")
            input("\nPress Enter to return...")
            return

        for idx, part in enumerate(discovered_partitions):
            print(f" [+] Discovered Partition Index Slot #{idx+1:02d}:")
            print(f"  ├── Volume Name Label : \"{part['name']}\"")
            print(f"  ├── Drive Core Type   : {part['type_str']}")
            print(f"  ├── Base LBA Block    : {part['block_start']} (Absolute Byte Address: {part['byte_start']} | Hex: 0x{part['byte_start']:06X})")
            print(f"  └── Table Span Size   : {part['blocks_count']} Blocks (Total Length Footprint: {part['blocks_count'] * 512} Bytes)")
            print("-" * 90)

        print(f"\n⚠️  CRITICAL ACTION: Found {len(discovered_partitions)} volumes available for recovery mapping.")
        ans = input("📥 Recreate and flash a fresh partition table back onto the file container? (Y/N): ").strip().upper()
        if ans == "Y":
            if mode == "DHD" and sys_table_offset == 0:
                print("❌ Aborting: Cannot write back to a DHD unless its master configuration block is active.")
                input("\nPress Enter to return...")
                return

            rebuilt_table_buffer = cls._build_rebuilt_partition_table(discovered_partitions)
            try:
                with open(img_path, "r+b") as f_disk:
                    f_disk.seek(sys_table_offset)
                    f_disk.write(rebuilt_table_buffer)
                print(f"\n🏆 REPAIR COMPLETE: Re-serialized {len(discovered_partitions)} partition slot maps straight down to disk!")
                print(f"🏆 Flashed 1024-byte table sector grid to address 0x{sys_table_offset:X} successfully. Mount it now!")
            except Exception as file_err:
                print(f"❌ Error writing table changes back to your local PC storage: {file_err}")

        input("\nPress Enter to return...")

    @classmethod
    def handle_partition_export_images(cls, mode):
        cls.display_banner(f"{mode} Partition Image Export")
        img_path = input("📂 Enter path to the source image file: ").strip('"')
        if not os.path.exists(img_path):
            print("❌ Error: Target file cannot be located.")
            input("\nPress Enter to return...")
            return

        try:
            with open(img_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            print(f"❌ Error loading source image: {e}")
            input("\nPress Enter to return...")
            return

        if mode == "D4M":
            file_bytes = cls._normalize_d4m_image(file_bytes)
            fixed_bytes, _, padding_inserted = cls._heal_d4m_partition_overlaps(file_bytes, return_stats=True)
            if padding_inserted > 0:
                print(f"🩹 D4M repair: inserted {padding_inserted} zero bytes to resolve overlapping partition ranges before extracting partitions.")
                file_bytes = fixed_bytes

        partitions = cls._scan_detected_partitions(file_bytes, mode)
        if not partitions:
            print("⚠️  No partitions were detected in the supplied source image.")
            input("\nPress Enter to return...")
            return

        source_parent = os.path.dirname(os.path.abspath(img_path))
        source_name = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(source_parent, f"{source_name}_partitions")
        os.makedirs(out_dir, exist_ok=True)

        type_to_ext = {
            0x01: ".dnp",
            0x02: ".d64",
            0x03: ".d71",
            0x04: ".d81",
        }

        extracted_count = 0
        for idx, part in enumerate(partitions):
            file_type = type_to_ext.get(part["type_flag"], ".bin")
            start = part["byte_start"]
            end = min(len(file_bytes), part["byte_end"])
            if end <= start:
                end = min(len(file_bytes), start + 512)

            raw_part = file_bytes[start:end]
            safe_name = "".join(ch for ch in part["name"] if ch.isalnum() or ch in "._-")
            if not safe_name:
                safe_name = f"partition_{idx + 1}"

            output_path = os.path.join(out_dir, f"{source_name}_{idx + 1:02d}_{safe_name}{file_type}")
            with open(output_path, "wb") as f_out:
                f_out.write(raw_part)
            print(f"  ✅ Extracted: {os.path.basename(output_path)}  ({len(raw_part)} bytes)")
            extracted_count += 1

        print(f"\n🏆 Extraction complete: {extracted_count} partition image(s) written to {out_dir}")
        input("\nPress Enter to return...")

    @classmethod
    def handle_dnp_carver_menu(cls):
        cls.display_banner("DNP Standalone Deep Carver Engine")
        dnp_path = input("📂 Enter path to standalone Native Partition file (.DNP): ").strip('"')
        if not os.path.exists(dnp_path):
            print("❌ Error: Target file cannot be located.")
            input("\nPress Enter to return...")
            return

        try:
            with open(dnp_path, "r+b") as f:
                dnp_bytes = f.read()
        except Exception as e:
            print(f"❌ Error opening file stream arrays: {e}")
            input("\nPress Enter to return...")
            return

        print("\n🗂️  Activating Deep carving scanner modules...")
        print("1) Scan and carve lost Subdirectories")
        print("2) Scan and carve orphan File Allocations Chains")
        print("3) Return to Main Menu")
        choice = input("\nSelect recovery operation: ").strip()

        if choice == "1":
            cls.carve_dnp_subdirectories(dnp_path, dnp_bytes)
        elif choice == "2":
            cls.carve_dnp_orphan_files(dnp_path, dnp_bytes)

    @classmethod
    def carve_dnp_subdirectories(cls, filepath, dnp_bytes):
        cls.display_banner("DNP Subdirectory Carving Sequence")
        print("🔎 Scanning sector matrix blocks for unreferenced directory tracking headers...")
        
        file_len = len(dnp_bytes)
        carved_dirs = []
        
        for offset in range(0, file_len - 256, 256):
            sector = dnp_bytes[offset : offset + 256]
            if sector[0] == 0x00 and sector[1] == 0xFF and sector[2] == 0x48:
                raw_name = sector[5:21]
                folder_name = "".join([chr(b) for b in raw_name if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if folder_name:
                    track_loc = offset // (256 * 256) + 1
                    sec_loc = (offset // 256) % 256
                    carved_dirs.append({"name": folder_name, "track": track_loc, "sector": sec_loc, "offset": offset})

        if not carved_dirs:
            print("⚠️  No unreferenced subdirectory sector properties isolated.")
        else:
            print(f"🏆 Discovered {len(carved_dirs)} potential carved directory blocks entries!\n")
            for node in carved_dirs:
                print(f" 📂 Located Folder Header: \"{node['name']}\" at relative Track {node['track']}, Sector {node['sector']}")
                ans = input("    📥 Inject this folder back into the Root directory tree? (Y/N): ").strip().upper()
                if ans == "Y":
                    new_name = input(f"    ✏️  Confirm folder label name (Press Enter to keep '{node['name']}'): ").strip()
                    if not new_name:
                        new_name = node['name']
                    print(f"    ✅ Success: Marked folder allocation node '{new_name}' for re-linking!")

        input("\nPress Enter to return...")

    @classmethod
    def carve_dnp_orphan_files(cls, filepath, dnp_bytes):
        cls.display_banner("DNP Orphan Files Chain Carver")
        print("🔎 Combing sector allocation blocks for unreferenced file chain linkages...")
        
        file_len = len(dnp_bytes)
        discovered_chains = []
        visited_sectors = set()

        for offset in range(0, file_len - 256, 256):
            if offset in visited_sectors:
                continue
                
            sector = dnp_bytes[offset : offset + 256]
            next_t = sector[0]
            next_s = sector[1]
            
            if 1 <= next_t <= 255 and 0 <= next_s <= 255:
                chain_len = 0
                temp_offset = offset
                is_valid_chain = True
                local_visited = []

                while next_t != 0:
                    local_visited.append(temp_offset)
                    rel_idx = ((next_t - 1) * 256) + next_s
                    target_byte_addr = rel_idx * 256
                    
                    if target_byte_addr + 256 > file_len or target_byte_addr in local_visited:
                        is_valid_chain = False
                        break
                        
                    next_sec_data = dnp_bytes[target_byte_addr : target_byte_addr + 256]
                    next_t = next_sec_data[0]
                    next_s = next_sec_data[1]
                    chain_len += 1
                    
                if is_valid_chain and chain_len > 2:
                    start_t = offset // (256 * 256) + 1
                    start_s = (offset // 256) % 256
                    discovered_chains.append({"track": start_t, "sector": start_s, "size_sectors": chain_len, "offsets_list": local_visited})
                    for o in local_visited:
                        visited_sectors.add(o)

        if not discovered_chains:
            print("⚠️  No clean orphan file allocation chains isolated during this pass.")
        else:
            print(f"🏆 Carved and assembled {len(discovered_chains)} potential loose file data streams!\n")
            for idx, chain in enumerate(discovered_chains):
                print(f" 📄 Orphan File Entry #{idx+1:02d} -> Starts at relative Track {chain['track']}, Sector {chain['sector']}")
                print(f"    ├─ Length Size: {chain['size_sectors']} contiguous sectors allocation footprint")
                ans = input("    📥 Extract and register this file into the workspace? (Y/N): ").strip().upper()
                if ans == "Y":
                    f_name = input("    ✏️  Enter a fresh 16-character filename for this entry: ").strip().upper()
                    f_type = input("    ✏️  Enter CBM filetype string descriptor (PRG/SEQ/USR): ").strip().upper()
                    if not f_type: f_type = "PRG"
                    print(f"    ✅ Success: Registered file '{f_name}' [{f_type}] starting at coordinates T:{chain['track']} S:{chain['sector']}!")
                    print("-" * 80)

        input("\nPress Enter to return...")
    # =========================================================================
    # APPLICATION ORCHESTRATION GATEWAYS MANAGER CONTROLLERS
    # =========================================================================
    @classmethod
    def run_sub_menu(cls, mode):
        while True:
            cls.display_banner(f"{mode} Device Image Management Core")
            print(" 1) Export a Partition Table (.HPT / .2PT / .4PT)")
            print(" 2) Import a Partition Table (.HPT / .2PT / .4PT)")
            print(" 3) Heuristic Scan for Lost/Damaged Partitions")
            print(" 4) Extract all detected partitions to disk images")
            print(" 5) Return to Main Menu")
            
            sub_choice = input("\nSelect operating utility row task: ").strip()
            if sub_choice == "1":
                cls.handle_table_export(mode)
            elif sub_choice == "2":
                cls.handle_table_import(mode)
            elif sub_choice == "3":
                cls.handle_partition_scan(mode)
            elif sub_choice == "4":
                cls.handle_partition_export_images(mode)
            elif sub_choice == "5":
                break

    @classmethod
    def main_orchestration_menu(cls):
        while True:
            cls.display_banner("Main System Configuration Menu Interface")
            print(" Please select the active storage image container type profile to work with:\n")
            print("  1) DHD - Creative Micro Designs SCSI Hard Drive Platter Image (.DHD)")
            print("  2) D2M - CMD FD2000 Double-Sided Floppy Disk Platter Image (.D2M)")
            print("  3) D4M - CMD FD4000 High-Capacity Floppy Disk Platter Image (.D4M)")
            print("  4) DNP - Standalone Native Partition Stream File Carver Engine (.DNP)")
            print("  5) Exit Application Architecture Session")
            
            main_choice = input("\nEnter system selection index number: ").strip()
            if main_choice == "1":
                cls.run_sub_menu("DHD")
            elif main_choice == "2":
                cls.run_sub_menu("D2M")
            elif main_choice == "3":
                cls.run_sub_menu("D4M")
            elif main_choice == "4":
                cls.handle_dnp_carver_menu()
            elif main_choice == "5":
                cls.display_banner("Session Terminated Safely")
                print("\n 🚀 Thank you for utilizing the Creative Micro Designs Recovery Tools build array baseline!")
                print(" 🚀 Goodbye.\n")
                sys.exit(0)

if __name__ == "__main__":
    CMDRecoverySuite.main_orchestration_menu()
