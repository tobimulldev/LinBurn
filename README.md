# LinBurn

**[Deutsch](#deutsch) | [English](#english)**

---

<a name="deutsch"></a>
# Deutsch

Ein Open-Source-Tool zum Erstellen bootbarer USB-Sticks — inspiriert von [Rufus](https://rufus.ie).
Läuft unter **Linux** und **Windows**.

![LinBurn Screenshot](Assets/Gemini_Generated_Image_296qmr296qmr296q.png)

## Features

- **ISO-Modus** — Dateien kopieren + Bootloader automatisch installieren
- **DD-Modus** — ISO direkt Byte für Byte auf USB schreiben
- **Nur formatieren** — USB-Stick formatieren ohne Boot-Medium
- **Bad-Block-Prüfung** — Fehlerhafte Sektoren vor dem Schreiben erkennen (Linux: `badblocks`, Windows: `chkdsk`)
- **Windows 11 Bypässe** — TPM 2.0 / Secure Boot / RAM / Online-Konto überspringen
- **Partitionsschema** — MBR und GPT
- **Dateisysteme** — FAT32, NTFS, exFAT, ext4
- **Automatische ISO-Erkennung** — Empfohlene Einstellungen werden automatisch gesetzt
- **Hotplug-Erkennung** — USB-Sticks werden automatisch erkannt (Linux: pyudev, Windows: Polling)
- **DE / EN** — Deutsche und englische Oberfläche

## Download

Fertige Pakete sind unter [Releases](../../releases) verfügbar:

| Plattform | Paket | Hinweis |
|-----------|-------|---------|
| Windows 10/11 | `LinBurn.exe` | Einzelne Datei, kein Setup nötig |
| Ubuntu / Debian / Mint | `linburn_*.deb` | APT-kompatibel |
| Alle Linux-Distros | `LinBurn.flatpak` | Sandboxed |

## Installation

### Windows

1. `LinBurn.exe` aus [Releases](../../releases) herunterladen
2. Doppelklick → UAC-Prompt bestätigen → fertig

> Keine Installation, keine Python-Abhängigkeiten — alles in einer Datei.

### .deb (Ubuntu / Debian / Linux Mint)

```bash
sudo dpkg -i linburn_*.deb
sudo apt install -f   # falls Abhängigkeiten fehlen
```

### Flatpak (alle Linux-Distros)

```bash
flatpak install --user LinBurn.flatpak
```

## Selbst bauen

### Linux — Voraussetzungen

```bash
sudo apt install python3-pyqt6 python3-pyudev \
    parted dosfstools ntfs-3g syslinux grub2 e2fsprogs
```

### Linux — .deb bauen

```bash
bash packaging/build_deb.sh
```

### Linux — Flatpak bauen

```bash
flatpak install org.freedesktop.Sdk//24.08 org.freedesktop.Platform//24.08
flatpak-builder --user --install --force-clean build-flatpak \
    packaging/flatpak/io.github.linburn.LinBurn.yaml
```

### Linux — Direkt starten (ohne Installation)

```bash
sudo python3 main.py
```

### Windows — .exe bauen

```bat
packaging\windows\build_exe.bat
```

Voraussetzungen: Python 3.10+, pip (PyInstaller und PyQt6 werden automatisch installiert).
Ausgabe: `dist\LinBurn.exe`

Alternativ wird die `.exe` automatisch per **GitHub Actions** gebaut, wenn ein Release veröffentlicht wird.

## Systemvoraussetzungen

### Linux

| Tool | Paket | Zweck |
|------|-------|-------|
| `parted` | `parted` | Partitionierung |
| `mkfs.fat` | `dosfstools` | FAT32-Formatierung |
| `mkfs.ntfs` | `ntfs-3g` | NTFS-Formatierung |
| `mkfs.exfat` | `exfatprogs` | exFAT-Formatierung |
| `syslinux` | `syslinux` | BIOS-Bootloader |
| `grub-install` | `grub2` | UEFI-Bootloader |
| `badblocks` | `e2fsprogs` | Bad-Block-Prüfung |
| `wimlib-imagex` | `wimtools` | install.wim splitten (Windows-ISO > 4 GB) |

### Windows

Alles bereits im System vorhanden — keine zusätzlichen Tools nötig:

| Tool | Zweck |
|------|-------|
| `diskpart` | Partitionierung + Formatierung |
| PowerShell `Mount-DiskImage` | ISO einbinden |
| `dism` | install.wim splitten |
| `chkdsk` | Bad-Block-Prüfung |
| `bootsect.exe` | BIOS-Bootloader (optional) |

## Lizenz

Dieses Projekt steht unter der [GPL-3.0 Lizenz](LICENSE).

---

<a name="english"></a>
# English

An open-source tool for creating bootable USB drives — inspired by [Rufus](https://rufus.ie).
Runs on **Linux** and **Windows**.

## Features

- **ISO mode** — Copy files and install bootloader automatically
- **DD mode** — Write ISO directly byte-for-byte to USB
- **Format only** — Format USB drive without writing a boot image
- **Bad block check** — Detect faulty sectors before writing (Linux: `badblocks`, Windows: `chkdsk`)
- **Windows 11 bypasses** — Skip TPM 2.0 / Secure Boot / RAM / online account requirements
- **Partition scheme** — MBR and GPT
- **Filesystems** — FAT32, NTFS, exFAT, ext4
- **Automatic ISO detection** — Recommended settings applied automatically
- **Hotplug detection** — USB drives detected automatically (Linux: pyudev, Windows: polling)
- **DE / EN** — German and English UI

## Download

Ready-to-use packages are available under [Releases](../../releases):

| Platform | Package | Notes |
|----------|---------|-------|
| Windows 10/11 | `LinBurn.exe` | Single file, no setup required |
| Ubuntu / Debian / Mint | `linburn_*.deb` | APT-compatible |
| All Linux distros | `LinBurn.flatpak` | Sandboxed |

## Installation

### Windows

1. Download `LinBurn.exe` from [Releases](../../releases)
2. Double-click → confirm UAC prompt → done

> No installation, no Python dependencies — everything in one file.

### .deb (Ubuntu / Debian / Linux Mint)

```bash
sudo dpkg -i linburn_*.deb
sudo apt install -f   # if dependencies are missing
```

### Flatpak (all Linux distros)

```bash
flatpak install --user LinBurn.flatpak
```

## Building from source

### Linux — Prerequisites

```bash
sudo apt install python3-pyqt6 python3-pyudev \
    parted dosfstools ntfs-3g syslinux grub2 e2fsprogs
```

### Linux — Build .deb

```bash
bash packaging/build_deb.sh
```

### Linux — Build Flatpak

```bash
flatpak install org.freedesktop.Sdk//24.08 org.freedesktop.Platform//24.08
flatpak-builder --user --install --force-clean build-flatpak \
    packaging/flatpak/io.github.linburn.LinBurn.yaml
```

### Linux — Run directly (without installation)

```bash
sudo python3 main.py
```

### Windows — Build .exe

```bat
packaging\windows\build_exe.bat
```

Requirements: Python 3.10+, pip (PyInstaller and PyQt6 are installed automatically).
Output: `dist\LinBurn.exe`

The `.exe` is also built automatically via **GitHub Actions** whenever a release is published.

## System requirements

### Linux

| Tool | Package | Purpose |
|------|---------|---------|
| `parted` | `parted` | Partitioning |
| `mkfs.fat` | `dosfstools` | FAT32 formatting |
| `mkfs.ntfs` | `ntfs-3g` | NTFS formatting |
| `mkfs.exfat` | `exfatprogs` | exFAT formatting |
| `syslinux` | `syslinux` | BIOS bootloader |
| `grub-install` | `grub2` | UEFI bootloader |
| `badblocks` | `e2fsprogs` | Bad block checking |
| `wimlib-imagex` | `wimtools` | Split install.wim (Windows ISO > 4 GB) |

### Windows

Everything is already built into the system — no additional tools required:

| Tool | Purpose |
|------|---------|
| `diskpart` | Partitioning + formatting |
| PowerShell `Mount-DiskImage` | Mount ISO images |
| `dism` | Split install.wim |
| `chkdsk` | Bad block checking |
| `bootsect.exe` | BIOS bootloader (optional) |

## License

This project is licensed under the [GPL-3.0 License](LICENSE).
