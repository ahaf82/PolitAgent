# ⚖️ PolitAgent - Neutraler Bundestag-Protokollant & Web-Dashboard

PolitAgent ist ein vollautomatisches System zur sachlichen, parteipolitisch neutralen und strukturierten Dokumentation und Analyse der Plenarsitzungen des Deutschen Bundestags.

Die Bundestagsdebatten werden vom offiziellen YouTube-Kanal erfasst, die Transkripte analysiert und mithilfe von Gemini in detaillierte Protokolle inklusive einer interaktiven Timeline mit direkten YouTube-Sprüngen übersetzt. Ein hochauflösendes Web-Dashboard (optimiert für GitHub Pages) stellt diese Protokolle barrierefrei zur Verfügung.

---

## 🚀 Features

- **Automatischer YouTube-Crawler**: Findet neue Plenarsitzungen und Ausschussdebatten über YouTube RSS und `yt-dlp`.
- **Robuster Playwright-Scraper (Bypass)**: Da YouTube Zugriffe von Cloud-Servern blockiert, nutzt der Crawler Playwright Chromium lokal als Fallback. Er akzeptiert Cookiedialoge, expandiert die Beschreibung und führt direkte JavaScript-Clicks aus, um Transkripte sicher auszulesen.
- **Fehlertolerante Gemini-API**: Verwendet `gemini-2.5-flash` mit einem **automatischen Rate-Limit- und Überlastungs-Handler**. Tritt ein Fehler (HTTP 429 oder 503) auf, schläft das Skript automatisch mit exponentiellem Backoff und versucht es erneut.
- **Smarte Protokollierung**: Generiert stundenlange Debatten absolut neutral und übersetzt englische Themen sinnvoll ins Deutsche.
- **Interaktive Timeline**: Jeder Redebeitrag enthält eine verlinkte Zeitangabe, die direkt zur entsprechenden Sekunde im YouTube-Video führt.
- **Premium Glassmorphism-Dashboard**: Modernes Web-Interface mit Echtzeit-Suche, Filterung nach Datum/Sitzung, responsivem Design, Statistik-Karten und Dark Mode Toggle.
- **Lokale Hintergrund-Automatisierung**: Dank des Antigravity-Schedulers läuft der Crawler vollkommen geräuschlos im Hintergrund Ihrer lokalen Maschine und synchronisiert Updates vollautomatisch mit GitHub Pages.

---

## 📂 Projektstruktur

```
PolitAgent/
├── docs/                       # Web-Dashboard (GitHub Pages Stammverzeichnis)
│   ├── data/
│   │   └── sessions.json       # Zentraler Index aller Sitzungen und Metadaten
│   ├── protocols/              # Generierte Markdown-Protokolle (nach Sitzung sortiert)
│   ├── app.js                  # Frontend-Anwendungslogik
│   ├── styles.css              # Premium Glassmorphism UI Styles
│   └── index.html              # Hauptseite des Dashboards
├── crawler.py                  # Der Python-Crawler & Analyzer
├── requirements.txt            # Python Dependencies
├── .env.example                # Template für lokalen API-Key
└── .gitignore                  # Git-Ausschlüsse
```

---

## 🛠️ Lokale Einrichtung & Verwendung

### 1. Voraussetzungen
Stellen Sie sicher, dass Python (3.11+) installiert ist.

### 2. Installation
Klonen Sie das Repository und installieren Sie die Abhängigkeiten:
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. API-Schlüssel einrichten
1. Kopieren Sie die `.env.example`-Datei zu `.env`:
   ```bash
   copy .env.example .env
   ```
2. Öffnen Sie die `.env` und tragen Sie Ihren **Gemini API-Key** ein:
   ```env
   GEMINI_API_KEY=AIzaSy...
   ```
   *(Einen kostenlosen API-Key erhalten Sie im [Google AI Studio](https://aistudio.google.com/))*

### 4. Crawler manuell ausführen
```bash
python crawler.py
```
*Standardmäßig lädt der Crawler bei der Erstausführung die Sitzungen der letzten 3 Sitzungstage herunter. Bei Folgeläufen werden automatisch nur neue, noch nicht verarbeitete Videos ergänzt.*

### 5. Dashboard lokal starten
Da das Dashboard die Daten per AJAX/Fetch nachlädt, muss es über einen lokalen Webserver geöffnet werden:
```bash
cd docs
python -m http.server 8000
```
Öffnen Sie anschließend **`http://localhost:8000`** in Ihrem Browser.

---

## 🤖 Automatisierung (Antigravity Scheduled Task)

Da YouTube direkte API-Anfragen nach Untertiteln von Cloud-Rechenzentren (wie GitHub Actions oder AWS/Azure-Instanzen) rigoros blockiert, läuft der Crawler als **hybride Lösung** über einen lokalen Scheduler:

### Funktionsweise
1. **Scheduled Task in Antigravity:** Auf Ihrer lokalen Instanz ist ein Scheduled Task registriert, der den Crawler **zweimal täglich** (`08:00` und `20:00` Uhr) im Hintergrund startet.
2. **Lokaler Durchlauf (Wohnzimmer-IP):** Da der Crawler Ihre private DSL-Verbindung nutzt, greift er ohne Sperren per Playwright auf YouTube zu, zieht die Transkripte und übersetzt sie via Gemini.
3. **Automatischer Git-Push:** Am Ende der Pipeline committet und pusht das Skript die neuen Markdown-Dateien und den aktualisierten Index automatisch in Ihr GitHub-Repository.
4. **Instant Update:** GitHub Pages baut das statische Dashboard live neu. Die Updates sind sofort weltweit unter Ihrer GitHub Pages URL erreichbar!

*Sollte Ihr PC um 08:00 Uhr morgens ausgeschaltet sein, holt der Antigravity-Dienst die verpasste Ausführung automatisch nach, sobald Sie den Rechner einschalten.*

---

## ☁️ Cloud-Hosting (GitHub Pages)

So schalten Sie das Web-Dashboard weltweit frei:

1. **GitHub Pages aktivieren**:
   - Gehen Sie in Ihrem GitHub-Repository (`ahaf82/PolitAgent`) auf **Settings > Pages**.
   - Wählen Sie unter *Build and deployment > Source* die Option **Deploy from a branch**.
   - Wählen Sie als Branch **`main`** und als Ordner **`/docs`** aus. Speichern Sie.
   - Nach wenigen Minuten ist Ihr interaktives Dashboard weltweit erreichbar unter: `https://ahaf82.github.io/PolitAgent/`

---

## 📝 Lizenz
Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe die Lizenzbedingungen im Repository.
