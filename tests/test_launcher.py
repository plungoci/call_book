"""Teste unitare pentru actualizatorul lansatorului."""
from __future__ import annotations

from pathlib import Path
import subprocess
from unittest import TestCase
from unittest.mock import MagicMock, patch

import launcher


def completed(returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
    """Construiește un rezultat subprocess succint pentru mock-uri."""
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


class LauncherTests(TestCase):
    """Păstrează testele complet izolate de Git, rețea și PySide6."""

    def setUp(self) -> None:
        self.project_dir = Path("/temporary/project")

    @patch("launcher.shutil.which", return_value=None)
    def test_git_not_installed(self, _: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.is_git_repository", return_value=False)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    def test_not_a_git_repository(self, _: MagicMock, __: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", return_value=completed(1))
    def test_fetch_failure(self, _: MagicMock, __: MagicMock, ___: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.get_remote_commit", return_value="same")
    @patch("launcher.get_current_commit", return_value="same")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", return_value=completed())
    def test_already_up_to_date(self, *_: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.install_requirements")
    @patch("launcher.requirements_changed", return_value=True)
    @patch("launcher.get_current_commit", side_effect=["old", "new"])
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), completed()])
    def test_update_pulls_and_installs_changed_requirements(self, run_git: MagicMock, *_: MagicMock) -> None:
        self.assertTrue(launcher.check_for_updates(self.project_dir))
        self.assertEqual(run_git.call_args_list[1].args[0], ["pull", "--ff-only", "origin", "work"])
        launcher.install_requirements.assert_called_once_with(self.project_dir)

    @patch("launcher.get_current_commit", return_value="old")
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), completed(1)])
    def test_pull_failure_does_not_update(self, *_: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.install_requirements")
    @patch("launcher.requirements_changed", return_value=False)
    @patch("launcher.get_current_commit", side_effect=["old", "new"])
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), completed()])
    def test_unchanged_requirements_do_not_run_pip(
        self,
        _: MagicMock,
        __: MagicMock,
        ___: MagicMock,
        ____: MagicMock,
        _____: MagicMock,
        ______: MagicMock,
        _______: MagicMock,
        ________: MagicMock,
        install: MagicMock,
    ) -> None:
        self.assertTrue(launcher.check_for_updates(self.project_dir))
        install.assert_not_called()

    @patch("launcher.subprocess.run", return_value=completed())
    def test_changed_requirements_runs_pip_with_current_python(self, run: MagicMock) -> None:
        self.assertTrue(launcher.install_requirements(self.project_dir))
        self.assertEqual(run.call_args.args[0][:3], [launcher.sys.executable, "-m", "pip"])

    @patch("launcher.start_application")
    @patch("launcher.check_for_updates", return_value=False)
    def test_main_starts_application_when_update_fails(
        self, _: MagicMock, start: MagicMock
    ) -> None:
        launcher.main()
        start.assert_called_once_with(Path(launcher.__file__).resolve().parent)
