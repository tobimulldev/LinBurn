"""Translations for LinBurn GUI (German / English)."""

_language = "de"


def get_language() -> str:
    return _language


def set_language(lang: str):
    global _language
    if lang in TRANSLATIONS:
        _language = lang


def tr(key: str) -> str:
    lang_dict = TRANSLATIONS.get(_language, TRANSLATIONS["de"])
    return lang_dict.get(key, TRANSLATIONS["de"].get(key, key))


TRANSLATIONS = {
    "de": {
        "window_title": "LinBurn — Bootbarer USB-Stick Ersteller",
        "subtitle": "Bootbaren USB-Stick erstellen",
        "device_label": "Gerät:",
        "device_tooltip": "USB-Stick auswählen",
        "refresh_tooltip": "Geräteliste aktualisieren",
        "boot_type_label": "Boot-Auswahl:",
        "boot_iso": "ISO-Abbild",
        "boot_format_only": "Nur formatieren (kein Boot)",
        "iso_placeholder": "ISO-Datei auswählen...",
        "browse_tooltip": "ISO-Datei auswählen",
        "image_option_label": "Image-Option:",
        "image_standard": "Standard (empfohlen)",
        "image_dd": "DD-Modus (Direktkopie)",
        "image_option_tooltip": (
            "Standard: Dateien kopieren + Bootloader installieren\n"
            "DD: ISO direkt Byte für Byte auf USB schreiben"
        ),
        "scheme_label": "Partitionsschema:",
        "scheme_tooltip": (
            "MBR: Für ältere BIOS-Systeme (max 2TB)\n"
            "GPT: Für moderne UEFI-Systeme (empfohlen)"
        ),
        "target_label": "Zielsystem:",
        "target_bios": "BIOS (oder UEFI-CSM)",
        "target_uefi": "UEFI (non-CSM)",
        "target_both": "BIOS + UEFI",
        "fs_label": "Dateisystem:",
        "fs_fat32": "FAT32 (Standard)",
        "cluster_label": "Clustergröße:",
        "cluster_default": "Standard",
        "vol_label": "Volume-Bezeichnung:",
        "quick_format": "Schnellformatierung (Quick Format)",
        "quick_format_tooltip": (
            "Aktiviert: Nur Dateisystemstruktur schreiben (schnell)\n"
            "Deaktiviert: Gesamten Datenträger überschreiben (langsam, sicherer)"
        ),
        "bad_blocks": "Bad Blocks prüfen (vor dem Schreiben)",
        "bad_blocks_tooltip": (
            "Prüft den USB-Stick vor dem Schreiben auf fehlerhafte Sektoren.\n"
            "Verlängert die Gesamtdauer erheblich."
        ),
        "win_group": "Windows 11 – Kompatibilitätsprüfungen umgehen",
        "win_warning": "Erkannt: Windows 11 ISO\nFolgende Bypässe können aktiviert werden:",
        "win_warning_generic": "Windows-ISO erkannt (Win11-Erkennung ungewiss)\nBypässe sind für Windows 11 relevant – bei Win11-ISO empfohlen:",
        "win_bypass_tpm": "TPM 2.0-Anforderung umgehen",
        "win_bypass_secureboot": "Secure Boot-Anforderung umgehen",
        "win_bypass_ram": "RAM-Anforderung umgehen (< 8 GB)",
        "win_remove_online": "Online-Konto-Pflicht entfernen (lokales Konto erlauben)",
        "step_label": "Schritt 0 / 0",
        "step_format": "Schritt %p%",
        "status_ready": "Bereit",
        "total_format": "Gesamt %p%",
        "btn_about": "Über",
        "btn_cancel": "Abbrechen",
        "btn_close": "Schließen",
        "log_group": "Protokoll",
        "no_device": "Kein USB-Gerät gefunden",
        "analyzing_iso": "Analysiere ISO...",
        "analyzing_iso_log": "Analysiere ISO-Abbild...",
        "iso_analysis_error": "Fehler bei ISO-Analyse: {0}",
        "iso_analysis_failed": "ISO-Analyse fehlgeschlagen",
        "yes": "Ja",
        "no": "Nein",
        "lbl_bootable": "Bootbar",
        "iso_ready": "ISO bereit",
        "win11_detected_log": "Windows 11 erkannt – Kompatibilitätsbypässe verfügbar.",
        "win_detected_log": "Windows-ISO erkannt – Win11-Bypässe sichtbar (Win11 nicht eindeutig erkannt).",
        "step_format_dyn": "Schritt {0} / {1}",
        "status_done": "Fertig!",
        "log_done": "=== Vorgang erfolgreich abgeschlossen ===",
        "status_error": "Fehler!",
        "status_cancelled": "Abgebrochen",
        "log_bad_block_start": "=== Starte Bad-Block-Prüfung ===",
        "log_bad_block": "Schlechter Block: {0}",
        "log_abort_req": "Abbruch angefordert...",
        "log_bad_block_aborted": "Bad-Block-Prüfung abgebrochen.",
        "log_write_start": "=== Starte Schreibvorgang ({0}-Modus) ===",
        "log_device": "Gerät: {0}",
        "log_iso": "ISO: {0}",
        "log_error": "FEHLER: {0}",
        "dlg_no_device_title": "Kein Gerät",
        "dlg_no_device_msg": "Bitte einen USB-Stick auswählen.",
        "dlg_no_iso_title": "Kein ISO",
        "dlg_no_iso_msg": "Bitte eine ISO-Datei auswählen.",
        "dlg_file_not_found_title": "Datei nicht gefunden",
        "dlg_file_not_found_msg": "ISO-Datei nicht gefunden:\n{0}",
        "dlg_confirm_title": "Bestätigung",
        "dlg_confirm_warning": "WARNUNG: Alle Daten auf {0} werden UNWIDERRUFLICH gelöscht!\n\nGerät: {0}\n",
        "dlg_confirm_iso": "ISO: {0}\n",
        "dlg_confirm_cont": "\nFortfahren?",
        "dlg_quit_title": "Beenden",
        "dlg_quit_msg": "Ein Schreibvorgang läuft noch!\nWirklich beenden?",
        "dlg_bad_blocks_title": "Schlechte Blöcke gefunden",
        "dlg_bad_blocks_msg": (
            "{0} schlechte Block(e) gefunden!\n"
            "Der USB-Stick könnte fehlerhaft sein.\n\n"
            "Trotzdem fortfahren?"
        ),
        "dlg_cancel_title": "Abbrechen",
        "dlg_cancel_msg": (
            "Schreibvorgang wirklich abbrechen?\n\n"
            "Der USB-Stick könnte unbrauchbar werden."
        ),
        "dlg_done_title": "Fertig",
        "dlg_done_msg": (
            "Der bootbare USB-Stick wurde erfolgreich erstellt!\n\n"
            "Der USB-Stick kann jetzt sicher entfernt werden."
        ),
        "dlg_error_title": "Fehler",
        "dlg_error_msg": "Fehler beim Schreiben:\n\n{0}",
        "dlg_about_title": "Über LinBurn",
        "dlg_about_msg": (
            "<h3>LinBurn für Linux</h3>"
            "<p>Ein Open-Source-Tool zum Erstellen bootbarer USB-Sticks.</p>"
            "<p>Inspiriert von <a href='https://rufus.ie'>Rufus</a> von Pete Batard.</p>"
            "<br>"
            "<b>Features:</b>"
            "<ul>"
            "<li>ISO-Modus (Dateien kopieren + Bootloader)</li>"
            "<li>DD-Modus (direktes Schreiben)</li>"
            "<li>USB formatieren</li>"
            "<li>Bad-Block-Prüfung</li>"
            "<li>Windows 11 TPM/SecureBoot-Bypass</li>"
            "<li>Online-Konto-Bypass (lokales Konto)</li>"
            "</ul>"
            "<p>Systemvoraussetzungen: parted, syslinux, grub2, badblocks</p>"
        ),
        "iso_open_title": "ISO-Abbild öffnen",
        "iso_filter": "Disk Images (*.iso *.img *.bin *.dmg);;Alle Dateien (*)",
    },
    "en": {
        "window_title": "LinBurn — Bootable USB Drive Creator",
        "subtitle": "Create Bootable USB Drive",
        "device_label": "Device:",
        "device_tooltip": "Select USB drive",
        "refresh_tooltip": "Refresh device list",
        "boot_type_label": "Boot Type:",
        "boot_iso": "ISO Image",
        "boot_format_only": "Format only (no boot)",
        "iso_placeholder": "Select ISO file...",
        "browse_tooltip": "Select ISO file",
        "image_option_label": "Image Option:",
        "image_standard": "Standard (recommended)",
        "image_dd": "DD Mode (Direct copy)",
        "image_option_tooltip": (
            "Standard: Copy files + install bootloader\n"
            "DD: Write ISO directly byte-for-byte to USB"
        ),
        "scheme_label": "Partition Scheme:",
        "scheme_tooltip": (
            "MBR: For older BIOS systems (max 2TB)\n"
            "GPT: For modern UEFI systems (recommended)"
        ),
        "target_label": "Target System:",
        "target_bios": "BIOS (or UEFI-CSM)",
        "target_uefi": "UEFI (non-CSM)",
        "target_both": "BIOS + UEFI",
        "fs_label": "File System:",
        "fs_fat32": "FAT32 (Default)",
        "cluster_label": "Cluster Size:",
        "cluster_default": "Default",
        "vol_label": "Volume Label:",
        "quick_format": "Quick Format",
        "quick_format_tooltip": (
            "Enabled: Write only file system structure (fast)\n"
            "Disabled: Overwrite entire drive (slow, more secure)"
        ),
        "bad_blocks": "Check Bad Blocks (before writing)",
        "bad_blocks_tooltip": (
            "Checks the USB drive for bad sectors before writing.\n"
            "Significantly increases total time."
        ),
        "win_group": "Windows 11 – Bypass Compatibility Checks",
        "win_warning": "Detected: Windows 11 ISO\nThe following bypasses can be enabled:",
        "win_warning_generic": "Windows ISO detected (Win11 detection uncertain)\nBypasses are relevant for Windows 11 – recommended for Win11 ISOs:",
        "win_bypass_tpm": "Bypass TPM 2.0 requirement",
        "win_bypass_secureboot": "Bypass Secure Boot requirement",
        "win_bypass_ram": "Bypass RAM requirement (< 8 GB)",
        "win_remove_online": "Remove online account requirement (allow local account)",
        "step_label": "Step 0 / 0",
        "step_format": "Step %p%",
        "status_ready": "Ready",
        "total_format": "Total %p%",
        "btn_about": "About",
        "btn_cancel": "Cancel",
        "btn_close": "Close",
        "log_group": "Log",
        "no_device": "No USB device found",
        "analyzing_iso": "Analyzing ISO...",
        "analyzing_iso_log": "Analyzing ISO image...",
        "iso_analysis_error": "ISO analysis error: {0}",
        "iso_analysis_failed": "ISO analysis failed",
        "yes": "Yes",
        "no": "No",
        "lbl_bootable": "Bootable",
        "iso_ready": "ISO ready",
        "win11_detected_log": "Windows 11 detected – compatibility bypasses available.",
        "win_detected_log": "Windows ISO detected – Win11 bypasses shown (Win11 not auto-detected).",
        "step_format_dyn": "Step {0} / {1}",
        "status_done": "Done!",
        "log_done": "=== Operation completed successfully ===",
        "status_error": "Error!",
        "status_cancelled": "Cancelled",
        "log_bad_block_start": "=== Starting bad block check ===",
        "log_bad_block": "Bad block: {0}",
        "log_abort_req": "Abort requested...",
        "log_bad_block_aborted": "Bad block check aborted.",
        "log_write_start": "=== Starting write operation ({0} mode) ===",
        "log_device": "Device: {0}",
        "log_iso": "ISO: {0}",
        "log_error": "ERROR: {0}",
        "dlg_no_device_title": "No Device",
        "dlg_no_device_msg": "Please select a USB drive.",
        "dlg_no_iso_title": "No ISO",
        "dlg_no_iso_msg": "Please select an ISO file.",
        "dlg_file_not_found_title": "File not found",
        "dlg_file_not_found_msg": "ISO file not found:\n{0}",
        "dlg_confirm_title": "Confirmation",
        "dlg_confirm_warning": "WARNING: All data on {0} will be PERMANENTLY deleted!\n\nDevice: {0}\n",
        "dlg_confirm_iso": "ISO: {0}\n",
        "dlg_confirm_cont": "\nProceed?",
        "dlg_quit_title": "Quit",
        "dlg_quit_msg": "A write operation is still running!\nReally quit?",
        "dlg_bad_blocks_title": "Bad Blocks Found",
        "dlg_bad_blocks_msg": (
            "{0} bad block(s) found!\n"
            "The USB drive may be defective.\n\n"
            "Continue anyway?"
        ),
        "dlg_cancel_title": "Cancel",
        "dlg_cancel_msg": (
            "Really cancel the write operation?\n\n"
            "The USB drive may become unusable."
        ),
        "dlg_done_title": "Done",
        "dlg_done_msg": (
            "The bootable USB drive was created successfully!\n\n"
            "The USB drive can now be safely removed."
        ),
        "dlg_error_title": "Error",
        "dlg_error_msg": "Error during writing:\n\n{0}",
        "dlg_about_title": "About LinBurn",
        "dlg_about_msg": (
            "<h3>LinBurn for Linux</h3>"
            "<p>An open-source tool for creating bootable USB drives.</p>"
            "<p>Inspired by <a href='https://rufus.ie'>Rufus</a> by Pete Batard.</p>"
            "<br>"
            "<b>Features:</b>"
            "<ul>"
            "<li>ISO Mode (copy files + bootloader)</li>"
            "<li>DD Mode (direct write)</li>"
            "<li>USB format</li>"
            "<li>Bad block check</li>"
            "<li>Windows 11 TPM/SecureBoot bypass</li>"
            "<li>Online account bypass (local account)</li>"
            "</ul>"
            "<p>System requirements: parted, syslinux, grub2, badblocks</p>"
        ),
        "iso_open_title": "Open ISO Image",
        "iso_filter": "Disk Images (*.iso *.img *.bin *.dmg);;All Files (*)",
    },
}
