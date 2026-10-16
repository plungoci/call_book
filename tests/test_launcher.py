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


def blocked_stderr(paths: list[str], untracked: bool = False) -> str:
    """Construiește ieșirea lui Git pentru un set dat de fișiere blocate."""
    header = (
        "error: The following untracked working tree files would be overwritten by merge:"
        if untracked
        else "error: Your local changes to the following files would be overwritten by merge:"
    )
    listing = "".join(f"\t{path}\n" for path in paths)
    return f"{header}\n{listing}Please move or remove them before you merge.\nAborting\n"


class LongMessageTests(TestCase):
    """Un repository ieșit din sincron poate bloca zeci de fișiere deodată.

    Mesajul trebuie să rămână citibil: câteva nume, apoi câte au mai rămas.
    """

    def test_a_short_list_is_shown_in_full(self) -> None:
        paths = [f"f{index}.py" for index in range(launcher.MAX_LISTED_PATHS)]
        message = launcher.describe_pull_failure(blocked_stderr(paths))
        for path in paths:
            self.assertIn(path, message)
        self.assertNotIn("și încă", message)
        self.assertNotIn("git status", message)

    def test_a_long_list_is_cut_and_the_rest_counted(self) -> None:
        paths = [f"f{index}.py" for index in range(16)]
        message = launcher.describe_pull_failure(blocked_stderr(paths))
        self.assertIn("f0.py", message)
        self.assertIn(f"și încă {16 - launcher.MAX_LISTED_PATHS} fișiere", message)
        self.assertNotIn("f15.py", message)

    def test_one_remaining_file_is_written_in_the_singular(self) -> None:
        paths = [f"f{index}.py" for index in range(launcher.MAX_LISTED_PATHS + 1)]
        message = launcher.describe_pull_failure(blocked_stderr(paths))
        self.assertIn("și încă 1 fișier.", message + ".")
        self.assertNotIn("1 fișiere", message)

    def test_the_full_list_hint_appears_only_when_the_list_was_cut(self) -> None:
        many = launcher.describe_pull_failure(blocked_stderr([f"f{i}.py" for i in range(9)], untracked=True))
        self.assertIn("git status", many)
        few = launcher.describe_pull_failure(blocked_stderr(["f0.py"], untracked=True))
        self.assertNotIn("git status", few)

    def test_the_message_stays_short_enough_to_read(self) -> None:
        # The reported case: 16 blocked files in a single printed paragraph.
        paths = [f"call_book/ui/modul_cu_nume_lung_{index}.py" for index in range(16)]
        self.assertLess(len(launcher.describe_pull_failure(blocked_stderr(paths, untracked=True))), 400)

    def test_an_unrecognised_git_error_is_quoted_but_not_endlessly(self) -> None:
        message = launcher.describe_pull_failure("fatal: " + "x" * 2000)
        self.assertLess(len(message), launcher.MAX_ERROR_CHARACTERS + 100)
        self.assertTrue(message.endswith("…"))

    def test_a_short_error_is_quoted_whole(self) -> None:
        message = launcher.describe_pull_failure("fatal: Could not resolve host: github.com")
        self.assertIn("Could not resolve host: github.com", message)
        self.assertFalse(message.endswith("…"))


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

    @patch("launcher.start_application", return_value=0)
    @patch("launcher.ensure_requirements", return_value=True)
    @patch("launcher.check_for_updates", return_value=False)
    def test_main_starts_application_when_update_fails(self, _: MagicMock, __: MagicMock, start: MagicMock) -> None:
        self.assertEqual(launcher.main(), 0)
        start.assert_called_once_with(Path(launcher.__file__).resolve().parent)

    @patch("launcher.start_application")
    @patch("launcher.ensure_requirements", return_value=False)
    @patch("launcher.check_for_updates", return_value=False)
    def test_main_does_not_start_without_dependencies(self, _: MagicMock, __: MagicMock, start: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(launcher.main(), 1)
        start.assert_not_called()


class DependencyTests(TestCase):
    """O instalare întreruptă trebuie să se repare la următoarea pornire."""

    def setUp(self) -> None:
        self.project_dir = Path("/temporary/project")

    @patch("launcher.importlib.util.find_spec", return_value=object())
    def test_no_missing_modules_when_everything_is_installed(self, _: MagicMock) -> None:
        self.assertEqual(launcher.missing_modules(), [])

    @patch("launcher.importlib.util.find_spec", side_effect=ModuleNotFoundError("PySide6"))
    def test_a_missing_parent_package_counts_as_missing(self, _: MagicMock) -> None:
        self.assertEqual(launcher.missing_modules(), ["PySide6", "openpyxl", "curl_cffi"])

    @patch("launcher.install_requirements")
    @patch("launcher.missing_modules", return_value=[])
    def test_installed_dependencies_skip_pip(self, _: MagicMock, install: MagicMock) -> None:
        self.assertTrue(launcher.ensure_requirements(self.project_dir))
        install.assert_not_called()

    @patch("launcher.install_requirements", return_value=True)
    @patch("launcher.missing_modules", side_effect=[["openpyxl"], []])
    def test_missing_dependencies_are_installed(self, _: MagicMock, install: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertTrue(launcher.ensure_requirements(self.project_dir))
        install.assert_called_once_with(self.project_dir)

    @patch("launcher.install_requirements", return_value=False)
    @patch("launcher.missing_modules", return_value=["openpyxl"])
    def test_failed_install_points_to_the_installer(self, _: MagicMock, __: MagicMock) -> None:
        with redirect_stdout(StringIO()) as output:
            self.assertFalse(launcher.ensure_requirements(self.project_dir))
        self.assertIn("scriptul de instalare", output.getvalue())

    @patch("launcher.subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 1))
    def test_a_pip_timeout_is_reported_as_failure(self, _: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertFalse(launcher.install_requirements(self.project_dir))


class StartApplicationTests(TestCase):
    """Lansatorul așteaptă aplicația, ca o eroare de pornire să rămână vizibilă."""

    def setUp(self) -> None:
        self.project_dir = Path("/temporary/project")

    @patch("launcher.subprocess.call", return_value=0)
    def test_waits_for_the_application_with_the_same_python(self, call: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(launcher.start_application(self.project_dir), 0)
        self.assertEqual(call.call_args.args[0], [launcher.sys.executable, str(self.project_dir / "main.py")])
        self.assertEqual(call.call_args.kwargs["cwd"], self.project_dir)

    @patch("launcher.subprocess.call", return_value=3)
    def test_a_crash_is_reported_with_its_exit_code(self, _: MagicMock) -> None:
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(launcher.start_application(self.project_dir), 3)
        self.assertIn("cod 3", output.getvalue())

    @patch("launcher.subprocess.call", return_value=-6)
    def test_a_signal_becomes_a_plain_failure_code(self, _: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(launcher.start_application(self.project_dir), 1)

    @patch("launcher.sys.platform", "linux")
    def test_a_qt_abort_on_linux_mentions_the_system_libraries(self) -> None:
        self.assertIn("libxcb-cursor0", launcher.describe_crash(-6))

    @patch("launcher.sys.platform", "win32")
    def test_other_crashes_do_not_blame_linux_libraries(self) -> None:
        self.assertNotIn("libxcb", launcher.describe_crash(1))

    @patch("launcher.subprocess.call", side_effect=OSError("lipsă"))
    def test_an_unstartable_application_is_a_failure(self, _: MagicMock) -> None:
        with redirect_stdout(StringIO()):
            self.assertEqual(launcher.start_application(self.project_dir), 1)
