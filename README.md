# Zug Ansagen Web

Moderne Web-App für Browser, mit der Zugansagen aus einer Streckenliste gestartet werden können. Strecken werden als einfache Textdatei hochgeladen, die Ansagetexte lassen sich direkt im Browser wiedergeben (Web Speech API) oder als Text anzeigen.

## Features

- Upload von Strecken (*.txt) – eine Station pro Zeile.
- Automatische Zusatzansagen (Willkommen, Endstation, Abschluss).
- Minimalistische Oberfläche mit Dark/Light Unterstützung, Splash Screen, Logo & Favicon.
- Browser-internes TTS (abschaltbar), keine lokalen Hotkeys mehr notwendig.
- REST API (`/api/...`) zur Fernsteuerung der Ansagen.

## Lokale Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Die Anwendung läuft anschließend unter [http://localhost:8000](http://localhost:8000). Der Splash Screen wird nach dem ersten erfolgreichen Statusabruf ausgeblendet.

## Strecken-Datei

Textdatei (`.txt`) mit UTF-8 oder Latin-1 Kodierung. Eine Station pro Zeile – Reihenfolge entspricht der Fahrt.

```text
Muenchen Hbf
Augsburg Hbf
Ulm Hbf
Stuttgart Hbf
Mannheim Hbf
Frankfurt(Main) Hbf
```

## Docker

```bash
docker build -t zugsim-ansager .
docker run -p 8000:8000 zugsim-ansager
```

### Docker Compose (Komodo-ready)

Die Datei `docker-compose.yml` enthält einen Service `komodo`, wie von Komodo erwartet. Start via:

```bash
docker compose up --build
```

Der Webserver steht danach unter `http://localhost:8000` bereit.

## API Überblick

- `GET /api/state` – aktueller Status, geladene Strecke, nächste Station.
- `POST /api/route` – Upload der Strecke (`multipart/form-data`, Feldname `file`).
- `POST /api/next` – erzeugt nächste Ansage, liefert Text und aktualisierten Status.
- `POST /api/repeat` – wiederholt den letzten Ansagetext.
- `POST /api/reset` – setzt den Zustand zurück.

## Lizenz

MIT – siehe `LICENSE` (falls vorhanden) oder projektspezifische Vereinbarung.
