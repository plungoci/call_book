#!/usr/bin/env bash
# Instalează și pornește Radio Logbook pe un calculator Linux sau macOS.
#
# Verifică Git și Python 3.11+, clonează proiectul, creează mediul virtual .venv,
# instalează dependențele și bibliotecile de sistem de care are nevoie Qt, verifică
# instalarea și pornește aplicația. Rularea din nou repară sau actualizează o
# instalare existentă, în loc să o dubleze.
#
#   curl -fsSL https://raw.githubusercontent.com/plungoci/call_book/main/scripts/install.sh | bash
#
# Variabile de mediu opționale:
#   CALL_BOOK_HOME        directorul de instalare (implicit ~/call_book)
#   CALL_BOOK_BRANCH      ramura Git (implicit main)
#   CALL_BOOK_NO_START=1  nu porni aplicația la final
#   CALL_BOOK_REPOSITORY  alt repository Git (folosit de CI pentru propria copie)

# Tot scriptul stă într-o funcție apelată pe ultimul rând: cu `curl ... | bash`,
# bash citește scriptul din stdin pe măsură ce îl execută, iar o comandă care
# citește și ea din stdin (apt-get, dpkg) ar înghiți restul scriptului. Așa,
# bash parcurge tot textul înainte să execute ceva — și nici o descărcare
# întreruptă nu poate rula pe jumătate.

set -euo pipefail

REPOSITORY_URL="${CALL_BOOK_REPOSITORY:-https://github.com/plungoci/call_book.git}"
INSTALL_PATH="${CALL_BOOK_HOME:-$HOME/call_book}"
BRANCH="${CALL_BOOK_BRANCH:-main}"

# Bibliotecile de sistem de care au nevoie Qt și pluginul lui X11 (xcb); roțile
# PySide6 nu le includ. Pe fiecare rând: biblioteca, apoi pachetul care o oferă
# pe apt (Debian/Ubuntu/Mint), dnf (Fedora/RHEL), pacman (Arch) și zypper (openSUSE).
QT_LIBRARIES="
libEGL.so.1             libegl1             libglvnd-egl        libglvnd           libEGL1
libGL.so.1              libgl1              libglvnd-glx        libglvnd           libGL1
libOpenGL.so.0          libopengl0          libglvnd-opengl     libglvnd           libOpenGL0
libxkbcommon.so.0       libxkbcommon0       libxkbcommon        libxkbcommon       libxkbcommon0
libxkbcommon-x11.so.0   libxkbcommon-x11-0  libxkbcommon-x11    libxkbcommon-x11   libxkbcommon-x11-0
libdbus-1.so.3          libdbus-1-3         dbus-libs           dbus               libdbus-1-3
libfontconfig.so.1      libfontconfig1      fontconfig          fontconfig         libfontconfig1
libX11-xcb.so.1         libx11-xcb1         libX11-xcb          libx11             libX11-xcb1
libxcb-cursor.so.0      libxcb-cursor0      xcb-util-cursor     xcb-util-cursor    libxcb-cursor0
libxcb-icccm.so.4       libxcb-icccm4       xcb-util-wm         xcb-util-wm        libxcb-icccm4
libxcb-keysyms.so.1     libxcb-keysyms1     xcb-util-keysyms    xcb-util-keysyms   libxcb-keysyms1
libxcb-image.so.0       libxcb-image0       xcb-util-image      xcb-util-image     libxcb-image0
libxcb-render-util.so.0 libxcb-render-util0 xcb-util-renderutil xcb-util-renderutil libxcb-render-util0
libxcb-shape.so.0       libxcb-shape0       libxcb              libxcb             libxcb-shape0
"

step() { printf '\n==> %s\n' "$1"; }
warn() { printf 'Atenție: %s\n' "$1" >&2; }
fail() {
    printf '\nEroare: %s\n' "$1" >&2
    exit 1
}

python_is_recent() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1
}

find_python() {
    local candidate
    for candidate in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && python_is_recent "$candidate"; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

python_version() {
    "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])'
}

package_manager() {
    local manager
    for manager in apt-get dnf pacman zypper brew; do
        if command -v "$manager" >/dev/null 2>&1; then
            echo "$manager"
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

APT_UPDATED=0
install_packages() {
    local manager
    manager="$(package_manager)" || return 1
    step "Instalez pachetele de sistem lipsă: $*"
    case "$manager" in
        apt-get)
            if [ "$APT_UPDATED" -eq 0 ]; then
                as_root apt-get update -qq </dev/null || return 1
                APT_UPDATED=1
            fi
            as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" </dev/null
            ;;
        dnf) as_root dnf install -y "$@" </dev/null ;;
        pacman) as_root pacman -S --needed --noconfirm "$@" </dev/null ;;
        zypper) as_root zypper --non-interactive install "$@" </dev/null ;;
        brew) brew install "$@" </dev/null ;;
    esac
}

ensure_git() {
    step "Verific Git..."
    command -v git >/dev/null 2>&1 && return 0
    install_packages git || true
    command -v git >/dev/null 2>&1 ||
        fail "Git lipsește și nu l-am putut instala automat. Instalează-l manual și rulează scriptul din nou."
}

ensure_python() {
    step "Verific Python 3.11 sau mai nou..."
    if ! PYTHON="$(find_python)"; then
        case "$(package_manager || true)" in
            # Pe Ubuntu 22.04, `python3` este 3.10; versiunile mai noi sunt
            # pachete separate, deci le încercăm pe rând.
            apt-get)
                install_packages python3 python3-venv || true
                PYTHON="$(find_python)" || install_packages python3.12 python3.12-venv ||
                    install_packages python3.11 python3.11-venv || true
                ;;
            dnf) install_packages python3 || true
                PYTHON="$(find_python)" || install_packages python3.12 || install_packages python3.11 || true ;;
            pacman) install_packages python || true ;;
            zypper) install_packages python311 || true ;;
            brew) install_packages python@3.12 || true ;;
        esac
        PYTHON="$(find_python)" ||
            fail "Python 3.11+ lipsește și nu l-am putut instala automat. Instalează-l (https://www.python.org/downloads/) și rulează scriptul din nou."
    fi
    printf 'Folosesc %s (Python %s)\n' "$PYTHON" "$(python_version "$PYTHON")"

    # Pe Debian/Ubuntu, modulul venv (ensurepip) este un pachet separat, iar
    # fără el `python -m venv` lasă în urmă un mediu virtual fără pip.
    if ! "$PYTHON" -c 'import ensurepip, venv' >/dev/null 2>&1; then
        install_packages "python$(python_version "$PYTHON")-venv" || install_packages python3-venv || true
        "$PYTHON" -c 'import ensurepip, venv' >/dev/null 2>&1 ||
            fail "Modulul venv al lui Python lipsește. Instalează pachetul python3-venv și rulează scriptul din nou."
    fi
}

get_sources() {
    if [ -d "$INSTALL_PATH/.git" ]; then
        step "Actualizez instalarea existentă din $INSTALL_PATH..."
        # O actualizare eșuată nu oprește instalarea: versiunea locală rămâne
        # funcțională, iar lansatorul spune la pornire de ce nu s-a actualizat.
        if ! git -C "$INSTALL_PATH" fetch origin ||
            ! git -C "$INSTALL_PATH" merge --ff-only "origin/$(git -C "$INSTALL_PATH" rev-parse --abbrev-ref HEAD)"; then
            warn "Nu am putut actualiza proiectul; continui cu versiunea locală."
        fi
        return 0
    fi
    if [ -e "$INSTALL_PATH" ] && [ -n "$(ls -A "$INSTALL_PATH" 2>/dev/null)" ]; then
        fail "Directorul $INSTALL_PATH există deja și nu este o instalare Radio Logbook. Alege altul prin CALL_BOOK_HOME."
    fi
    step "Clonez proiectul în $INSTALL_PATH..."
    git clone --branch "$BRANCH" "$REPOSITORY_URL" "$INSTALL_PATH" </dev/null
}

create_venv() {
    VENV_PYTHON="$INSTALL_PATH/.venv/bin/python"
    # Un mediu virtual creat pe jumătate (de exemplu fără python3-venv) are
    # interpretorul, dar nu și pip; se recreează în loc să fie refolosit.
    if [ -x "$VENV_PYTHON" ] && "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
        return 0
    fi
    step "Creez mediul virtual .venv..."
    rm -rf "$INSTALL_PATH/.venv"
    "$PYTHON" -m venv "$INSTALL_PATH/.venv"
    "$VENV_PYTHON" -m pip --version >/dev/null 2>&1 || fail "Mediul virtual a fost creat fără pip."
}

install_dependencies() {
    step "Instalez dependențele Python (PySide6, openpyxl, curl_cffi)..."
    "$VENV_PYTHON" -m pip install --upgrade pip </dev/null
    "$VENV_PYTHON" -m pip install --upgrade -r "$INSTALL_PATH/requirements.txt" </dev/null
}

# Rulează după ensure_qt_libraries: importul QtWidgets are nevoie de libEGL & co.
verify_dependencies() {
    step "Verific instalarea..."
    "$VENV_PYTHON" -c 'import PySide6.QtWidgets, openpyxl, curl_cffi' ||
        fail "Dependențele Python s-au instalat, dar nu pot fi importate (vezi eroarea de mai sus)."
    echo "Totul este în regulă."
}

# Afișează bibliotecile de care are nevoie pluginul X11 al lui Qt și care lipsesc.
missing_qt_libraries() {
    local plugin
    # Pachetul e localizat fără să fie importat: importul ar cere chiar
    # bibliotecile de sistem pe care le căutăm.
    plugin="$("$VENV_PYTHON" -c 'import importlib.util, pathlib
spec = importlib.util.find_spec("PySide6")
roots = list(spec.submodule_search_locations or []) if spec else []
print(next((str(p) for r in roots for p in pathlib.Path(r).glob("Qt/plugins/platforms/libqxcb.so")), ""))')"
    if [ -n "$plugin" ] && command -v ldd >/dev/null 2>&1; then
        ldd "$plugin" | awk '/not found/ { print $1 }' | sort -u
    fi
    # ldd nu vede bibliotecile încărcate dinamic la rulare (libxcb-cursor e una).
    # Lista e citită întreagă înainte de căutare: cu `pipefail`, un `grep -q`
    # care închide pipe-ul devreme ar face ca ldconfig să pară că a eșuat.
    local cache library
    cache="$( (ldconfig -p || /sbin/ldconfig -p) 2>/dev/null || true)"
    [ -n "$cache" ] || return 0
    for library in libxcb-cursor.so.0 libEGL.so.1; do
        case "$cache" in
            *"$library "*) ;;
            *) echo "$library" ;;
        esac
    done
}

ensure_qt_libraries() {
    [ "$(uname -s)" = "Linux" ] || return 0
    step "Verific bibliotecile de sistem de care are nevoie Qt..."
    local missing manager column packages="" library package
    missing="$(missing_qt_libraries | sort -u)"
    if [ -z "$missing" ]; then
        echo "Toate sunt prezente."
        return 0
    fi
    manager="$(package_manager || true)"
    case "$manager" in
        apt-get) column=2 ;;
        dnf) column=3 ;;
        pacman) column=4 ;;
        zypper) column=5 ;;
        *) column="" ;;
    esac
    for library in $missing; do
        package=""
        if [ -n "$column" ]; then
            package="$(printf '%s\n' "$QT_LIBRARIES" | awk -v lib="$library" -v col="$column" '$1 == lib { print $col }')"
        fi
        if [ -n "$package" ]; then
            case " $packages " in *" $package "*) ;; *) packages="$packages $package" ;; esac
        fi
    done
    # shellcheck disable=SC2086
    if [ -n "$packages" ] && install_packages $packages; then
        missing="$(missing_qt_libraries | sort -u)"
    fi
    if [ -n "$missing" ]; then
        # shellcheck disable=SC2086
        warn "lipsesc bibliotecile de sistem: $(printf '%s ' $missing)— Fără ele, fereastra aplicației nu se poate deschide; instalează pachetele care le oferă și rulează scriptul din nou."
    fi
}

main() {
    ensure_git
    ensure_python
    get_sources
    create_venv
    install_dependencies
    ensure_qt_libraries
    verify_dependencies
    chmod +x "$INSTALL_PATH/Launcher.sh" 2>/dev/null || true

    printf '\nRadio Logbook este instalat.\n'
    printf 'Director: %s\n' "$INSTALL_PATH"
    printf 'Pornire:  %s/Launcher.sh\n' "$INSTALL_PATH"

    if [ "${CALL_BOOK_NO_START:-0}" != "1" ]; then
        step "Pornesc aplicația..."
        "$INSTALL_PATH/Launcher.sh" </dev/null
    fi
}

main "$@"
