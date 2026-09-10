"""Teste unitare pentru actualizatorul lansatorului."""

from __future__ import annotations

import subprocess
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import launcher


def completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Construiește un rezultat subprocess succint pentru mock-uri."""
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr=stderr)


# Ieșirea reală a lui `git pull --ff-only`, verificată contra unui Git adevărat.
LOCAL_CHANGES_STDERR = """From https://github.com/plungoci/call_book
 * branch            main       -> FETCH_HEAD
error: Your local changes to the following files would be overwritten by merge:
\talt.txt
\tfisier.txt
Please commit your changes or stash them before you merge.
Aborting
"""
UNTRACKED_STDERR = """From https://github.com/plungoci/call_book
 * branch            main       -> FETCH_HEAD
error: The following untracked working tree files would be overwritten by merge:
\tnou.txt
Please move or remove them before you merge.
Aborting
"""


class PullFailureMessageTests(TestCase):
    """Mesajul trebuie să spună cauza reală, nu una generică.

    Când se ajunge la `git pull`, verificarea fast-forward a trecut deja —
    deci „istoric divergent” este exact explicația greșită.
    """

    def test_local_changes_are_named_with_the_way_out(self) -> None:
        message = launcher.describe_pull_failure(LOCAL_CHANGES_STDERR)
        self.assertIn("alt.txt", message)
        self.assertIn("fisier.txt", message)
        self.assertIn("git stash", message)
        self.assertNotIn("divergent", message)

    def test_untracked_files_get_their_own_explanation(self) -> None:
        message = launcher.describe_pull_failure(UNTRACKED_STDERR)
        self.assertIn("nou.txt", message)
        self.assertIn("nu sunt urmărite", message)

    def test_any_other_git_error_is_passed_through_verbatim(self) -> None:
        message = launcher.describe_pull_failure("fatal: Could not resolve host: github.com")
        self.assertIn("Could not resolve host: github.com", message)

    def test_a_silent_failure_still_produces_a_message(self) -> None:
        self.assertTrue(launcher.describe_pull_failure(""))

    def test_the_file_list_stops_at_gits_closing_line(self) -> None:
        # "Please commit your changes..." must not be read as a file name.
        self.assertEqual(launcher._blocked_paths(LOCAL_CHANGES_STDERR), ["alt.txt", "fisier.txt"])


class DivergenceMessageTests(TestCase):
    def setUp(self) -> None:
        self.project_dir = Path("/temporary/project")

    @patch("launcher.run_git_command", return_value=completed(0))
    def test_local_commits_ahead_of_origin_are_named_as_such(self, _: MagicMock) -> None:
        message = launcher.describe_divergence(self.project_dir, "local", "remote")
        self.assertIn("commituri locale", message)

    @patch("launcher.run_git_command", return_value=completed(1))
    def test_a_real_divergence_says_so(self, _: MagicMock) -> None:
        message = launcher.describe_divergence(self.project_dir, "local", "remote")
        self.assertIn("divergat", message)

    @patch("launcher.run_git_command", return_value=None)
    def test_an_unavailable_git_still_yields_a_message(self, _: MagicMock) -> None:
        self.assertTrue(launcher.describe_divergence(self.project_dir, "local", "remote"))


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
    def test_update_pulls_and_installs_changed_requirements(
        self,
        run_git: MagicMock,
        _which: MagicMock,
        _is_git_repository: MagicMock,
        _remote_is_newer: MagicMock,
        _current_branch: MagicMock,
        _remote_commit: MagicMock,
        _current_commit: MagicMock,
        _requirements_changed: MagicMock,
        install_requirements: MagicMock,
    ) -> None:
        self.assertTrue(launcher.check_for_updates(self.project_dir))
        self.assertEqual(run_git.call_args_list[1].args[0], ["pull", "--ff-only", "origin", "work"])
        install_requirements.assert_called_once_with(self.project_dir)

    @patch("launcher.get_current_commit", return_value="old")
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), completed(1)])
    def test_pull_failure_does_not_update(self, *_: MagicMock) -> None:
        self.assertFalse(launcher.check_for_updates(self.project_dir))

    @patch("launcher.get_current_commit", return_value="old")
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), completed(1, stderr=LOCAL_CHANGES_STDERR)])
    def test_a_blocked_pull_reports_the_files_that_blocked_it(self, *_: MagicMock) -> None:
        with redirect_stdout(StringIO()) as output:
            self.assertFalse(launcher.check_for_updates(self.project_dir))
        printed = output.getvalue()
        self.assertIn("fisier.txt", printed)
        self.assertNotIn("divergent", printed)

    @patch("launcher.get_current_commit", return_value="old")
    @patch("launcher.get_remote_commit", return_value="new")
    @patch("launcher.get_current_branch", return_value="work")
    @patch("launcher._remote_is_newer", return_value=True)
    @patch("launcher.is_git_repository", return_value=True)
    @patch("launcher.shutil.which", return_value="/usr/bin/git")
    @patch("launcher.run_git_command", side_effect=[completed(), None])
    def test_a_timed_out_pull_is_reported_as_such(self, *_: MagicMock) -> None:
        with redirect_stdout(StringIO()) as output:
            self.assertFalse(launcher.check_for_updates(self.project_dir))
        self.assertIn("expirat", output.getvalue())

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
    def test_main_starts_application_when_update_fails(self, _: MagicMock, start: MagicMock) -> None:
        launcher.main()
        start.assert_called_once_with(Path(launcher.__file__).resolve().parent)
