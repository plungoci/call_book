"""Teste pentru scripturile de instalare și pentru lansatoarele din rădăcina proiectului."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_DIR = Path(__file__).resolve().parent.parent
LAUNCHER_SH = PROJECT_DIR / "Launcher.sh"
INSTALL_SH = PROJECT_DIR / "scripts" / "install.sh"
INSTALL_PS1 = PROJECT_DIR / "scripts" / "install.ps1"

# Scriptul PowerShell este verificat sintactic prin parserul propriu, disponibil
# pe agenții GitHub și pe orice sistem cu pwsh instalat.
POWERSHELL_PARSE_CHECK = (
    "$errors = $null; "
    "$null = [System.Management.Automation.Language.Parser]::ParseFile("
    "'{path}', [ref]$null, [ref]$errors); "
    "if ($errors) {{ $errors | ForEach-Object {{ $_.Message }}; exit 1 }}"
)


def write_fake_python(path: Path, marker: str) -> None:
    """Creează un „python” care raportează doar cine a fost rulat și cu ce argumente."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\necho "{marker} $*"\n', encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def run_launcher(project_dir: Path, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if path_prefix is not None:
        environment["PATH"] = f"{path_prefix}{os.pathsep}{environment['PATH']}"
    return subprocess.run(
        [str(project_dir / "Launcher.sh")],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=30,
    )


@unittest.skipUnless(shutil.which("sh"), "shell POSIX indisponibil")
class LauncherShellTests(unittest.TestCase):
    """Lansatorul trebuie să folosească mediul virtual creat de instalator."""

    def _project(self, directory: str) -> Path:
        project_dir = Path(directory)
        shutil.copy(LAUNCHER_SH, project_dir / "Launcher.sh")
        (project_dir / "Launcher.sh").chmod(0o755)
        (project_dir / "launcher.py").write_text("", encoding="utf-8")
        return project_dir

    def test_launcher_prefers_the_local_virtual_environment(self) -> None:
        with TemporaryDirectory() as directory:
            project_dir = self._project(directory)
            write_fake_python(project_dir / ".venv" / "bin" / "python", "VENV")

            result = run_launcher(project_dir)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("VENV", result.stdout)
            self.assertIn("launcher.py", result.stdout)

    def test_launcher_falls_back_to_the_system_python(self) -> None:
        with TemporaryDirectory() as directory, TemporaryDirectory() as fake_bin:
            project_dir = self._project(directory)
            write_fake_python(Path(fake_bin) / "python3", "SISTEM")

            result = run_launcher(project_dir, path_prefix=Path(fake_bin))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SISTEM", result.stdout)


class InstallScriptTests(unittest.TestCase):
    """Scripturile de instalare nu pot fi rulate în teste, dar pot fi verificate sintactic."""

    @unittest.skipUnless(shutil.which("bash"), "bash indisponibil")
    def test_linux_installer_is_valid_shell(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(INSTALL_SH)], capture_output=True, text=True, check=False, timeout=30
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("sh"), "shell POSIX indisponibil")
    def test_launcher_is_valid_posix_shell(self) -> None:
        result = subprocess.run(["sh", "-n", str(LAUNCHER_SH)], capture_output=True, text=True, check=False, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("pwsh"), "pwsh indisponibil")
    def test_windows_installer_is_valid_powershell(self) -> None:
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", POWERSHELL_PARSE_CHECK.format(path=INSTALL_PS1)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
