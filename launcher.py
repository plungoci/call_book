"""Pornește aplicația și instalează în siguranță actualizările Git disponibile."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

GIT_NETWORK_TIMEOUT = 20
GIT_COMMAND_TIMEOUT = 10


def run_git_command(
    arguments: Sequence[str], project_dir: Path, timeout: int = GIT_COMMAND_TIMEOUT
) -> subprocess.CompletedProcess[str] | None:
    """Execută o comandă Git fără excepții propagate către lansator."""
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def is_git_repository(project_dir: Path) -> bool:
    """Returnează dacă directorul este rădăcina sau un subdirector al unui repository Git."""
    result = run_git_command(["rev-parse", "--is-inside-work-tree"], project_dir)
    return result is not None and result.returncode == 0 and result.stdout.strip() == "true"


def get_current_branch(project_dir: Path) -> str | None:
    """Obține numele ramurii locale curente, sau ``None`` pentru HEAD detașat."""
    result = run_git_command(["symbolic-ref", "--quiet", "--short", "HEAD"], project_dir)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def get_current_commit(project_dir: Path) -> str | None:
    """Obține identificatorul commitului local HEAD."""
    result = run_git_command(["rev-parse", "HEAD"], project_dir)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def get_remote_commit(project_dir: Path, branch: str) -> str | None:
    """Obține identificatorul commitului urmărit pe ``origin/<branch>``."""
    result = run_git_command(["rev-parse", f"origin/{branch}"], project_dir)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def requirements_changed(project_dir: Path, old_commit: str, new_commit: str) -> bool:
    """Returnează dacă requirements.txt diferă între cele două commituri."""
    result = run_git_command(["diff", "--quiet", old_commit, new_commit, "--", "requirements.txt"], project_dir)
    return result is not None and result.returncode == 1


def install_requirements(project_dir: Path) -> bool:
    """Instalează dependențele în mediul Python care rulează lansatorul."""
    print("Fișierul requirements.txt s-a modificat. Actualizez dependențele...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Nu am putut instala dependențele. Pornesc versiunea locală.")
        return False
    if result.returncode != 0:
        print("Nu am putut instala dependențele. Pornesc versiunea locală.")
        return False
    print("Dependențele au fost actualizate cu succes.")
    return True


def _remote_is_newer(project_dir: Path, local_commit: str, remote_commit: str) -> bool:
    """Verifică dacă HEAD poate avansa fast-forward la commitul remote."""
    result = run_git_command(["merge-base", "--is-ancestor", local_commit, remote_commit], project_dir)
    return result is not None and result.returncode == 0


def _blocked_paths(stderr: str) -> list[str]:
    """Extrage fișierele enumerate de Git sub un mesaj „would be overwritten”.

    Git le listează pe câte un rând indentat cu tab, după linia de eroare.
    """
    paths = []
    listing = False
    for line in stderr.splitlines():
        if "would be overwritten" in line:
            listing = True
            continue
        if listing:
            if line.startswith(("\t", "    ")) and line.strip():
                paths.append(line.strip())
            elif line.strip():
                break
    return paths


def describe_pull_failure(stderr: str) -> str:
    """Explică de ce a eșuat actualizarea și ce are de făcut utilizatorul.

    Cauza obișnuită nu este un istoric divergent — verificarea fast-forward a
    trecut deja când se ajunge aici — ci fișiere modificate local, pe care Git
    refuză (pe bună dreptate) să le suprascrie. Mesajul spune care sunt.
    """
    paths = _blocked_paths(stderr)
    if paths and "untracked working tree files" in stderr:
        listed = ", ".join(paths)
        return (
            f"Actualizarea a fost anulată: fișierele {listed} există local, dar nu sunt urmărite de Git, "
            "iar versiunea nouă le conține. Mută-le sau șterge-le, apoi pornește din nou aplicația."
        )
    if paths:
        listed = ", ".join(paths)
        return (
            f"Actualizarea a fost anulată ca să nu pierzi modificările locale din: {listed}. "
            "Rulează `git restore .` dacă nu ai nevoie de ele, sau `git stash` ca să le păstrezi deoparte, "
            "apoi pornește din nou aplicația."
        )
    details = " ".join(line for line in stderr.splitlines() if line.strip())
    if details:
        return f"Actualizarea a fost anulată. Git a raportat: {details}"
    return "Actualizarea a fost anulată, fără un motiv raportat de Git."


def describe_divergence(project_dir: Path, local_commit: str, remote_commit: str) -> str:
    """Spune de ce ramura locală nu poate avansa fast-forward la cea remote."""
    result = run_git_command(["merge-base", "--is-ancestor", remote_commit, local_commit], project_dir)
    if result is not None and result.returncode == 0:
        return (
            "Ai commituri locale care nu există pe origin, deci versiunea locală este mai nouă. "
            "Actualizarea a fost anulată."
        )
    return (
        "Istoricul local și cel de pe origin au divergat (ramura remote a fost rescrisă, "
        "sau ai commituri proprii). Actualizarea a fost anulată."
    )


def check_for_updates(project_dir: Path) -> bool:
    """Verifică și aplică doar actualizările Git care pot fi fast-forward.

    Orice problemă este raportată, dar nu împiedică lansarea versiunii locale.
    """
    print("Verific actualizările...")
    if shutil.which("git") is None:
        print("Git nu este instalat. Pornesc versiunea locală.")
        return False
    if not is_git_repository(project_dir):
        print("Directorul nu este un repository Git. Pornesc versiunea locală.")
        return False

    fetch_result = run_git_command(["fetch", "origin"], project_dir, GIT_NETWORK_TIMEOUT)
    if fetch_result is None or fetch_result.returncode != 0:
        print("Nu am putut verifica actualizările. Pornesc versiunea locală.")
        return False

    branch = get_current_branch(project_dir)
    local_commit = get_current_commit(project_dir)
    if branch is None or local_commit is None:
        print("Nu am putut determina ramura curentă. Pornesc versiunea locală.")
        return False
    remote_commit = get_remote_commit(project_dir, branch)
    if remote_commit is None:
        print("Ramura remote corespunzătoare nu există. Pornesc versiunea locală.")
        return False
    if local_commit == remote_commit:
        print("Aplicația este deja actualizată.")
        return False
    if not _remote_is_newer(project_dir, local_commit, remote_commit):
        print(describe_divergence(project_dir, local_commit, remote_commit))
        return False

    print("A fost găsită o versiune nouă.")
    pull_result = run_git_command(["pull", "--ff-only", "origin", branch], project_dir, GIT_NETWORK_TIMEOUT)
    if pull_result is None:
        print("Comanda Git de actualizare nu a putut fi rulată sau a expirat. Pornesc versiunea locală.")
        return False
    if pull_result.returncode != 0:
        print(describe_pull_failure(pull_result.stderr))
        return False

    new_commit = get_current_commit(project_dir)
    if new_commit is None:
        print("Actualizarea a reușit, dar nu am putut verifica noul commit.")
        return True
    if requirements_changed(project_dir, local_commit, new_commit):
        install_requirements(project_dir)
    print("Actualizarea a fost instalată cu succes.")
    return True


def start_application(project_dir: Path) -> None:
    """Pornește main.py separat, astfel încât lansatorul se poate încheia imediat."""
    main_file = project_dir / "main.py"
    print("Pornesc aplicația...")
    try:
        subprocess.Popen([sys.executable, str(main_file)], cwd=project_dir)
    except OSError as error:
        print(f"Nu am putut porni aplicația: {error}")


def main() -> None:
    """Determină directorul proiectului, actualizează opțional și pornește aplicația."""
    project_dir = Path(__file__).resolve().parent
    check_for_updates(project_dir)
    start_application(project_dir)


if __name__ == "__main__":
    main()
