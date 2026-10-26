# Schreibhilfe für Linux Mint (Cinnamon) — native Fassung

Eine echte GTK-3-Anwendung. **Kein Browser, kein WebKit, kein Webserver.**
Titelleiste und Rahmen zeichnet Cinnamon selbst (Muffin, dein Theme); darunter
Menüleiste, Werkzeugleiste, Schreibfeld, Fundkarten und Statuszeile.

## Installieren und starten

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-gtksource-3.0   # meist schon da
./linux/install.sh
```

`install.sh` prüft die Voraussetzungen (und nennt das fehlende Paket), legt den
Menüeintrag **Schreibhilfe** (Büro) und das Symbol im eigenen Benutzerordner an.
Kein `sudo`, nichts im System, keine Cinnamon-Einstellung wird verändert.
Danach genügt das Anwendungsmenü; ohne Menü: `./linux/run-app.sh`.

* Ein zweiter Start holt das laufende Fenster nach vorn (Gtk.Application).
* Verschiebst du den Projektordner, zieht der nächste Start von `run-app.sh`
  den Menüeintrag selbst nach.
* Entfernen: `./linux/install.sh --weg` (Texte und Einstellungen bleiben).

## Bedienung

| | |
|---|---|
| **Prüfen** (Strg+Eingabe) | jeder Fund als Karte mit Grund; **Ändern** setzt ihn ein |
| **Alles ändern** (Strg+Umschalt+Eingabe) | alles Eindeutige auf einmal, Stellen leuchten grün |
| **Rückgängig / Löschen / Zurückholen** | wie in der Handy-App |
| Wortleiste unter dem Feld | *Weiter mit* (ab 3 Buchstaben) / *Meintest du* (nach dem Klang) |
| **KI-Werkzeuge** | Für wen? · Worum geht's? · KI-Korrektur · Vorschläge · Übersetzen |
| Werkzeugleiste | Einfügen (und gleich prüfen), Kopieren, Vorlesen |
| Menü Datei | Text aus Datei öffnen / als Datei speichern |
| **Einstellungen** (Strg+,) | ersetzen im selben Fenster die Schreibansicht; Esc = zurück |

Die KI-Knöpfe bleiben grau, bis ein API-Schlüssel hinterlegt ist **oder** ein
Ollama-Modell gewählt wurde. Ohne KI-Knopf verlässt kein Wort den Rechner.

## Wo was liegt — alles in diesem Ordner

| Was | Ort |
|---|---|
| Programm | `linux/` (`main.py`, `window.py`, `ui/`, `services/`, `resources/`) |
| Wörterliste und Regeln | `linux/daten/` (Kopie von `online/daten/`; ein Test warnt, wenn sie abweichen) |
| Schlüssel, Modell, Gedächtnis, Kosten | `linux/benutzer/einstellungen.json` (Rechte 600) |
| Schrift, Hell/Dunkel, Stimme | `linux/benutzer/linux.json` |
| Text im Feld, Fenstergröße | `linux/benutzer/text.txt`, `fenster-gtk.json` |

`linux/benutzer/` steht in `.gitignore`: Der Schlüssel gelangt nie ins Repo.
Beim ersten Start werden Einstellungen, Text und Fenstergröße aus den alten
Orten (`~/.config/schreibhilfe`, `~/.local/share/schreibhilfe`) hierher
**kopiert** — nie gelöscht. Piper-Stimmen (`./stimme-holen.sh`, ~90 MB) bleiben,
wo sie schon liegen, oder kommen nach `linux/benutzer/piper`.

Nur der Menüeintrag und das Symbol müssen außerhalb liegen
(`~/.local/share/applications/`, `~/.local/share/icons/`), sonst findet Cinnamon
sie nicht. `./linux/install.sh --weg` entfernt beide.

Die LibreOffice-Erweiterung liest weiter `~/.config/schreibhilfe/`. Wer beide
Programme teilen will, kopiert `einstellungen.json` in den jeweils anderen Ort.

## Aufbau

```
main.py               Einstiegspunkt (prüft GTK, startet application)
application.py        Gtk.Application: Kennung, Programmname, CSS, Symbol
window.py             Hauptfenster: Stapel aus Schreib- und Einstellungsansicht
ui/editor.py          Schreibfeld (GtkSourceView): Wortstreifen, grüne Stellen, Strg+Z
ui/funde.py           Fundkarten
ui/ki_kasten.py       Für wen? / Zettel / KI-Knöpfe
ui/einstellungen.py   Einstellungsansicht
services/pruefung.py  die Prüfung (Abschrift des Originals, Test hält sie gleich)
daten/                Wörterliste und Regeln
benutzer/             Einstellungen und Text (nicht im Repo)
services/klang.py     Kölner Phonetik, Wortvorschläge
services/ki.py        Anweisungen, Claude, Ollama, Kosten
services/einstellungen.py  Einstellungen, Gedächtnis, Sicherungs-Text
services/vorlesen.py  Piper oder spd-say
resources/            Symbol, CSS
tests/                Tests
```

Die Oberfläche rechnet nie selbst: KI und Vorlesen laufen in Hintergrundfäden.

## Tests

```bash
python3 -m unittest discover -s linux/tests -t linux            # Dienste, ohne Fenster
SCHREIBHILFE_GUI_TEST=1 python3 -m unittest discover -s linux/tests -t linux   # mit Fenster
```

Die Tests lenken `linux/benutzer` in einen Wegwerf-Ordner um. Der GUI-Test
öffnet kurz ein echtes Fenster auf dem aktuellen Bildschirm.

## Was sich geändert hat (Webfenster-Problem)

Die alte `linux/schreibhilfe.py` war ein GTK-Rahmen um `WebKit2.WebView`, der
einen lokalen Server startete und `online/index.html` lud — also die Webversion.
Sie ist entfernt; `run-app.sh` startet jetzt `main.py`.
