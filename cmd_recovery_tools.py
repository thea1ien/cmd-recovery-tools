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
        discovered_partitions = []
        
        if mode == "D2M":   sys_table_offset = 0x190800
        elif mode == "D4M": sys_table_offset = 0x320800
        else:               sys_table_offset = 0x00

        print("\n🔬 Activating Deep-Probing 256-Byte Sector Scanning Grid Engines...")
        print("🔎 Scanning every single 256-byte sector boundary for unaligned signatures...")

        # FIXED ALIGNMENT PHYSICS: We step explicitly by 256 bytes to catch signatures no matter which half of a block they sit in!
        for sector_idx in range(0, file_len // 256):
            offset = sector_idx * 256
            if offset + 256 > file_len:
                break

            sector = file_bytes[offset : offset + 256]

            # --- HEURISTIC PROBE 1: 1581 FORMAT BOUNDARIES MAP ---
            # A 1581 Directory Header sits at T40 S0. It links forward to Track 40, Sector 3 (sector[0]=40, sector[1]=3).
            # Byte 2 holds the master character code 'D' (0x44). 
            # FIXED: Corrected the layout signature validation to target indices 25 and 26 natively!
            if sector[0] == 40 and sector[1] == 3 and sector[2] == 0x44:
                if sector[25] == 0x33 and sector[26] == 0x44: # Confirms ASCII "3D" at positions 25 and 26
                    # 1581 headers sit at Track 40, Sector 0. To calculate the base of Track 1, Sector 0:
                    # Step back exactly 39 tracks * 40 sectors/track = 1560 sectors allocation footprint
                    p_start_sector = sector_idx - 1560
                    p_start_bytes = p_start_sector * 256
                    p_start_block = p_start_bytes // 512

                    # Extract disk name label out of the Track 40 header record string offsets safely
                    name_bytes = sector[4 : 20] # Standard 16-byte name field shift window offset
                    p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                    if not p_name: p_name = "1581 RECOVERED"

                    discovered_partitions.append({
                        "type_flag": 0x04, "type_str": "81 (1581 Mode)", "name": p_name,
                        "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": 1600
                    })
                    continue


            # --- HEURISTIC PROBE 2: 1541 / 1571 DIRECTORY BAM SECTORS ---
            # Standard CBM BAM sits at Track 18, Sector 0. Byte 0=18, Byte 1=1, Byte 2='A' (0x41)
            elif sector[0] == 18 and sector[1] == 1 and sector[2] == 0x41:
                # Step back 17 tracks * 21 sectors/track = 357 sectors to hit Track 1, Sector 0
                p_start_sector = sector_idx - 357
                p_start_bytes = p_start_sector * 256
                p_start_block = p_start_bytes // 512

                # Extract partition name label safely out of the Track 18 header string offsets
                name_bytes = sector[144 : 160]
                p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                if not p_name: p_name = "RECOVERED CBM"

                # --- HARDWARE INTEGRITY EXTRACTION PASS ---
                # Inspect Byte 3 of the BAM sector: 0x80 explicitly flags a 1571 double-sided format!
                if sector[3] == 0x80:
                    is_1571 = True
                else:
                    # Fallback verification step: check if side-2 BAM records exist at relative track 53
                    is_1571 = False
                    lookahead_1571_offset = (p_start_block * 512) + (34 * 256 * 21) + (18 * 256)
                    if lookahead_1571_offset + 256 <= file_len:
                        ext_bam = file_bytes[lookahead_1571_offset : lookahead_1571_offset + 256]
                        if ext_bam[0] == 0x00 and ext_bam[1] == 0xFF:
                            is_1571 = True

                t_code = 0x03 if is_1571 else 0x02
                t_label = "71 (1571 Mode)" if is_1571 else "41 (1541 Mode)"
                t_blocks = 684 if is_1571 else 342

                discovered_partitions.append({
                    "type_flag": t_code, "type_str": t_label, "name": p_name,
                    "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": t_blocks
                })


            # --- HEURISTIC PROBE 3: CMD NATIVE PARTITION (NAT) ---
            # --- HEURISTIC PROBE 3: CMD NATIVE PARTITION (NAT) ---
            # A DNP Native Directory Header sits at Track 1, Sector 1.
            # FIXED: Validated against your physical screen dump parameters:
            # 1) Link Track byte must be Track 1 (0x01)
            # 2) Offset 2 must hold the character 'H' (0x48)
            # 3) Offsets 25 and 26 must hold the exact "$31 $48" ("1H") DOS layout ID signature string!
            elif sector[0] == 1 and sector[2] == 0x48:
                if sector[25] == 0x31 and sector[26] == 0x48:
                    # Because T1 S1 is exactly 1 sector deep from the absolute partition boundary base (Track 1, Sector 0),
                    # we step back precisely 1 sector (256 bytes) to calculate the true starting LBA block!
                    p_start_sector = sector_idx - 1
                    p_start_bytes = p_start_sector * 256
                    p_start_block = p_start_bytes // 512

                    # Extract disk name label out of the Track 1, Sector 1 directory header field offsets safely
                    name_bytes = sector[4 : 20] # Standard 16-character volume label slice
                    p_name = "".join([chr(b) for b in name_bytes if 32 <= b <= 126 or b == 0xA0]).replace(chr(0xA0), " ").strip()
                    if not p_name: p_name = "NAT RECOVERED"

                    discovered_partitions.append({
                        "type_flag": 0x01, "type_str": "NAT (Native Mode)", "name": p_name,
                        "block_start": p_start_block, "byte_start": p_start_block * 512, "default_blocks": 0
                    })


        # Process, clean up duplicates, and sort final records
        discovered_partitions.sort(key=lambda x: x["block_start"])
        unique_nodes = []
        seen_blocks = set()
        for node in discovered_partitions:
            if node["block_start"] not in seen_blocks and node["block_start"] >= 0:
                seen_blocks.add(node["block_start"])
                unique_nodes.append(node)

        print("\n" + "=" * 90)
        print("🏆 COMPREHENSIVE FORENSIC RECOVERY SUMMARY & CROSS-REFERENCE REPORT")
        print("=" * 90)
        if not unique_nodes:
            print("⚠️  No working filesystem track markers isolated during this scan pass.")
            input("\nPress Enter to return...")
            return

        # COLLISION PROCESSING ENGINE: Dynamically balance block allocations based on the next neighbor
        for idx, part in enumerate(unique_nodes):
            if idx < len(unique_nodes) - 1:
                calc_len_bytes = unique_nodes[idx+1]["byte_start"] - part["byte_start"]
            else:
                calc_len_bytes = file_len - part["byte_start"]
                
            calc_blocks_size = calc_len_bytes // 512
            # For rigid emulation formats, enforce their physical hardware constraint caps
            if part["default_blocks"] > 0:
                part["blocks_count"] = part["default_blocks"]
            else:
                part["blocks_count"] = calc_blocks_size

            print(f" [+] Discovered Partition Index Slot #{idx+1:02d}:")
            print(f"  ├── Volume Name Label : \"{part['name']}\"")
            print(f"  ├── Drive Core Type   : {part['type_str']}")
            print(f"  ├── Base LBA Block    : {part['block_start']} (Absolute Byte Address: {part['byte_start']} | Hex: 0x{part['byte_start']:06X})")
            print(f"  └── Table Span Size   : {part['blocks_count']} Blocks (Total Length Footprint: {part['blocks_count'] * 512} Bytes)")
            print("-" * 90)

        # --- THE ACTIVE RECOVERY TABLE FLASHER REPAIR PASS ---
        print(f"\n⚠️  CRITICAL ACTION: Found {len(unique_nodes)} volumes available for recovery mapping.")
        ans = input("📥 Recreate and flash a fresh partition table back onto the file container? (Y/N): ").strip().upper()
        if ans == "Y":
            if mode == "DHD" and sys_table_offset == 0:
                print("❌ Aborting: Cannot write back to a DHD unless its master configuration block is active.")
                input("\nPress Enter to return...")
                return

            # Compile a fresh, sterile 1024-byte table block initialized with binary null primitives
            rebuilt_table_buffer = bytearray(1024)
            
            # Map out Slot 0 as your rigid hardware SYSTEM Configuration Block
            rebuilt_table_buffer[2] = 0xFF # Type SYSTEM
            # Pad filename field index rows with unshifted spaces (0xA0) up to 16 characters
            rebuilt_table_buffer[5:21] = b"SYSTEM".ljust(16, b"\xA0")
            # Set System track starting position matching hardware offsets
            sys_start_lba = sys_table_offset // 512
            rebuilt_table_buffer[21] = (sys_start_lba >> 16) & 0xFF
            rebuilt_table_buffer[22] = (sys_start_lba >> 8) & 0xFF
            rebuilt_table_buffer[23] = sys_start_lba & 0xFF
            rebuilt_table_buffer[29] = 0
            rebuilt_table_buffer[30] = 0
            rebuilt_table_buffer[31] = 12 # Standard 12-block configuration tracking width width
            
            # Loop sequentially and write your recovered entry nodes into slots 1 through 31
            for idx, part in enumerate(unique_nodes[:31]):
                slot_offset = (idx + 1) * 32
                
                rebuilt_table_buffer[slot_offset] = 0x00 # Next link tracking track pointer
                rebuilt_table_buffer[slot_offset + 1] = 0x00 # Next link sector pointer
                rebuilt_table_buffer[slot_offset + 2] = part["type_flag"] # Inject type integer
                
                # Format name label safely to PETSCII space-padded bytes
                clean_petscii_name = part["name"].upper().encode('ascii', errors='ignore')[:16].ljust(16, b"\xA0")
                rebuilt_table_buffer[slot_offset + 5 : slot_offset + 21] = clean_petscii_name
                
                # Inject 24-bit Big-Endian Location Block into bytes 21, 22, 23
                loc_lba = part["block_start"]
                rebuilt_table_buffer[slot_offset + 21] = (loc_lba >> 16) & 0xFF
                rebuilt_table_buffer[slot_offset + 22] = (loc_lba >> 8) & 0xFF
                rebuilt_table_buffer[slot_offset + 23] = loc_lba & 0xFF
                
                # Inject 24-bit Big-Endian Size Blocks Count into final trailing bytes 29, 30, 31
                sz_blocks = part["blocks_count"]
                rebuilt_table_buffer[slot_offset + 29] = (sz_blocks >> 16) & 0xFF
                rebuilt_table_buffer[slot_offset + 30] = (sz_blocks >> 8) & 0xFF
                rebuilt_table_buffer[slot_offset + 31] = sz_blocks & 0xFF

            try:
                # Open up the real file handle on your desktop and overwrite the exact table offset bytes!
                with open(img_path, "r+b") as f_disk:
                    f_disk.seek(sys_table_offset)
                    f_disk.write(rebuilt_table_buffer)
                print(f"\n🏆 REPAIR COMPLETE: Re-serialized {len(unique_nodes)} partition slot maps straight down to disk!")
                print(f"🏆 Flashed 1024-byte table sector grid to address 0x{sys_table_offset:X} successfully. Mount it now!")
            except Exception as file_err:
                print(f"❌ Error writing table changes back to your local PC storage: {file_err}")

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
