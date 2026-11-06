#!/usr/bin/env python3
"""
Retro Emulation Manager & Migrator
A CLI utility to audit, deduplicate, organize, and migrate RetroArch ROM collections,
and generate updated Libretro playlists.
"""

import os
import sys
import shutil
import json
import argparse
from pathlib import Path

# Supported platforms and file extension heuristics
PLATFORM_EXTENSIONS = {
    "nes": [".nes"],
    "snes": [".smc", ".sfc", ".fig"],
    "genesis": [".md", ".gen", ".smd", ".bin"],
    "n64": [".z64", ".n64", ".v64"],
    "gba": [".gba"],
    "gb": [".gb"],
    "gbc": [".gbc"],
    "psx": [".chd", ".cue", ".bin"],
    "ps2": [".iso", ".chd"],
    "gamecube": [".iso", ".nkit.iso", ".gcm", ".rvz"],
    "wii": [".wbfs", ".rvz", ".nkit.iso"],
    "arcade": [".zip"],
    "pc": [".iso", ".img", ".vhd", ".dsk", ".cue", ".zip"]
}

# Known GameCube vs Wii titles in user's collection
GAMECUBE_IDENTIFIERS = [
    "metroid prime", "metroid prime 2", "luigi's mansion",
    "judge dredd", "ultimate spider-man"
]
WII_IDENTIFIERS = ["metroid prime 3", "wii sports", "wii"]
PS2_IDENTIFIERS = ["mega man x7", "ps2", "playstation 2"]
PS1_IDENTIFIERS = [
    "chrono cross", "jackie chan stuntmaster", "marvel super heroes"
]

def detect_platform_from_file(filename, parent_dir_name=""):
    name_lower = filename.lower()
    parent_lower = parent_dir_name.lower()
    combined = f"{parent_lower}/{name_lower}"

    # Check specific multi-console disc games
    if any(k in combined for k in WII_IDENTIFIERS):
        return "wii"
    if any(k in combined for k in GAMECUBE_IDENTIFIERS):
        return "gamecube"
    if any(k in combined for k in PS2_IDENTIFIERS):
        return "ps2"
    if any(k in combined for k in PS1_IDENTIFIERS):
        return "psx"

    # Extension checks
    if name_lower.endswith(".nes"):
        return "nes"
    if name_lower.endswith((".smc", ".sfc", ".fig")):
        return "snes"
    if name_lower.endswith((".z64", ".n64", ".v64")):
        return "n64"
    if name_lower.endswith(".gba"):
        return "gba"
    if name_lower.endswith((".md", ".gen", ".smd")):
        return "genesis"
    if name_lower.endswith(".nkit.iso"):
        return "gamecube"
    if name_lower.endswith(".dsk"):
        return "pc"

    # Zip files can be arcade, PC, or compressed cartridge roms
    if name_lower.endswith(".zip"):
        # Specific arcade zip checks
        arcade_zips = ["mvscu.zip", "mvsc2u.zip", "1941.zip", "rampage.zip", "robocopb.zip"]
        if name_lower in arcade_zips:
            return "arcade"
        return "archive_rom"

    return "unknown"

def analyze_source(source_dir):
    source = Path(source_dir)
    if not source.exists():
        print(f"Error: Source directory {source_dir} does not exist.")
        return None

    report = {
        "total_files": 0,
        "total_size_bytes": 0,
        "platforms": {},
        "duplicates": [],
        "ignored": []
    }

    seen_titles = {}

    for item in sorted(source.iterdir()):
        # Ignore non-game tools
        if "airconnect" in item.name.lower():
            report["ignored"].append(str(item))
            continue

        if item.is_dir():
            # Directory with game contents
            dir_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
            report["total_size_bytes"] += dir_size

            # Check inside directory
            files = [f for f in item.rglob('*') if f.is_file()]
            for f in files:
                report["total_files"] += 1
                plat = detect_platform_from_file(f.name, item.name)
                report["platforms"].setdefault(plat, []).append((f, f.stat().st_size))

        elif item.is_file():
            report["total_files"] += 1
            report["total_size_bytes"] += item.stat().st_size
            plat = detect_platform_from_file(item.name)
            report["platforms"].setdefault(plat, []).append((item, item.stat().st_size))

    return report

def migrate(source_dir, target_dir, dry_run=True, copy_mode=True):
    source = Path(source_dir)
    target = Path(target_dir)

    print(f"=== {'DRY RUN: ' if dry_run else ''}Migration from {source} to {target} ===")
    
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        for p in ["nes", "snes", "genesis", "n64", "gba", "psx", "ps2", "gamecube", "wii", "arcade", "pc"]:
            (target / p).mkdir(parents=True, exist_ok=True)

    action_count = 0
    total_bytes_migrated = 0

    # Collect all items
    for item in sorted(source.iterdir()):
        if "airconnect" in item.name.lower() or item.name.startswith("."):
            continue

        if item.is_file():
            plat = detect_platform_from_file(item.name)
            if plat == "archive_rom":
                # Determine likely platform or place in sorted roms
                plat = "unassigned_zips"
            
            dest_dir = target / plat
            dest_file = dest_dir / item.name
            sz = item.stat().st_size

            action_count += 1
            total_bytes_migrated += sz

            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                if not dest_file.exists():
                    if copy_mode:
                        shutil.copy2(item, dest_file)
                    else:
                        shutil.move(item, dest_file)
            print(f"[{plat.upper()}] {item.name} -> {dest_file} ({sz / (1024**2):.1f} MB)")

        elif item.is_dir():
            # Check if it's a game folder
            files = [f for f in item.rglob('*') if f.is_file()]
            if not files:
                continue

            # Detect main platform
            plat = "unknown"
            for f in files:
                p_cand = detect_platform_from_file(f.name, item.name)
                if p_cand != "unknown":
                    plat = p_cand
                    break

            dest_dir = target / plat
            action_count += 1

            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)

            # If directory has a single rom file, copy the file cleanly
            if len(files) == 1 and plat in ["nes", "snes", "n64", "gba", "genesis"]:
                f = files[0]
                sz = f.stat().st_size
                total_bytes_migrated += sz
                dest_file = dest_dir / f.name
                if not dry_run and not dest_file.exists():
                    if copy_mode:
                        shutil.copy2(f, dest_file)
                    else:
                        shutil.move(f, dest_file)
                print(f"[{plat.upper()}] (Single file extract) {f.name} -> {dest_file} ({sz / (1024**2):.1f} MB)")
            else:
                # Multi-file or disc game (folder kept)
                dest_subfolder = dest_dir / item.name
                dir_size = sum(f.stat().st_size for f in files)
                total_bytes_migrated += dir_size
                if not dry_run and not dest_subfolder.exists():
                    if copy_mode:
                        shutil.copytree(item, dest_subfolder)
                    else:
                        shutil.move(item, dest_subfolder)
                print(f"[{plat.upper()}] (Folder) {item.name}/ -> {dest_subfolder}/ ({dir_size / (1024**2):.1f} MB)")

    print(f"\nCompleted! Total actions: {action_count}, Volume: {total_bytes_migrated / (1024**3):.2f} GB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retro Emulation Manager & Migrator")
    subparsers = parser.add_subparsers(dest="command")

    scan_p = subparsers.add_parser("scan", help="Scan source ROM collection")
    scan_p.add_argument("--source", default="/home/sean/Desktop/Desk926/Game Roms")

    migrate_p = subparsers.add_parser("migrate", help="Migrate ROMs to structured storage")
    migrate_p.add_argument("--source", default="/home/sean/Desktop/Desk926/Game Roms")
    migrate_p.add_argument("--target", default="/mnt/FastDrive/Emulation/roms")
    migrate_p.add_argument("--live", action="store_true", help="Execute live migration (default is dry-run)")
    migrate_p.add_argument("--move", action="store_true", help="Move instead of copy (default copies to preserve safety)")

    args = parser.parse_args()

    if args.command == "scan":
        rep = analyze_source(args.source)
        if rep:
            print(f"Total files: {rep['total_files']}, Total size: {rep['total_size_bytes'] / (1024**3):.2f} GB")
            for plat, flist in rep["platforms"].items():
                sz_gb = sum(s for _, s in flist) / (1024**3)
                print(f"  {plat}: {len(flist)} files ({sz_gb:.2f} GB)")
    elif args.command == "migrate":
        migrate(args.source, args.target, dry_run=not args.live, copy_mode=not args.move)
    else:
        parser.print_help()
