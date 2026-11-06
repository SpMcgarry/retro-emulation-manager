# Retro Emulation Manager & Migrator

A command-line tool built to audit, deduplicate, organize, and migrate RetroArch ROM collections across modern Linux storage systems (NVMe / secondary mounts) and generate clean Libretro playlists.

## Features
- **Smart Platform Detection**: Automatically categorizes cartridge, disc, and arcade formats (`.nes`, `.smc`/`.sfc`, `.md`, `.z64`, `.gba`, `.chd`, `.iso`, `.nkit.iso`, `.zip`).
- **Safe Dry-Run Migration**: Simulates moves/copies to verify paths and destination directories before touching the filesystem.
- **Deduplication Awareness**: Identifies duplicate extractions (`Folder (2)`, uncompressed ROM vs. archive ZIP).
- **RetroArch Storage Alignment**: Prepares structured folders matching Libretro core standards (`/mnt/FastDrive/Emulation/roms/`).

## Usage

### 1. Scan Source ROMs
```bash
python3 rom_manager.py scan --source "/home/sean/Desktop/Desk926/Game Roms"
```

### 2. Dry-Run Migration (Simulation)
```bash
python3 rom_manager.py migrate --source "/home/sean/Desktop/Desk926/Game Roms" --target "/mnt/FastDrive/Emulation/roms"
```

### 3. Live Migration (Safe Copy)
```bash
python3 rom_manager.py migrate --source "/home/sean/Desktop/Desk926/Game Roms" --target "/mnt/FastDrive/Emulation/roms" --live
```
