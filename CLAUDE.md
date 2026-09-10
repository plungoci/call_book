# Instrucțiuni pentru Claude Code în acest proiect

## Flux de lucru Git

**Orice modificare cerută primește un branch propriu și un pull request nou.**
Cerere explicită a utilizatorului, nu preferință dedusă.

- Niciodată nu se adaugă commituri într-un PR existent pentru o lucrare nouă.
- Niciodată nu se refolosește un branch al cărui PR a fost deja fuzionat: se
  pornește un branch nou din `origin/main` la zi.
- Branch: `claude/<descriere-scurtă>`, în română, descriind lucrarea.
- PR-ul se creează după ce lucrarea este completă și verificată, fără să fie
  nevoie să fie cerut separat.
- Înainte de a începe: `git fetch origin main`, apoi branch din `origin/main`.
  Un PR fuzionat nu mai poate purta lucrare nouă — dacă un commit a rămas pe
  un branch al cărui PR s-a fuzionat între timp, se mută pe un branch nou
  (`git cherry-pick`) și primește PR propriu.
- Excepție: corecțiile pe feedback de review sau pe CI roșu se împing în
  PR-ul lor, pentru că sunt iterație pe aceeași lucrare, nu lucrare nouă.

## Limbă

Interfața, mesajele către utilizator, documentația (README) și mesajele de
commit sunt în română, cu diacritice. Comentariile din cod și docstringurile
sunt în engleză, ca restul codului existent.

## Verificări înainte de commit

Toate trebuie să treacă; CI le rulează pe aceleași:

```bash
ruff check .
ruff format --check .
python -m mypy call_book main.py launcher.py tests
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests
```

Testele Qt au nevoie de bibliotecile de sistem Qt (`libegl1`, `libgl1`,
`libopengl0`, `libxkbcommon0`, `libdbus-1-3`) plus `QT_QPA_PLATFORM=offscreen`.
Suita rulează integral offline — nimic din ea nu trebuie să atingă rețeaua.

## Dependențe

`requirements.txt` = rulare (instalat și de `launcher.py` la actualizare);
`requirements-dev.txt` = rulare + `ruff` și `mypy`. Aceleași versiuni sunt
declarate în `pyproject.toml` (`[project.optional-dependencies] dev`). Cele
trei trebuie ținute sincronizate.

## Interfață

Aplicația trebuie să rămână utilizabilă pe ecrane mici (1366x768) și la
scalare 125–150%: fără dimensiuni fixe în pixeli care să impună o lățime
minimă ferestrei. Panourile din `Jurnal QSO` se rearanjează după lățime — vezi
`QSOForm._relayout`.

Pentru capturi din aplicație în mod headless, fereastra trebuie **afișată**
(`show()`) înainte de `grab()`; altfel layouturile copil nu rulează și
randarea iese greșită.
