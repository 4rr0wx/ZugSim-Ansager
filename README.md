# Zug Ansagen Simulator

Moderne Desktop-App mit Flet (Material 3 UI) fuer Windows, mit der sich Zugansagen fuer Strecken aus einer Textdatei abspielen lassen. Ideal als Begleiter fuer den Zugsimulator: Globale Hotkeys feuern im Hintergrund die jeweils naechste Ansage ab.

## Features

- Strecken (*.txt) mit beliebig vielen Stationen laden (eine Station pro Zeile).
- Automatisch eingefuegte Standardansagen:
  - Willkommenstext beim Start der Fahrt.
  - Endstationshinweis fuer die letzte Station.
- Globale Hotkeys fuer
  - naechste Ansage (`Ctrl` + `Alt` + `N`)
  - Wiederholung der letzten Ansage (`Ctrl` + `Alt` + `R`)
- Hotkeys lassen sich im laufenden Betrieb anpassen.
- Text-to-Speech ueber `pyttsx3` (offline).

## Installation

1. [Python 3.10+](https://www.python.org/downloads/windows/) installieren und sicherstellen, dass `python` und `pip` im `PATH` liegen.
2. Abhaengigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
3. Die App starten:
   ```bash
   python app.py
   ```

> **Hinweis:** Das `keyboard`-Modul benoetigt fuer globale Hotkeys unter Windows meist Administratorrechte. Starte das Terminal beziehungsweise die App bei Bedarf als Administrator.

> Flet kann die App in einem eingebetteten Fenster oder Browser darstellen. Beim ersten Start koennen Firewall-Rueckfragen erscheinen, die lokalen Zugriff erlauben sollten.

## Strecken-Datei

- Einfache Textdatei (`.txt`) mit UTF-8 oder Latin-1 Kodierung.
- Eine Station pro Zeile, in Fahrt-Reihenfolge (erste Zeile = Abfahrtsbahnhof, letzte Zeile = Endstation).

Beispiel:

```text
Muenchen Hbf
Augsburg Hbf
Ulm Hbf
Stuttgart Hbf
Mannheim Hbf
Frankfurt(Main) Hbf
```

## Bedienung

1. App starten und ueber **"Strecke laden..."** die gewuenschte Textdatei auswaehlen (Dateiendung `.txt`).
2. Mit dem Button **"Naechste Ansage"** oder dem zugeordneten Hotkey die Ansagen abspielen.
3. Die Liste zeigt stets den naechsten Halt. Die Statuszeile bestaetigt abgespielte Texte.
4. Hotkeys lassen sich im unteren Bereich aendern; danach auf **"Hotkeys uebernehmen"** klicken.
5. Zum Beenden einfach das Fenster schliessen. Die Hotkeys werden automatisch abgemeldet.

## Tipps

- Falls die Stimme zu langsam oder zu schnell wirkt, kann in `app.py` im `AudioEngine`-Konstruktor die `rate` des `pyttsx3`-Engines angepasst werden.
- Fuer eigene Audio-Dateien anstelle von TTS koennte der `AudioEngine`-Teil spaeter gegen eine Soundplayer-Implementierung getauscht werden.
