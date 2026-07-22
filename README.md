# Radio Logbook

Aplicație desktop locală/offline pentru evidența legăturilor radioamatorice (QSO). Datele sunt păstrate în SQLite, iar Excel este utilizat numai pentru export.

## Funcționalități

- Adăugare, editare, ștergere, listare și filtrare QSO (indicativ, bandă, mod, repetor și interval UTC), cu confirmare înaintea ștergerii.
- Profil operator persistent în SQLite: date personale, echipament, antenă, putere implicită, club și observații.
- Validare indicativ, frecvență, putere, locator Maidenhead, date de propagare și interval temporal; avertizare pentru duplicate în ±2 minute.
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

Toate orele formularului și ale bazei de date sunt UTC; antetul afișează simultan timpul local și UTC. **QSO nou** sau `Ctrl+N` resetează formularul. `Ctrl+S` salvează, `Ctrl+F` deschide și focalizează căutarea, `Delete` șterge QSO-ul selectat după confirmare, iar `Escape` anulează editarea. Repetoarele pot completa frecvența, modul și banda, dar aceste valori rămân editabile.

### Meniul Fișier

Acțiunile care produc fișiere sunt grupate în **Fișier**: **Exportă Excel**, **Exportă ADIF** și **Creează backup**. Exporturile păstrează aceleași formate și alegerea destinației, iar backupul SQLite este creat în `backups/`. Comanda **Ieșire** închide în siguranță aplicația și ferestrele secundare deschise.

### Meniul Setări

**Setări → Date operator** deschide profilul operatorului, iar **Setări → Repetoare** deschide administrarea repetoarelor. Dacă una dintre aceste ferestre este deja deschisă, aplicația o aduce în față în loc să creeze un duplicat.

### Căutare și filtrare

Panoul de căutare și filtrare este ascuns la pornire pentru a păstra ecranul principal aerisit. Apasă **Caută / Filtrează** sau `Ctrl+F` pentru a-l afișa; butonul devine **Ascunde căutarea**. Ascunderea panoului nu șterge valorile și nu modifică rezultatele deja filtrate. Folosește numai **Resetează filtrele** pentru a elimina filtrele active.

### Profil operator și localizare Maidenhead

Deschide **Setări → Date operator** pentru a completa indicativul, numele, locatorul, localitatea, județul, țara, datele de contact, stația, antena, puterea implicită, clubul și observațiile. **Salvează** persistă profilul, iar **Resetează** îl golește numai după confirmare.

Formularul include și **Latitudine**, **Longitudine**, **Precizie localizare**, **Sursa localizării** și **Locator Maidenhead**. Pe Windows, activează mai întâi **Setări Windows → Confidențialitate și securitate → Locație**, apoi apasă **Detectează locația**. Aplicația execută o singură cerere explicită către API-ul local Windows Location (nu urmărește poziția în fundal) și completează câmpurile cu sursa și precizia raportate de sistem. Dacă locatorul salvat diferă, aplicația cere confirmare înainte de înlocuire. Poți introduce manual coordonatele pe orice platformă și apăsa **Recalculează locatorul**.

Coordonatele, sursa, precizia și momentul actualizării sunt păstrate numai local în SQLite, în profilul operatorului. Nu sunt trimise prin internet, nu sunt trimise la servicii de localizare IP, nu sunt scrise în logurile tehnice și nu sunt exportate ca latitudine/longitudine brută. Locatorul operatorului este exportat ADIF ca `MY_GRIDSQUARE` (iar indicativul ca `STATION_CALLSIGN`); locatorul corespondentului rămâne `GRIDSQUARE`. QSO-urile noi rețin o copie a locatorului propriu pentru acuratețe istorică.

Pe laptopuri fără GPS, Windows poate estima poziția din Wi-Fi, rețea sau alte surse disponibile sistemului; precizia poate fi redusă. Un laptop fără senzori sau cu serviciile de localizare dezactivate poate necesita introducerea manuală. Verificarea reală a Windows Location trebuie făcută pe un laptop Windows cu serviciile active; testele automate folosesc mock-uri și nu solicită poziția sistemului.

### Editarea și ștergerea QSO-urilor

Selectează un rând din tabel: devin disponibile **Editează** și **Șterge**. **Editează** încarcă toate datele și schimbă acțiunea principală în **Actualizează QSO**; ID-ul înregistrării rămâne același. **Anulează editarea** abandonează modificările fără a scrie în baza de date. **Șterge** afișează indicativul, frecvența și ora UTC a QSO-ului și solicită confirmare înainte de eliminarea definitivă.

### Formatare automată

Pe măsură ce tastezi, câmpul **Indicativ** este convertit în majuscule (inclusiv cifrele și `/`), iar spațiile exterioare sunt eliminate. Câmpul **Nume** capitalizează fiecare cuvânt și reduce spațiile multiple; cursorul este păstrat în poziția corespunzătoare în timpul formatării. La salvare, aceleași reguli sunt aplicate din nou ca validare finală.

Din **Fișier**, **Exportă Excel** creează implicit un fișier în `exports/`, **Exportă ADIF** creează `.adi` în același director, iar **Creează backup** folosește API-ul `sqlite3.backup()` și salvează în `backups/`.

### Propagare

Secțiunea **Propagare** a formularului este opțională și documentează traseul real al semnalului. După alegerea sau detectarea benzii din frecvență, aplicația completează **Tip propagare** cu o **sugestie implicită**: de exemplu, 20 m → **F2**, 40/80 m → **NVIS**, iar 2 m/70 cm → **Directă**. Aceasta nu detectează și nu confirmă condițiile ionosferice sau atmosferice reale; fenomene precum Sporadic-E, aurora, ducting sau rain scatter trebuie confirmate și, când este cazul, alese manual de operator.

Sugestia poate fi modificată din listă, iar valoarea manuală este protejată la schimbările obișnuite ale frecvenței, benzii sau modului (inclusiv **EME (Moonbounce)**). Eticheta discretă indică **Sugestie automată** sau **Valoare manuală**. **Satelit** are cea mai mare prioritate, urmat de **Repeater** pentru un repetor selectat; modurile de rețea EchoLink, AllStar, DMR, D-STAR, C4FM și Internet Gateway sunt de asemenea păstrate. Pentru a ignora temporar valoarea manuală, apasă **Recalculează propagarea**: aplicația reaplică regulile după bandă, mod, repetor și satelit și marchează rezultatul automat. QSO-urile deja salvate și încărcate pentru editare își păstrează propagarea istorică până când schimbi contextul relevant sau folosești acest buton.

Alege **Directă** pentru legături fără releu, **Repeater** pentru un repetor selectat deja în QSO, și **Satelit** pentru comunicații prin satelit. Lista include și modurile uzuale de propagare: **EME (Moonbounce)**, **Meteor Scatter**, **Troposcatter**, **Tropospheric Ducting**, **Sporadic-E**, **F2**, **Aurora/Aurora-E**, **NVIS**, **Backscatter**, **Aircraft/Rain Scatter** și **Ionoscatter**, precum și opțiuni pentru gateway-uri și moduri digitale. Selectează **Necunoscută** când traseul nu este cunoscut și **Altele** pentru un caz neacoperit de listă.

Pentru **Satelit**, completează obligatoriu numele satelitului și modurile de lucru **uplink** și **downlink**; de exemplu, `QO-100`, `SSB`, `SSB`. Alegerea **QO-100** completează automat propagarea prin satelit și numele satelitului. **Distanță (km)** acceptă un număr pozitiv cu zecimale, iar **Azimut (°)** este opțional și trebuie să fie între 0 și 360. Observațiile de propagare pot păstra detalii precum QSB, aurora sau o deschidere Sporadic-E. Câmpurile sunt separate în modelul QSO pentru a permite ulterior calculul din locator, integrarea indicilor solari și a serviciilor de propagare.

Exportul ADIF include `PROP_MODE` când există echivalent ADIF, `SAT_NAME`, `SAT_MODE` (uplink/downlink), `DISTANCE` și observațiile de propagare în `COMMENT`, păstrând și observațiile QSO existente. Azimutul și modurile fără echivalent ADIF rămân disponibile în Excel. Exportul Excel adaugă coloanele **Propagare**, **Satelit**, **Uplink**, **Downlink**, **Distanță**, **Azimut** și **Observații propagare**.

## Structură

```text
main.py                 pornire
models.py               modele de date
database.py             acces SQLite parametrizat
validators.py           validare și benzi
utils/maidenhead.py     conversie locală coordonate/locator
services/location_service.py API Windows Location izolat de interfață
services/propagation_service.py reguli testabile pentru sugestia implicită de propagare
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
