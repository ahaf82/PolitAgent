# ⚖️ PolitAgent - Neutraler Bundestag-Protokollant & Web-Dashboard

PolitAgent ist ein vollautomatisches System zur sachlichen, parteipolitisch neutralen und strukturierten Dokumentation und Analyse der Plenarsitzungen des Deutschen Bundestags. 

Die Sitzungen werden vom offiziellen YouTube-Kanal des Bundestags erfasst, die Transkripte analysiert und mithilfe von Gemini in detaillierte Protokolle inklusive einer interaktiven timeline mit direkten YouTube-Sprüngen übersetzt. Ein hochauflösendes Web-Dashboard (optimiert für GitHub Pages) stellt diese Protokolle barrierefrei zur Verfügung.

---

## 🚀 Features

- **Automatischer YouTube-Crawler**: Findet neue Plenarsitzungen und liest Transkripte sekundenschnell über die YouTube-Subtitle-Schnittstellen aus.
- **Smarte Gemini-Protokollierung**: Nutzt Gemini 2.5, um stundenlange Debatten absolut neutral und strukturiert zusammenzufassen.
- **Mehrperspektivische Darstellung**: Argumente aller Fraktionen (Koalition wie Opposition) werden gleichberechtigt und wertungsfrei aufbereitet.
- **Interaktive Timeline**: Jeder wichtige Debattenpunkt enthält eine Sprungmarke, die direkt zur passenden Sekunde im YouTube-Video verlinkt.
- **Premium Glassmorphism-Dashboard**: Modernes Web-Interface mit Echtzeit-Suche, Filterung nach Datum/Sitzung, responsivem Design und Dark Mode.
- **Vollautomatischer Betrieb (Serverless)**: Dank integrierter GitHub Action aktualisiert sich das System täglich vollkommen autark und kostenlos.

---

## 📂 Projektstruktur

```
PolitAgent/
├── .github/
│   └── workflows/
│       └── crawl.yml           # GitHub Action für den täglichen Crawler-Lauf
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

### 4. Crawler ausführen
Führen Sie den Crawler aus, um neue Bundestagssitzungen zu analysieren:
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

## ☁️ Automatisches Deployment (GitHub Pages & Actions)

Das Projekt ist so vorkonfiguriert, dass es sich einmal täglich vollautomatisch im Hintergrund aktualisiert:

1. **GitHub Repository erstellen**: Erstellen Sie ein neues, leeres Repository namens `PolitAgent` unter Ihrem GitHub-Konto.
2. **Push des Codes**: Verknüpfen Sie Ihren lokalen Ordner und pushen Sie den Stand:
   ```bash
   git remote add origin git@github.com:ahaf82/PolitAgent.git
   git branch -M main
   git push -u origin main
   ```
3. **Gemini API Key als Secret hinterlegen**:
   - Gehen Sie in Ihrem GitHub-Repository auf **Settings > Secrets and variables > Actions**.
   - Erstellen Sie ein neues Repository-Secret namens `GEMINI_API_KEY` und fügen Sie Ihren Gemini API-Schlüssel dort ein.
4. **GitHub Pages aktivieren**:
   - Gehen Sie im Repository auf **Settings > Pages**.
   - Wählen Sie unter *Build and deployment > Source* die Option **Deploy from a branch**.
   - Wählen Sie als Branch **`main`** und als Ordner **`/docs`** aus. Speichern Sie.
   - Nach wenigen Minuten ist Ihr interaktives Dashboard weltweit erreichbar unter: `https://<IhrUsername>.github.io/PolitAgent/`

Die GitHub Action sucht ab jetzt jede Nacht um 4:00 Uhr UTC automatisch nach neuen Bundestagsvideos, erstellt die Protokolle und aktualisiert die Webseite!

---

## 📝 Lizenz
Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe die Lizenzbedingungen im Repository.
