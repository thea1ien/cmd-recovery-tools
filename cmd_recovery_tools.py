import os
import struct
import sys

class CMDRecoverySuite:
    VERSION = "v1.0.0"

    # --- CORE FILE IO EXTENSION LOOKUPS ---
    FORMAT_EXTENSIONS = {
        "DHD": ".HPT",
        "D2M": ".2PT",
        "D4M": ".4PT"
    }

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
    def handle_partition_scan(cls, mode):
        cls.display_banner(f"{mode} Heuristic Partition Scan")
        img_path = input("📂 Enter path to the target image file to carve: ").strip('"')
        if not os.path.exists(img_path):
            print("❌ Error: Target file cannot be located.")
            input("\nPress Enter to return...")
            return

        print("\n🔍 Activating Heuristic Sector-Scanning Grid Engines...")
        print("🔍 Searching for structural filesystem signatures at 256-byte boundaries...")
        
        try:
            with open(img_path, "rb") as f:
                file_bytes = f.read()
        except Exception as e:
            print(f"❌ Error loading file memory streams: {e}")
            input("\nPress Enter to return...")
            return

        file_len = len(file_bytes)
        discovered_partitions = []

        for current_offset in range(0, file_len - 256, 256):
            sector = file_bytes[current_offset : current_offset + 256]
            
            if current_offset + 512 < file_len:
                bam_sec1 = file_bytes[current_offset + 256 : current_offset + 512]
                if sector[0] == 40 and sector[1] == 3 and sector[2] == 0x44:
                    if bam_sec1[0] == 0x00 and bam_sec1[1] == 0xFF and bam_sec1[2] == 0x44:
                        discovered_partitions.append({
                            "type": "1581 Emulation (D81)",
                            "byte_start": current_offset - (39 * 40 * 256),
                            "block_start": (current_offset - (39 * 40 * 256)) // 512
                        })
                        continue

            if sector[0] == 18 and sector[1] == 1 and sector[2] == 0x41:
                base_1541_offset = current_offset - (17 * 21 * 256)
                is_1571 = False
                ext_bam_track_offset = base_1541_offset + (34 * 256 * 21) + (18 * 256)
                if ext_bam_track_offset + 256 <= file_len:
                    ext_bam_sector = file_bytes[ext_bam_track_offset : ext_bam_track_offset + 256]
                    if ext_bam_sector[0] == 0x00 and ext_bam_sector[1] == 0xFF:
                        is_1571 = True

                p_label = "1571 Emulation (D71)" if is_1571 else "1541 Emulation (D64)"
                discovered_partitions.append({
                    "type": p_label,
                    "byte_start": max(0, base_1541_offset),
                    "block_start": max(0, base_1541_offset) // 512
                })
                continue

            if current_offset + 512 < file_len:
                nat_bam = file_bytes[current_offset + 256 : current_offset + 512]
                if sector[2] == 0x48 and nat_bam[0] == 0x00 and nat_bam[1] == 0xFF and nat_bam[2] == 0x48:
                    discovered_partitions.append({
                        "type": "CMD Native Partition (DNP)",
                        "byte_start": current_offset,
                        "block_start": current_offset // 512
                    })

        print("\n" + "=" * 80)
        print("🏆 HEURISTIC CARVER SCANNING RECOVERY SUMMARY")
        print("=" * 80)
        if not discovered_partitions:
            print("⚠️  No standalone filesystem sector signature signatures discovered.")
        else:
            discovered_partitions.sort(key=lambda x: x["byte_start"])
            unique_nodes = []
            seen_offsets = set()
            for node in discovered_partitions:
                rounded_start = (node["byte_start"] // 512) * 512
                if rounded_start not in seen_offsets:
                    seen_offsets.add(rounded_start)
                    node["byte_start"] = rounded_start
                    node["block_start"] = rounded_start // 512
                    unique_nodes.append(node)

            for idx, part in enumerate(unique_nodes):
                if idx < len(unique_nodes) - 1:
                    calculated_len_bytes = unique_nodes[idx+1]["byte_start"] - part["byte_start"]
                else:
                    calculated_len_bytes = file_len - part["byte_start"]

                calculated_blocks = calculated_len_bytes // 512
                
                print(f" Discovered Volume Entry #{idx+1:02d}:")
                print(f"  ├── Partition Profile Model : {part['type']}")
                print(f"  ├── Base LBA Block Pointer  : {part['block_start']} (Hex Absolute Offset: 0x{part['byte_start']:06X})")
                print(f"  └── Calculated Blocks Span  : {calculated_blocks} Blocks ({calculated_len_bytes} Bytes) [BEST GUESS MAP]")
                print("-" * 80)

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
            print(" 4) Return to Main Menu")
            
            sub_choice = input("\nSelect operating utility row task: ").strip()
            if sub_choice == "1":
                cls.handle_table_export(mode)
            elif sub_choice == "2":
                cls.handle_table_import(mode)
            elif sub_choice == "3":
                cls.handle_partition_scan(mode)
            elif sub_choice == "4":
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
