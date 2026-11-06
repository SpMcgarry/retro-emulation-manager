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
import zipfile
import argparse
from pathlib import Path

PLATFORM_NAMES = {
    "nes": "Nintendo - Nintendo Entertainment System",
    "snes": "Nintendo - Super Nintendo Entertainment System",
    "genesis": "Sega - Mega Drive - Genesis",
    "n64": "Nintendo - Nintendo 64",
    "gba": "Nintendo - Game Boy Advance",
    "gb": "Nintendo - Game Boy",
    "gbc": "Nintendo - Game Boy Color",
    "psx": "Sony - PlayStation",
    "ps2": "Sony - PlayStation 2",
    "gamecube": "Nintendo - GameCube",
    "wii": "Nintendo - Wii",
    "arcade": "FBNeo - Arcade Games",
    "pc": "DOS"
}

GAMECUBE_IDENTIFIERS = [
    "metroid prime", "metroid prime 2", "luigi's mansion",
    "judge dredd", "ultimate spider-man"
]
WII_IDENTIFIERS = ["metroid prime 3", "wii sports", "wii"]
PS2_IDENTIFIERS = ["mega man x7", "ps2", "playstation 2"]
PS1_IDENTIFIERS = [
    "chrono cross", "jackie chan stuntmaster", "marvel super heroes"
]
ARCADE_ZIPS = ["mvscu.zip", "mvsc2u.zip", "1941.zip", "rampage.zip", "robocopb.zip"]

def classify_extension(ext):
    ext = ext.lower()
    if ext == ".nes":
        return "nes"
    if ext in [".smc", ".sfc", ".fig"]:
        return "snes"
    if ext in [".md", ".gen", ".smd"]:
        return "genesis"
    if ext in [".z64", ".n64", ".v64"]:
        return "n64"
    if ext == ".gba":
        return "gba"
    if ext == ".gb":
        return "gb"
    if ext == ".gbc":
        return "gbc"
    if ext in [".chd", ".cue"]:
        return "psx"
    if ext == ".nkit.iso":
        return "gamecube"
    if ext in [".dsk", ".vhd", ".img"]:
        return "pc"
    return None

def detect_platform(item_path):
    p = Path(item_path)
    name_lower = p.name.lower()

    # Disc-based titles
    if any(k in name_lower for k in WII_IDENTIFIERS):
        return "wii"
    if any(k in name_lower for k in GAMECUBE_IDENTIFIERS):
        return "gamecube"
    if any(k in name_lower for k in PS2_IDENTIFIERS):
        return "ps2"
    if any(k in name_lower for k in PS1_IDENTIFIERS):
        return "psx"
    if "simcity" in name_lower or name_lower.endswith(".dsk"):
        return "pc"

    if name_lower in ARCADE_ZIPS:
        return "arcade"

    if p.is_file():
        # Check direct extension
        direct_plat = classify_extension(p.suffix)
        if direct_plat:
            return direct_plat

        # Check inside ZIP
        if p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p, 'r') as zf:
                    for inner in zf.namelist():
                        inner_ext = Path(inner).suffix.lower()
                        plat = classify_extension(inner_ext)
                        if plat:
                            return plat
            except Exception:
                pass
            return "arcade"

    elif p.is_dir():
        for sub in p.rglob('*'):
            if sub.is_file():
                plat = detect_platform(sub)
                if plat not in ["unknown", "arcade"]:
                    return plat

    return "unknown"

def clean_game_label(filename):
    stem = Path(filename).stem
    for tag in ["(USA)", "(U)", "(Japan)", "(Europe)", "(E)", "(J)", "[!]", "(Rev 1)", "(Rev 2)", "(1)", "(2)", "(3)"]:
        stem = stem.replace(tag, "")
    return stem.strip().replace("_", ": ")

def generate_playlists(target_dir, playlist_dir):
    target = Path(target_dir)
    p_dir = Path(playlist_dir)
    p_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Generating RetroArch Playlists in {p_dir} ===")

    for plat_key, db_name in PLATFORM_NAMES.items():
        folder = target / plat_key
        if not folder.exists():
            continue

        items = []
        for file_path in sorted(folder.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in [
                ".nes", ".smc", ".sfc", ".fig", ".md", ".gen",
                ".z64", ".n64", ".gba", ".gb", ".gbc", ".chd",
                ".iso", ".nkit.iso", ".wbfs", ".zip", ".dsk"
            ]:
                items.append({
                    "path": str(file_path.resolve()),
                    "label": clean_game_label(file_path.name),
                    "core_path": "DETECT",
                    "core_name": "DETECT",
                    "crc32": "DETECT",
                    "db_name": f"{db_name}.lpl"
                })

        if items:
            pl_file = p_dir / f"{db_name}.lpl"
            data = {
                "version": "1.5",
                "default_core_path": "",
                "default_core_name": "",
                "label_display_mode": 0,
                "right_thumbnail_mode": 0,
                "left_thumbnail_mode": 0,
                "thumbnail_match_mode": 0,
                "sort_mode": 0,
                "items": items
            }
            with open(pl_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Wrote {len(items)} games to playlist: {pl_file.name}")

def migrate(source_dir, target_dir, live=False):
    source = Path(source_dir)
    target = Path(target_dir)

    print(f"=== {'LIVE' if live else 'DRY RUN'} Migration: {source} -> {target} ===")

    if live:
        target.mkdir(parents=True, exist_ok=True)
        for p in PLATFORM_NAMES.keys():
            (target / p).mkdir(parents=True, exist_ok=True)

    migrated_count = 0
    total_bytes = 0

    # 1. Process files and directories
    items = sorted(source.iterdir())
    for item in items:
        # Ignore tools or temporary files
        if "airconnect" in item.name.lower() or item.name.endswith(".crdownload"):
            continue

        plat = detect_platform(item)
        if plat == "unknown":
            continue

        dest_dir = target / plat

        if item.is_file():
            dest_file = dest_dir / item.name
            sz = item.stat().st_size
            total_bytes += sz
            migrated_count += 1
            if live and not dest_file.exists():
                shutil.copy2(item, dest_file)
            print(f"[{plat.upper()}] File: {item.name} ({sz / (1024**2):.1f} MB)")

        elif item.is_dir():
            # If the directory has disc images or PC game files
            subfiles = [f for f in item.rglob('*') if f.is_file()]
            if not subfiles:
                continue

            # If folder is a duplicate or single ROM that's already in a zip, handle cleanly
            if len(subfiles) == 1 and plat in ["nes", "snes", "genesis", "n64", "gba"]:
                single_rom = subfiles[0]
                sz = single_rom.stat().st_size
                dest_file = dest_dir / single_rom.name
                total_bytes += sz
                migrated_count += 1
                if live and not dest_file.exists():
                    shutil.copy2(single_rom, dest_file)
                print(f"[{plat.upper()}] Clean ROM Extract: {single_rom.name} ({sz / (1024**2):.1f} MB)")
            else:
                # Multi-disc, PC game directory, or complex game
                dest_subfolder = dest_dir / item.name
                dir_sz = sum(f.stat().st_size for f in subfiles)
                total_bytes += dir_sz
                migrated_count += 1
                if live and not dest_subfolder.exists():
                    shutil.copytree(item, dest_subfolder)
                print(f"[{plat.upper()}] Game Directory: {item.name}/ ({dir_sz / (1024**2):.1f} MB)")

    print(f"\nSummary: {migrated_count} games organized, Total: {total_bytes / (1024**3):.2f} GB")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retro Emulation Manager & Migrator")
    subparsers = parser.add_subparsers(dest="command")

    migrate_p = subparsers.add_parser("migrate", help="Migrate ROMs to structured storage")
    migrate_p.add_argument("--source", default="/home/sean/Desktop/Desk926/Game Roms")
    migrate_p.add_argument("--target", default="/mnt/FastDrive/Emulation/roms")
    migrate_p.add_argument("--live", action="store_true", help="Execute live migration")

    playlist_p = subparsers.add_parser("playlists", help="Generate RetroArch playlists")
    playlist_p.add_argument("--target", default="/mnt/FastDrive/Emulation/roms")
    playlist_p.add_argument("--playlists", default="/home/sean/.var/app/org.libretro.RetroArch/config/retroarch/playlists")

    args = parser.parse_args()

    if args.command == "migrate":
        migrate(args.source, args.target, live=args.live)
    elif args.command == "playlists":
        generate_playlists(args.target, args.playlists)
    else:
        parser.print_help()
