# -*- coding: utf-8 -*-
"""Wo die Linux-Fassung ihre Dateien findet.

ALLES liegt im Ordner linux/ — Programm, Wörterliste, Regeln und das, was dieser
Mensch schreibt und einstellt:

    linux/daten/      Wörterliste und Regeln (mitgeliefert)
    linux/benutzer/   Einstellungen, Schlüssel, Text, Fenstergröße (nicht im Repo)

Die Datei „einstellungen.json“ hat dasselbe Format wie die der LibreOffice-
Erweiterung; wer beide Programme teilen will, kopiert sie hinüber.
"""

import os
import shutil

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # …/linux
WURZEL = os.path.dirname(HIER)
RESSOURCEN = os.path.join(HIER, "resources")
DATEN_QUELLE = os.path.join(HIER, "daten")

APP_NAME = "schreibhilfe"
APP_ID = "de.schreibhilfe.App"

# Die Tests lenken das auf einen Wegwerf-Ordner um, damit sie nie an echte Daten kommen.
_UMGELENKT = os.environ.get("SCHREIBHILFE_BENUTZER", "")
BENUTZER = _UMGELENKT if os.path.isabs(_UMGELENKT) else os.path.join(HIER, "benutzer")

EINSTELLUNGEN_ORDNER = BENUTZER
EINSTELLUNGEN_DATEI = os.path.join(BENUTZER, "einstellungen.json")   # Schlüssel, Modell, Gedächtnis
ANSICHT_DATEI = os.path.join(BENUTZER, "linux.json")                 # Schrift, Hell/Dunkel, Stimme
DATEN_ORDNER = BENUTZER
TEXT_DATEI = os.path.join(BENUTZER, "text.txt")                      # der Text im Feld
FENSTER_DATEI = os.path.join(BENUTZER, "fenster-gtk.json")

# Piper (Stimmen, ~90 MB) darf im eigenen Ordner liegen; wer es schon über
# stimme-holen.sh geholt hat, behält seinen alten Platz.
_PIPER_ALT = os.path.expanduser("~/.local/share/schreibhilfe/piper")
PIPER_ORT = (os.path.join(BENUTZER, "piper")
             if os.path.isdir(os.path.join(BENUTZER, "piper")) or not os.path.isdir(_PIPER_ALT)
             else _PIPER_ALT)


def _xdg(variable, vorgabe):
    wert = os.environ.get(variable, "")
    return wert if os.path.isabs(wert) else os.path.expanduser(vorgabe)


def uebernehme_alte_daten():
    """Holt beim ersten Start, was frühere Fassungen an anderer Stelle abgelegt
    haben: Einstellungen und Gedächtnis (~/.config/schreibhilfe), Text und
    Fenstergröße (~/.local/share/schreibhilfe). Es wird nur KOPIERT, nie
    gelöscht, und nur, was im neuen Ordner noch fehlt."""
    if _UMGELENKT:
        return []
    alt = {
        EINSTELLUNGEN_DATEI: os.path.join(_xdg("XDG_CONFIG_HOME", "~/.config"), APP_NAME, "einstellungen.json"),
        TEXT_DATEI: os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), APP_NAME, "text.txt"),
        FENSTER_DATEI: os.path.join(_xdg("XDG_DATA_HOME", "~/.local/share"), APP_NAME, "fenster-gtk.json"),
    }
    geholt = []
    os.makedirs(BENUTZER, mode=0o700, exist_ok=True)
    for neu, quelle in alt.items():
        if not os.path.exists(neu) and os.path.isfile(quelle):
            try:
                shutil.copy2(quelle, neu)
                os.chmod(neu, 0o600)
                geholt.append(quelle)
            except OSError:
                pass
    return geholt


def schreibe_atomar(pfad, inhalt, rechte=None):
    """Erst in eine Nachbardatei, dann umbenennen: Bricht der Strom mitten im
    Schreiben ab, bleibt die alte Datei ganz — statt einer halben."""
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    zwischen = pfad + ".neu"
    with open(zwischen, "w", encoding="utf-8") as datei:
        datei.write(inhalt)
    if rechte is not None:
        os.chmod(zwischen, rechte)
    os.replace(zwischen, pfad)
