# Schreibhilfe für Linux Mint (Cinnamon) — native Fassung

Eine echte GTK-3-Anwendung. **Kein Browser, kein WebKit, kein Webserver.**
Titelleiste und Rahmen zeichnet Cinnamon selbst (Muffin, dein Theme); darunter
Menüleiste, Werkzeugleiste, Schreibfeld, Fundkarten und Statuszeile.

## Voraussetzungen

Linux Mint 22.x / Ubuntu 24.04 (Python 3.12). Laufzeit:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0          # Pflicht
sudo apt install gir1.2-gtksource-3.0 speech-dispatcher   # empfohlen: Strg+Z im Feld, Vorlesen
```

## Als Debian-Paket installieren (empfohlen)

```bash
sudo apt install build-essential dpkg-dev debhelper librsvg2-bin lintian   # nur zum Bauen
./linux/build-deb.sh                          # baut nach linux/dist/, installiert nichts
./linux/build-deb.sh --pruefen                # dazu dpkg-deb --info/--contents und lintian
sudo apt install ./linux/dist/stevie-schreibhilfe_1.0.5_all.deb
```

`build-deb.sh` baut in einer Wegwerf-Kopie und lässt `linux/benutzer/`
(Schlüssel, Text) außen vor. Beim Bauen laufen die Tests der Dienste mit
(`DEB_BUILD_OPTIONS=nocheck` schaltet sie ab).

| Was | Wo |
|---|---|
| Programm, Wörterliste, Regeln, Symbol (nur lesen) | `/opt/stevie-empire/schreibhilfe/` |
| Starter | `/opt/stevie-empire/schreibhilfe/bin/schreibhilfe` |
| Befehl im Terminal | `schreibhilfe` (`/usr/bin/schreibhilfe`, Link aus dem Paket) |
| Menüeintrag | `/usr/share/applications/stevie-schreibhilfe.desktop` („Schreibhilfe“, Büro) |
| Symbol | `/usr/share/icons/hicolor/{scalable,16x16 … 512x512}/apps/stevie-schreibhilfe.*` |
| Handbuchseite | `man schreibhilfe` |
| Einstellungen, Schlüssel, Gedächtnis | `~/.config/schreibhilfe/einstellungen.json` (Rechte 600) |
| Schrift, Hell/Dunkel, Stimme | `~/.config/schreibhilfe/linux.json` |
| Text im Feld, Fenstergröße, Piper-Stimmen | `~/.local/share/schreibhilfe/` |

Gesetzte `XDG_CONFIG_HOME` / `XDG_DATA_HOME` gelten statt `~/.config` und
`~/.local/share`. Installiert schreibt die App nie nach `/opt`. Die
LibreOffice-Erweiterung liest dieselbe `~/.config/schreibhilfe/einstellungen.json`.

Das Paket ersetzt das ältere Paket `schreibhilfe` (1.0.2, unter
`/opt/schreibhilfe`); apt entfernt es beim Installieren. Wer zusätzlich
`install.sh` benutzt hat, nimmt diesen Eintrag mit `./linux/install.sh --weg`
zurück — sonst stehen zwei „Schreibhilfe“ im Menü.

Entfernen:

```bash
sudo apt remove stevie-schreibhilfe   # Programm, Link, Menüeintrag, Symbol
```

Einstellungen und Texte in `~/.config/schreibhilfe` und
`~/.local/share/schreibhilfe` bleiben erhalten, auch bei `apt purge`.

## Ohne Paket aus dem Projektordner starten (Entwicklung)

```bash
./linux/install.sh        # prüft Voraussetzungen, legt Menüeintrag + Symbol in ~/.local/share an
./linux/run-app.sh        # startet die App (erneuert dabei den Menüeintrag)
python3 linux/main.py     # oder direkt, von jedem Arbeitsverzeichnis aus
```

`install.sh` braucht kein `sudo` und ändert keine Cinnamon-Einstellung.
Entfernen: `./linux/install.sh --weg` (Texte und Einstellungen bleiben).
Ein zweiter Start holt das laufende Fenster nach vorn (Gtk.Application).

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

## Wo die Nutzerdaten liegen

Entschieden wird an einer Stelle, `services/pfade.py`, aus der Lage des
Programms (nie aus dem Arbeitsverzeichnis):

* **Aus dem Projektordner** (Ordner gehört dir, oder `linux/benutzer/` gibt
  es schon): alles in `linux/benutzer/` — `einstellungen.json`, `linux.json`,
  `text.txt`, `fenster-gtk.json`. Der Ordner steht in `.gitignore`: Der
  Schlüssel gelangt nie ins Repo. Beim ersten Start wird aus den alten Orten
  (`~/.config/schreibhilfe`, `~/.local/share/schreibhilfe`) **kopiert**, nie
  gelöscht.
* **Installiert** (Programmordner gehört root): XDG, siehe Tabelle oben.

Piper-Stimmen (`./stimme-holen.sh`, ~90 MB) liegen unter
`~/.local/share/schreibhilfe/piper` oder, im Projektordner, unter
`linux/benutzer/piper`.

## Aufbau

```
main.py               Einstiegspunkt (prüft GTK, startet application)
run-app.sh            Start aus dem Projektordner
install.sh            Menüeintrag im Benutzerordner (ohne Paket)
build-deb.sh          baut das Debian-Paket
debian/               Paketbeschreibung (debhelper)
packaging/            Starter, Desktop-Datei, Handbuchseite fürs Paket
application.py        Gtk.Application: Kennung, Programmname, CSS, Symbol
window.py             Hauptfenster: Stapel aus Schreib- und Einstellungsansicht
ui/editor.py          Schreibfeld (GtkSourceView): Wortstreifen, grüne Stellen, Strg+Z
ui/funde.py           Fundkarten
ui/ki_kasten.py       Für wen? / Zettel / KI-Knöpfe
ui/einstellungen.py   Einstellungsansicht
services/pfade.py     alle Pfade: Programm, Daten, Nutzerdaten (pathlib, XDG)
services/pruefung.py  die Prüfung (Abschrift des Originals, Test hält sie gleich)
daten/                Wörterliste und Regeln
benutzer/             Einstellungen und Text beim Start aus dem Ordner (nicht im Repo)
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

Ohne sichtbares Fenster (`sudo apt install xvfb`):

```bash
SCHREIBHILFE_GUI_TEST=1 GDK_BACKEND=x11 xvfb-run -a python3 -m unittest discover -s linux/tests -t linux
```

Skripte und Paket prüfen (`sudo apt install shellcheck desktop-file-utils lintian`):

```bash
shellcheck linux/build-deb.sh linux/run-app.sh linux/packaging/schreibhilfe
desktop-file-validate linux/packaging/stevie-schreibhilfe.desktop
./linux/build-deb.sh --pruefen
```

Dasselbe läuft auf GitHub in `.github/workflows/linux-deb.yml`, dort auch
Installieren, Starten und Entfernen des Pakets.

## Fehlerdiagnose

| Meldung / Verhalten | Abhilfe |
|---|---|
| „Schreibhilfe braucht GTK 3 für Python“ | `sudo apt install python3-gi gir1.2-gtk-3.0` |
| `python3 linux/main.py` scheitert an GTK, obwohl installiert | ein aktives venv ohne PyGObject — `deactivate` oder `/usr/bin/python3` nehmen; der Paket-Starter nutzt immer `/usr/bin/python3` |
| Zwei „Schreibhilfe“ im Menü | `./linux/install.sh --weg` (Eintrag aus dem Projektordner entfernen) |
| Vorlesen grau | `sudo apt install speech-dispatcher`, oder Piper mit `./stimme-holen.sh` |
| KI-Knöpfe grau | Schlüssel oder Ollama-Modell in den Einstellungen eintragen |
| `build-deb.sh`: „Es fehlt: …“ | `sudo apt install build-essential dpkg-dev debhelper librsvg2-bin python3` |

Ausgaben der App sehen: `schreibhilfe` im Terminal starten.

## Bekannte Einschränkungen

* `/opt` ist nach Debian-Policy lokaler Software vorbehalten. Das Paket ist
  für die eigene Installation gedacht, nicht fürs Debian-Archiv; lintian
  meldet das (`dir-or-file-in-opt`) und ist dafür per Override still.
* Getestet auf Ubuntu 24.04 (Container mit Xvfb); auf Linux Mint 22.3 selbst
  noch nicht, und Wayland nicht (Cinnamon läuft unter X11).

## Was sich geändert hat (Webfenster-Problem)

Die alte `linux/schreibhilfe.py` war ein GTK-Rahmen um `WebKit2.WebView`, der
einen lokalen Server startete und `online/index.html` lud — also die Webversion.
Sie ist entfernt; `run-app.sh` startet jetzt `main.py`.
