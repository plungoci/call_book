# Radio Logbook

Aplicație desktop locală/offline pentru evidența legăturilor radioamatorice (QSO). Datele sunt păstrate în SQLite, iar Excel este utilizat numai pentru export.

## Funcționalități

- Adăugare, editare, ștergere, listare și filtrare QSO (indicativ, bandă, mod, repetor și interval UTC), cu confirmare înaintea ștergerii.
- Profil operator persistent în SQLite: date personale, echipament, antenă, putere implicită, club și observații.
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

La prima pornire se creează `data/logbook.db` și `config.json`. Datele personale ale operatorului sunt stocate separat, în tabelul SQLite `operator_profile`, astfel încât nu sunt pierdute la actualizările aplicației.

## Utilizare

Toate orele formularului și ale bazei de date sunt UTC; antetul afișează simultan timpul local și UTC. **QSO nou** sau `Ctrl+N` resetează formularul. `Ctrl+S` salvează, `Ctrl+F` focalizează căutarea, `Delete` șterge QSO-ul selectat după confirmare, iar `Escape` anulează editarea. Repetoarele pot completa frecvența, modul și banda, dar aceste valori rămân editabile.

### Profil operator și localizare Maidenhead

Deschide **Setări → Date operator** (sau butonul **Date operator**) pentru a completa indicativul, numele, locatorul, localitatea, județul, țara, datele de contact, stația, antena, puterea implicită, clubul și observațiile. **Salvează** persistă profilul, iar **Resetează** îl golește numai după confirmare.

Formularul include și **Latitudine**, **Longitudine**, **Precizie localizare**, **Sursa localizării** și **Locator Maidenhead**. Pe Windows, activează mai întâi **Setări Windows → Confidențialitate și securitate → Locație**, apoi apasă **Detectează locația**. Aplicația execută o singură cerere explicită către API-ul local Windows Location (nu urmărește poziția în fundal) și completează câmpurile cu sursa și precizia raportate de sistem. Dacă locatorul salvat diferă, aplicația cere confirmare înainte de înlocuire. Poți introduce manual coordonatele pe orice platformă și apăsa **Recalculează locatorul**.

Coordonatele, sursa, precizia și momentul actualizării sunt păstrate numai local în SQLite, în profilul operatorului. Nu sunt trimise prin internet, nu sunt trimise la servicii de localizare IP, nu sunt scrise în logurile tehnice și nu sunt exportate ca latitudine/longitudine brută. Locatorul operatorului este exportat ADIF ca `MY_GRIDSQUARE` (iar indicativul ca `STATION_CALLSIGN`); locatorul corespondentului rămâne `GRIDSQUARE`. QSO-urile noi rețin o copie a locatorului propriu pentru acuratețe istorică.

Pe laptopuri fără GPS, Windows poate estima poziția din Wi-Fi, rețea sau alte surse disponibile sistemului; precizia poate fi redusă. Un laptop fără senzori sau cu serviciile de localizare dezactivate poate necesita introducerea manuală. Verificarea reală a Windows Location trebuie făcută pe un laptop Windows cu serviciile active; testele automate folosesc mock-uri și nu solicită poziția sistemului.

### Editarea și ștergerea QSO-urilor

Selectează un rând din tabel: devin disponibile **Editează** și **Șterge**. **Editează** încarcă toate datele și schimbă acțiunea principală în **Actualizează QSO**; ID-ul înregistrării rămâne același. **Anulează editarea** abandonează modificările fără a scrie în baza de date. **Șterge** afișează indicativul, frecvența și ora UTC a QSO-ului și solicită confirmare înainte de eliminarea definitivă.

### Formatare automată

Pe măsură ce tastezi, câmpul **Indicativ** este convertit în majuscule (inclusiv cifrele și `/`), iar spațiile exterioare sunt eliminate. Câmpul **Nume** capitalizează fiecare cuvânt și reduce spațiile multiple; cursorul este păstrat în poziția corespunzătoare în timpul formatării. La salvare, aceleași reguli sunt aplicate din nou ca validare finală.

Butonul **Excel** creează implicit un fișier în `exports/`; **ADIF** creează `.adi` în același director; **Backup** folosește API-ul `sqlite3.backup()` și salvează în `backups/`.

## Structură

```text
main.py                 pornire
models.py               modele de date
database.py             acces SQLite parametrizat
validators.py           validare și benzi
utils/maidenhead.py     conversie locală coordonate/locator
services/location_service.py API Windows Location izolat de interfață
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
