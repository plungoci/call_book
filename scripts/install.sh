#!/usr/bin/env bash
# Instalează și pornește Radio Logbook pe un calculator Linux sau macOS nou.
#
# Verifică Git și Python 3.11+ (plus bibliotecile de sistem Qt pe Linux), clonează
# proiectul, creează mediul virtual .venv, instalează dependențele și pornește
# aplicația. Rularea din nou actualizează o instalare existentă în loc să o dubleze.
#
#   curl -fsSL https://raw.githubusercontent.com/plungoci/call_book/main/scripts/install.sh | bash
#
# Se poate configura prin variabile de mediu: CALL_BOOK_HOME (directorul de
# instalare), CALL_BOOK_BRANCH (ramura) și CALL_BOOK_NO_START=1 (nu porni la final).

set -euo pipefail

REPOSITORY_URL="https://github.com/plungoci/call_book.git"
INSTALL_PATH="${CALL_BOOK_HOME:-$HOME/call_book}"
BRANCH="${CALL_BOOK_BRANCH:-main}"
# Bibliotecile de sistem de care are nevoie Qt; roțile PySide6 nu le includ.
QT_PACKAGES="libegl1 libgl1 libopengl0 libxkbcommon0 libdbus-1-3"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nEroare: %s\n' "$1" >&2; exit 1; }

python_is_recent() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

find_python() {
    for candidate in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && python_is_recent "$candidate"; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

# sudo își citește parola direct de la terminal, deci funcționează și când
# scriptul însuși vine pe stdin prin `curl ... | bash`.
as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        return 1
    fi
}

install_system_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        step "Instalez pachetele de sistem lipsă ($*)..."
        # shellcheck disable=SC2086
        as_root apt-get update -qq && as_root apt-get install -y $* || return 1
        return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
        step "Instalez pachetele de sistem lipsă ($*)..."
        # shellcheck disable=SC2086
        as_root dnf install -y $* || return 1
        return 0
    fi
    if command -v brew >/dev/null 2>&1; then
        step "Instalez pachetele de sistem lipsă ($*)..."
        # shellcheck disable=SC2086
        brew install $* || return 1
        return 0
    fi
    return 1
}

step "Verific Git..."
if ! command -v git >/dev/null 2>&1; then
    install_system_packages git || fail "Git lipsește și nu l-am putut instala automat. Instalează-l manual și rulează scriptul din nou."
fi
command -v git >/dev/null 2>&1 || fail "Git tot nu este disponibil."

step "Verific Python 3.11 sau mai nou..."
if ! PYTHON="$(find_python)"; then
    if [ "$(uname -s)" = "Darwin" ]; then
        install_system_packages python@3.12 || fail "Python 3.11+ lipsește. Instalează-l de pe https://www.python.org/downloads/ și rulează scriptul din nou."
    else
        # python3-venv este separat pe Debian/Ubuntu, iar `python3 -m venv` eșuează fără el.
        install_system_packages python3 python3-venv python3-pip || fail "Python 3.11+ lipsește. Instalează-l manual și rulează scriptul din nou."
    fi
    PYTHON="$(find_python)" || fail "Python 3.11+ tot nu este disponibil."
fi
printf 'Folosesc %s (%s)\n' "$PYTHON" "$("$PYTHON" -c 'import platform; print(platform.python_version())')"

if [ "$(uname -s)" = "Linux" ]; then
    step "Verific bibliotecile de sistem Qt..."
    if command -v ldconfig >/dev/null 2>&1 && ! ldconfig -p | grep -q 'libEGL\.so\.1'; then
        # shellcheck disable=SC2086
        install_system_packages $QT_PACKAGES ||
            printf 'Atenție: instalează manual %s dacă aplicația nu pornește.\n' "$QT_PACKAGES"
    fi
fi

if [ -d "$INSTALL_PATH/.git" ]; then
    step "Actualizez instalarea existentă din $INSTALL_PATH..."
    git -C "$INSTALL_PATH" fetch origin
    git -C "$INSTALL_PATH" pull --ff-only
else
    if [ -e "$INSTALL_PATH" ] && [ -n "$(ls -A "$INSTALL_PATH" 2>/dev/null)" ]; then
        fail "Directorul $INSTALL_PATH există deja și nu este o instalare Radio Logbook. Alege altul prin CALL_BOOK_HOME."
    fi
    step "Clonez proiectul în $INSTALL_PATH..."
    git clone --branch "$BRANCH" "$REPOSITORY_URL" "$INSTALL_PATH"
fi

VENV_PYTHON="$INSTALL_PATH/.venv/bin/python"
if [ ! -x "$VENV_PYTHON" ]; then
    step "Creez mediul virtual .venv..."
    "$PYTHON" -m venv "$INSTALL_PATH/.venv"
fi

step "Instalez dependențele (PySide6, openpyxl, curl_cffi)..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$INSTALL_PATH/requirements.txt"

printf '\nRadio Logbook este instalat.\n'
printf 'Director: %s\n' "$INSTALL_PATH"
printf 'Pornire:  %s/Launcher.sh\n' "$INSTALL_PATH"

if [ "${CALL_BOOK_NO_START:-0}" != "1" ]; then
    step "Pornesc aplicația..."
    "$VENV_PYTHON" "$INSTALL_PATH/launcher.py"
fi
