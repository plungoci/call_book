# Radio Logbook

Aplicație desktop locală/offline pentru evidența legăturilor radioamatorice (QSO). Datele sunt păstrate în SQLite, iar Excel este utilizat numai pentru export.

## Funcționalități

- Adăugare, editare, ștergere, listare și filtrare QSO (indicativ, bandă, mod, repetor și interval UTC).
- Validare indicativ, frecvență, putere, locator Maidenhead și interval temporal; avertizare pentru duplicate în ±2 minute.
- Calcul configurabil al benzii, repetoare administrabile și păstrarea QSO-urilor la ștergerea unui repetor (`repeater_id` devine `NULL`).
- Export Excel `.xlsx` cu antet, filtru, rând înghețat și dimensiuni ajustate; export ADIF cu lungimi calculate în octeți.
- Backup SQLite online în `backups/`, configurare JSON locală și jurnal în `radio_logbook.log`.

## Cerințe și instalare

Este necesar Python 3.11+ și o instalare Python care include Tkinter.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python main.py
```

La prima pornire se creează `data/logbook.db` și `config.json`. Configurația conține indicativul, operatorul, locatorul, locația, echipamentul, antena, puterea implicită și directoarele de export/backup.

## Utilizare

Toate orele formularului și ale bazei de date sunt UTC; antetul afișează simultan timpul local și UTC. **QSO nou** sau `Ctrl+N` resetează formularul. `Ctrl+S` salvează, `Ctrl+F` focalizează căutarea, `Delete` șterge QSO-ul selectat după confirmare, iar `Escape` anulează editarea. Repetoarele pot completa frecvența, modul și banda, dar aceste valori rămân editabile.

Butonul **Excel** creează implicit un fișier în `exports/`; **ADIF** creează `.adi` în același director; **Backup** folosește API-ul `sqlite3.backup()` și salvează în `backups/`.

## Structură

```text
main.py                 pornire
models.py               modele de date
database.py             acces SQLite parametrizat
validators.py           validare și benzi
adif_export.py          export ADIF
excel_export.py         export Excel
backup.py               backup SQLite
config.py               configurare JSON
ui/                     interfața Tkinter/ttk
tests/                  teste unittest
data/ exports/ backups/ date runtime
```

## Limitări și extensii

Interfața necesită un calculator cu server grafic pentru verificare vizuală. În medii headless se verifică importurile și logica independentă de UI, fără a porni o buclă Tkinter persistentă. Nu sunt implementate QRZ, LoTW/eQSL, CAT, cloud, hărți, autentificare sau o aplicație web; modulele actuale permit adăugarea lor ulterioară fără a amesteca UI cu persistenta.
