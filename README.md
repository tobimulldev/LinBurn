# LinBurn

Ein Open-Source-Tool zum Erstellen bootbarer USB-Sticks unter Linux — inspiriert von [Rufus](https://rufus.ie).

![LinBurn Screenshot](Assets/Gemini_Generated_Image_296qmr296qmr296q.png)

## Features

- **ISO-Modus** — Dateien kopieren + Bootloader automatisch installieren
- **DD-Modus** — ISO direkt Byte für Byte auf USB schreiben
- **Nur formatieren** — USB-Stick formatieren ohne Boot-Medium
- **Bad-Block-Prüfung** — Fehlerhafte Sektoren vor dem Schreiben erkennen
- **Windows 11 Bypässe** — TPM 2.0 / Secure Boot / RAM / Online-Konto überspringen
- **Partitionsschema** — MBR und GPT
- **Dateisysteme** — FAT32, NTFS, exFAT, ext4
- **Automatische ISO-Erkennung** — Empfohlene Einstellungen werden automatisch gesetzt
- **DE / EN** — Deutsche und englische Oberfläche

## Installation

### .deb (Ubuntu / Debian / Linux Mint)

```bash
sudo dpkg -i linburn_1.0.0_amd64.deb
sudo apt install -f   # falls Abhängigkeiten fehlen
```

### Flatpak

```bash
flatpak install --user LinBurn.flatpak
```

Fertige Pakete sind unter [Releases](../../releases) verfügbar.

## Selbst bauen

### Voraussetzungen

```bash
sudo apt install python3-pyqt6 python3-pyudev \
    parted dosfstools ntfs-3g syslinux grub2 e2fsprogs
```

### .deb bauen

```bash
bash packaging/build_deb.sh
```

### Flatpak bauen

```bash
flatpak install org.freedesktop.Sdk//24.08 org.freedesktop.Platform//24.08
flatpak-builder --user --install --force-clean build-flatpak \
    packaging/flatpak/io.github.linburn.LinBurn.yaml
```

### Direkt starten (ohne Installation)

```bash
sudo python3 main.py
```

## Systemvoraussetzungen

| Tool | Paket | Zweck |
|------|-------|-------|
| `parted` | `parted` | Partitionierung |
| `mkfs.fat` | `dosfstools` | FAT32-Formatierung |
| `mkfs.ntfs` | `ntfs-3g` | NTFS-Formatierung |
| `syslinux` | `syslinux` | BIOS-Bootloader |
| `grub-install` | `grub2` | UEFI-Bootloader |
| `badblocks` | `e2fsprogs` | Bad-Block-Prüfung |

## Lizenz

Dieses Projekt steht unter der [GPL-3.0 Lizenz](LICENSE).
