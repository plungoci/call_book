"""Pornește aplicația și instalează în siguranță actualizările Git disponibile."""

from __future__ import annotations

import importlib.util
import io
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

GIT_NETWORK_TIMEOUT = 20
GIT_COMMAND_TIMEOUT = 10
# Câte fișiere sunt numite într-un mesaj de eroare înainte de „și încă N”.
MAX_LISTED_PATHS = 3
# Cât din ieșirea brută a lui Git este citată, când nu are o cauză recunoscută.
MAX_ERROR_CHARACTERS = 300
# Modulele fără de care aplicația nu poate porni, câte unul din fiecare pachet
# din requirements.txt.
REQUIRED_MODULES = ("PySide6.QtWidgets", "openpyxl", "curl_cffi")
# Prima instalare descarcă ~100 MB; pe o conexiune lentă durează minute bune.
PIP_TIMEOUT = 1800
INSTALLER_HINT = (
    "Rulează din nou scriptul de instalare (vezi README, „Instalare rapidă”): "
    "creează mediul virtual .venv și instalează tot ce lipsește."
)


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
    """Instalează dependențele în mediul Python care rulează lansatorul.

    Ieșirea lui pip nu este capturată, ca progresul descărcării să fie vizibil.
    """
    print("Instalez dependențele din requirements.txt...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=project_dir,
            check=False,
            timeout=PIP_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Nu am putut instala dependențele.")
        return False
    if result.returncode != 0:
        print("Nu am putut instala dependențele.")
        return False
    print("Dependențele au fost instalate cu succes.")
    return True


def missing_modules() -> list[str]:
    """Returnează modulele necesare aplicației care nu pot fi găsite."""
    missing = []
    for module in REQUIRED_MODULES:
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(module.split(".")[0])
    return missing


def ensure_requirements(project_dir: Path) -> bool:
    """Instalează dependențele lipsă, ca o instalare întreruptă să se repare singură."""
    missing = missing_modules()
    if not missing:
        return True
    print(f"Lipsesc pachetele Python: {', '.join(missing)}.")
    if install_requirements(project_dir) and not missing_modules():
        return True
    print(f"Aplicația nu poate porni fără ele. {INSTALLER_HINT}")
    return False


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


def _format_paths(paths: list[str], limit: int = MAX_LISTED_PATHS) -> str:
    """Enumeră cel mult ``limit`` fișiere, apoi spune câte au mai rămas.

    Un repository ieșit din sincron poate produce zeci de fișiere blocate, iar
    un paragraf cu toate numele nu se citește — primele câteva sunt suficiente
    ca să recunoști despre ce e vorba, iar `git status` le arată pe toate.
    """
    if len(paths) <= limit:
        return ", ".join(paths)
    remaining = len(paths) - limit
    files_word = "fișier" if remaining == 1 else "fișiere"
    return f"{', '.join(paths[:limit])} și încă {remaining} {files_word}"


def _full_list_hint(paths: list[str], limit: int = MAX_LISTED_PATHS) -> str:
    """Trimite la `git status` doar când lista afișată a fost scurtată."""
    return " Lista completă: rulează `git status` în directorul aplicației." if len(paths) > limit else ""


def describe_pull_failure(stderr: str) -> str:
    """Explică de ce a eșuat actualizarea și ce are de făcut utilizatorul.

    Cauza obișnuită nu este un istoric divergent — verificarea fast-forward a
    trecut deja când se ajunge aici — ci fișiere modificate local, pe care Git
    refuză (pe bună dreptate) să le suprascrie. Mesajul spune care sunt.
    """
    paths = _blocked_paths(stderr)
    if paths and "untracked working tree files" in stderr:
        return (
            f"Actualizarea a fost anulată: {_format_paths(paths)} există local, dar nu sunt urmărite de Git, "
            "iar versiunea nouă le conține. Mută-le sau șterge-le, apoi pornește din nou aplicația."
            f"{_full_list_hint(paths)}"
        )
    if paths:
        return (
            f"Actualizarea a fost anulată ca să nu pierzi modificările locale din: {_format_paths(paths)}. "
            "Rulează `git restore .` dacă nu ai nevoie de ele, sau `git stash` ca să le păstrezi deoparte, "
            "apoi pornește din nou aplicația."
            f"{_full_list_hint(paths)}"
        )
    details = " ".join(line for line in stderr.splitlines() if line.strip())
    if details:
        if len(details) > MAX_ERROR_CHARACTERS:
            details = details[:MAX_ERROR_CHARACTERS].rstrip() + "…"
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
        print("Fișierul requirements.txt s-a modificat.")
        install_requirements(project_dir)
    print("Actualizarea a fost instalată cu succes.")
    return True


def describe_crash(returncode: int) -> str:
    """Explică, cât se poate, de ce aplicația s-a oprit cu eroare."""
    message = f"Aplicația s-a oprit cu eroare (cod {returncode}). Detaliile sunt în mesajele de mai sus."
    # Qt termină procesul cu abort() (SIGABRT) când nu își poate încărca
    # pluginul de afișare — pe Linux, aproape mereu o bibliotecă de sistem lipsă.
    if sys.platform.startswith("linux") and returncode in (-6, 134):
        message += (
            " Pe Linux, cauza obișnuită este o bibliotecă de sistem lipsă pentru Qt "
            "(de exemplu libxcb-cursor0); scriptul scripts/install.sh le detectează și le instalează."
        )
    return message


def start_application(project_dir: Path) -> int:
    """Pornește main.py și așteaptă închiderea lui, ca o eroare să rămână vizibilă.

    Lansatorul nu se încheie înaintea aplicației: pe Windows, consola s-ar
    închide odată cu el și ar lua cu ea orice mesaj de eroare.
    """
    main_file = project_dir / "main.py"
    print("Pornesc aplicația...")
    try:
        returncode = subprocess.call([sys.executable, str(main_file)], cwd=project_dir)
    except OSError as error:
        print(f"Nu am putut porni aplicația: {error}")
        return 1
    except KeyboardInterrupt:
        return 130
    if returncode != 0:
        print(describe_crash(returncode))
        # Un proces oprit de un semnal are cod negativ; spre exterior, doar „eșuat”.
        return returncode if returncode > 0 else 1
    return 0


def configure_output(stream: TextIO) -> None:
    """Pregătește ieșirea pentru mesajele lansatorului, cu diacritice cu tot.

    Mesajele trebuie să apară înaintea ieșirii lui pip și a aplicației, chiar
    și când ieșirea e redirecționată. Tot atunci, pe Windows, Python scrie în
    codarea ANSI (cp1252), în care „ă” nu există: primul mesaj ar opri
    lansatorul cu UnicodeEncodeError. Într-o consolă reală nu e cazul.
    """
    if not isinstance(stream, io.TextIOWrapper):
        return
    if stream.isatty():
        stream.reconfigure(line_buffering=True)
    else:
        stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")


def main() -> int:
    """Actualizează opțional, verifică dependențele și pornește aplicația.

    Returnează codul de ieșire al aplicației; Launcher.bat ține fereastra
    deschisă când acesta nu este 0.
    """
    project_dir = Path(__file__).resolve().parent
    configure_output(sys.stdout)
    check_for_updates(project_dir)
    if not ensure_requirements(project_dir):
        return 1
    return start_application(project_dir)


if __name__ == "__main__":
    sys.exit(main())
