"""
Windows 11 compatibility patches for USB installations.
Bypasses TPM 2.0, Secure Boot, RAM requirements and removes
mandatory online account (Microsoft Account) requirement.
"""
import os
import shutil
import subprocess
import tempfile
import textwrap


class WindowsPatcher:
    """
    Applies patches to Windows installation media on a mounted USB drive.
    These patches allow installing Windows 11 on hardware that does not
    meet Microsoft's minimum requirements (no TPM 2.0, no Secure Boot, < 8 GB RAM).
    """

    @classmethod
    def apply(
        cls,
        usb_mount: str,
        bypass_tpm: bool = True,
        bypass_secureboot: bool = True,
        bypass_ram: bool = True,
        remove_online_requirement: bool = True,
        log_callback=None,
    ):
        def log(msg):
            if log_callback:
                log_callback(msg)

        if bypass_tpm or bypass_secureboot or bypass_ram:
            log("Wende TPM/SecureBoot/RAM-Bypass an...")
            cls._patch_appraiserres(usb_mount, log)
            cls._patch_boot_wim(usb_mount, log)   # patch inside boot.wim (WinPE)
            cls._add_registry_bypass(usb_mount, bypass_tpm, bypass_secureboot, bypass_ram, log)

        # autounattend.xml is needed whenever any bypass or online removal is active.
        # The windowsPE RunSynchronous registry commands live inside this file, so it
        # must be created even if remove_online_requirement is False.
        if bypass_tpm or bypass_secureboot or bypass_ram or remove_online_requirement:
            if remove_online_requirement:
                log("Entferne Online-Konto-Pflicht...")
            cls._add_autounattend(
                usb_mount,
                bypass_tpm=bypass_tpm,
                bypass_secureboot=bypass_secureboot,
                bypass_ram=bypass_ram,
                remove_online=remove_online_requirement,
                log=log,
            )

        log("Windows-Patches erfolgreich angewendet.")

    @classmethod
    def _patch_boot_wim(cls, usb_mount: str, log):
        """
        Patch appraiserres.dll inside sources/boot.wim (image index 2 = Windows Setup).
        This DLL runs inside WinPE and causes the restart loop when TPM 2.0 is missing.
        Uses wimlib-imagex to replace it with an empty stub without mounting the WIM.
        """
        boot_wim = os.path.join(usb_mount, "sources", "boot.wim")
        if not os.path.exists(boot_wim):
            log("Warnung: boot.wim nicht gefunden, überspringe WinPE-Patch.")
            return

        # Create a temporary empty file to use as the stub DLL
        tmp_empty = tempfile.NamedTemporaryFile(delete=False, suffix=".dll")
        tmp_empty.close()

        try:
            # wimlib-imagex update replaces a file inside the WIM directly (no mount needed)
            result = subprocess.run(
                [
                    "wimlib-imagex", "update", boot_wim, "2",
                    "--command", f"add {tmp_empty.name} /Windows/System32/appraiserres.dll",
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                log("boot.wim gepatcht: appraiserres.dll in WinPE deaktiviert (kein TPM-Bootloop mehr).")
            else:
                log(f"Warnung: boot.wim-Patch fehlgeschlagen: {result.stderr.strip()[:200]}")
        except FileNotFoundError:
            log("Warnung: wimlib-imagex nicht gefunden — boot.wim nicht gepatcht. 'sudo apt install wimtools'")
        except subprocess.TimeoutExpired:
            log("Warnung: boot.wim-Patch Timeout.")
        finally:
            os.unlink(tmp_empty.name)

    @classmethod
    def _patch_appraiserres(cls, usb_mount: str, log):
        """
        Replace sources/appraiserres.dll with an empty file.
        This DLL performs hardware compatibility checks during setup.
        Replacing it with an empty file disables all hardware requirement checks.
        """
        dll_path = os.path.join(usb_mount, "sources", "appraiserres.dll")
        if os.path.exists(dll_path):
            # Back up original
            backup = dll_path + ".bak"
            if not os.path.exists(backup):
                shutil.copy2(dll_path, backup)
            # Replace with empty file (setup will skip the check)
            with open(dll_path, "wb") as f:
                f.write(b"")
            log("appraiserres.dll ersetzt (TPM/SecureBoot-Checks deaktiviert).")
        else:
            log("Warnung: appraiserres.dll nicht gefunden, überspringe.")

    @classmethod
    def _add_registry_bypass(
        cls,
        usb_mount: str,
        bypass_tpm: bool,
        bypass_secureboot: bool,
        bypass_ram: bool,
        log,
    ):
        """
        Add a SetupComplete.cmd script that writes registry bypass keys.
        These keys tell Windows Setup to skip hardware requirement checks.
        Location: $OEM$$/$$/Setup/Scripts/SetupComplete.cmd
        """
        scripts_dir = os.path.join(
            usb_mount, "$OEM$", "$$$", "Setup", "Scripts"
        )
        os.makedirs(scripts_dir, exist_ok=True)

        cmd_path = os.path.join(scripts_dir, "SetupComplete.cmd")
        lines = ["@echo off", ""]

        reg_base = r"HKLM\SYSTEM\Setup\LabConfig"
        if bypass_tpm:
            lines.append(
                f'reg add "{reg_base}" /v BypassTPMCheck /t REG_DWORD /d 1 /f'
            )
        if bypass_secureboot:
            lines.append(
                f'reg add "{reg_base}" /v BypassSecureBootCheck /t REG_DWORD /d 1 /f'
            )
        if bypass_ram:
            lines.append(
                f'reg add "{reg_base}" /v BypassRAMCheck /t REG_DWORD /d 1 /f'
            )

        lines += ["", "exit /b 0"]

        with open(cmd_path, "w", newline="\r\n") as f:
            f.write("\n".join(lines))

        log(f"Registry-Bypass-Skript erstellt: {cmd_path}")

        # Also add a registry patch via SETUPREG.HIV approach
        # This applies before the OS is installed via winpe
        cls._add_winpe_registry_patch(usb_mount, bypass_tpm, bypass_secureboot, bypass_ram, log)

    @classmethod
    def _add_winpe_registry_patch(
        cls,
        usb_mount: str,
        bypass_tpm: bool,
        bypass_secureboot: bool,
        bypass_ram: bool,
        log,
    ):
        """
        Create a registry file that will be merged during WinPE startup.
        Uses autounattend.xml RunSynchronous commands.
        """
        # This is handled via autounattend.xml below; no separate file needed here.
        pass

    @classmethod
    def _add_autounattend(
        cls,
        usb_mount: str,
        bypass_tpm: bool = True,
        bypass_secureboot: bool = True,
        bypass_ram: bool = True,
        remove_online: bool = True,
        log=None,
    ):
        """
        Create autounattend.xml that applies registry bypasses during WinPE
        and optionally skips the Microsoft Account requirement during OOBE.

        IMPORTANT: xmlns:wcm must be declared on <unattend> (and repeated on
        each component) so that wcm:action="add" attributes are valid XML.
        A missing namespace declaration causes Windows Setup to fail parsing
        the file → setup crashes → machine reboots → boot loop.
        """
        xml_path = os.path.join(usb_mount, "autounattend.xml")

        if os.path.exists(xml_path):
            log("autounattend.xml bereits vorhanden, überspringe.")
            return

        # Build RunSynchronous block — include only the requested bypass keys,
        # plus storage/CPU which are always safe to bypass on older hardware.
        bypass_keys = []
        if bypass_tpm:
            bypass_keys.append(("BypassTPMCheck",        "TPM-Check umgehen"))
        if bypass_secureboot:
            bypass_keys.append(("BypassSecureBootCheck", "SecureBoot-Check umgehen"))
        if bypass_ram:
            bypass_keys.append(("BypassRAMCheck",        "RAM-Check umgehen"))
        # Storage and CPU checks are always bypassed alongside the others
        bypass_keys.append(("BypassStorageCheck", "Storage-Check umgehen"))
        bypass_keys.append(("BypassCPUCheck",     "CPU-Check umgehen"))
        run_cmds = []
        for i, (reg_val, desc) in enumerate(bypass_keys, start=1):
            run_cmds.append(
                f'        <RunSynchronousCommand wcm:action="add">\n'
                f'          <Order>{i}</Order>\n'
                f'          <Description>{desc}</Description>\n'
                f'          <Path>cmd /c reg add &quot;HKLM\\SYSTEM\\Setup\\LabConfig&quot;'
                f' /v {reg_val} /t REG_DWORD /d 1 /f</Path>\n'
                f'          <WillReboot>Never</WillReboot>\n'
                f'        </RunSynchronousCommand>'
            )
        run_sync_xml = "\n".join(run_cmds)

        # OOBE section — only included when remove_online is True.
        # We do NOT pre-create a local account here; Windows 11 24H2 handles
        # that during OOBE itself.  We only suppress the online-account screens.
        oobe_section = ""
        if remove_online:
            oobe_section = textwrap.dedent("""\

              <!-- Pass 7: oobeSystem - Online-Konto-Pflicht entfernen -->
              <settings pass="oobeSystem">
                <component name="Microsoft-Windows-Shell-Setup"
                           processorArchitecture="amd64"
                           publicKeyToken="31bf3856ad364e35"
                           language="neutral"
                           versionScope="nonSxS"
                           xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">
                  <OOBE>
                    <HideEULAPage>true</HideEULAPage>
                    <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
                    <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
                    <ProtectYourPC>3</ProtectYourPC>
                  </OOBE>
                </component>
              </settings>""")

        xml_content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<unattend xmlns="urn:schemas-microsoft-com:unattend"\n'
            '          xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">\n'
            '\n'
            '  <!-- Pass 1: windowsPE - Hardware-Anforderungs-Bypass -->\n'
            '  <settings pass="windowsPE">\n'
            '    <component name="Microsoft-Windows-Setup"\n'
            '               processorArchitecture="amd64"\n'
            '               publicKeyToken="31bf3856ad364e35"\n'
            '               language="neutral"\n'
            '               versionScope="nonSxS"\n'
            '               xmlns:wcm="http://schemas.microsoft.com/WMIConfig/2002/State">\n'
            '      <RunSynchronous>\n'
            + run_sync_xml + '\n'
            '      </RunSynchronous>\n'
            '      <UserData>\n'
            '        <AcceptEula>true</AcceptEula>\n'
            '      </UserData>\n'
            '    </component>\n'
            '  </settings>\n'
            + oobe_section + '\n'
            '\n'
            '</unattend>\n'
        )

        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        log("autounattend.xml erstellt (xmlns:wcm korrekt deklariert, Hardware-Bypass aktiv).")
