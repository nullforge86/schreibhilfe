# -*- coding: utf-8 -*-
"""Wo die Linux-Fassung ihre Dateien findet — die eine Stelle für alle Pfade.

Mitgeliefert (nur lesen), immer neben dem Programm:

    <programm>/daten/       Wörterliste und Regeln
    <programm>/resources/   Symbol, CSS

<programm> ist der Ordner linux/ im Arbeitsbaum oder, als Debian-Paket,
/opt/stevie-empire/schreibhilfe/. Beides wird aus der Lage DIESER Datei
abgeleitet, nie aus dem Arbeitsverzeichnis.

Was dieser Mensch schreibt und einstellt, liegt je nach Art des Starts:

  · aus dem Arbeitsbaum (Programmordner gehört mir und ist beschreibbar,
    oder linux/benutzer/ ist schon da): alles in linux/benutzer/ — wie bisher, nicht im Repo;
  · installiert (Programmordner gehört root oder ist schreibgeschützt):
    nach XDG getrennt — Einstellungen in ~/.config/schreibhilfe/, Text, Fenstergröße und Piper
    in ~/.local/share/schreibhilfe/. Ins Installationsverzeichnis wird nie
    geschrieben.

Die Datei „einstellungen.json“ hat dasselbe Format wie die der LibreOffice-
Erweiterung, die ~/.config/schreibhilfe/ liest; installiert teilen sich beide.
"""

import os
import shutil
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent          # …/linux bzw. /opt/stevie-empire/schreibhilfe
WURZEL = HIER.parent
RESSOURCEN = HIER / "resources"
DATEN_QUELLE = HIER / "daten"

APP_NAME = "schreibhilfe"
APP_ID = "de.schreibhilfe.App"


def _xdg(variable, vorgabe, umgebung=os.environ):
    """XDG-Ordner nach Spezifikation: nur ein absoluter Wert gilt."""
    wert = umgebung.get(variable, "")
    return Path(wert) if os.path.isabs(wert) else Path.home() / vorgabe


def waehle_orte(hier=HIER, umgebung=os.environ):
    """(Einstellungsordner, Datenordner, umgelenkt) für diesen Start.

    Die Tests lenken über SCHREIBHILFE_BENUTZER auf einen Wegwerf-Ordner um,
    damit sie nie an echte Daten kommen."""
    umgelenkt = umgebung.get("SCHREIBHILFE_BENUTZER", "")
    if os.path.isabs(umgelenkt):
        return Path(umgelenkt), Path(umgelenkt), True
    portabel = hier / "benutzer"
    # Gehört der Programmordner root, ist er installiert — auch wenn root
    # selbst startet und schreiben dürfte.
    if portabel.is_dir() or (os.access(hier, os.W_OK) and hier.stat().st_uid != 0):
        return portabel, portabel, False
    return (_xdg("XDG_CONFIG_HOME", ".config", umgebung) / APP_NAME,
            _xdg("XDG_DATA_HOME", ".local/share", umgebung) / APP_NAME, False)


EINSTELLUNGEN_ORDNER, DATEN_ORDNER, _UMGELENKT = waehle_orte()
BENUTZER = EINSTELLUNGEN_ORDNER
INSTALLIERT = EINSTELLUNGEN_ORDNER != DATEN_ORDNER

EINSTELLUNGEN_DATEI = EINSTELLUNGEN_ORDNER / "einstellungen.json"   # Schlüssel, Modell, Gedächtnis
ANSICHT_DATEI = EINSTELLUNGEN_ORDNER / "linux.json"                 # Schrift, Hell/Dunkel, Stimme
TEXT_DATEI = DATEN_ORDNER / "text.txt"                              # der Text im Feld
FENSTER_DATEI = DATEN_ORDNER / "fenster-gtk.json"

# Piper (Stimmen, ~90 MB) darf im eigenen Ordner liegen; wer es schon über
# stimme-holen.sh geholt hat, behält seinen alten Platz.
_PIPER_ALT = _xdg("XDG_DATA_HOME", ".local/share") / APP_NAME / "piper"
PIPER_ORT = (DATEN_ORDNER / "piper"
             if (DATEN_ORDNER / "piper").is_dir() or not _PIPER_ALT.is_dir()
             else _PIPER_ALT)


def uebernehme_alte_daten():
    """Holt beim ersten Start, was frühere Fassungen an anderer Stelle abgelegt
    haben: Einstellungen und Gedächtnis (~/.config/schreibhilfe), Text und
    Fenstergröße (~/.local/share/schreibhilfe). Es wird nur KOPIERT, nie
    gelöscht, und nur, was im neuen Ordner noch fehlt. Installiert sind die
    alten Orte schon die neuen — dann gibt es nichts zu holen."""
    if _UMGELENKT:
        return []
    alt = {
        EINSTELLUNGEN_DATEI: _xdg("XDG_CONFIG_HOME", ".config") / APP_NAME / "einstellungen.json",
        TEXT_DATEI: _xdg("XDG_DATA_HOME", ".local/share") / APP_NAME / "text.txt",
        FENSTER_DATEI: _xdg("XDG_DATA_HOME", ".local/share") / APP_NAME / "fenster-gtk.json",
    }
    geholt = []
    for ordner in {EINSTELLUNGEN_ORDNER, DATEN_ORDNER}:
        ordner.mkdir(mode=0o700, parents=True, exist_ok=True)
    for neu, quelle in alt.items():
        if neu != quelle and not neu.exists() and quelle.is_file():
            try:
                shutil.copy2(quelle, neu)
                neu.chmod(0o600)
                geholt.append(str(quelle))
            except OSError:
                pass
    return geholt


def schreibe_atomar(pfad, inhalt, rechte=None):
    """Erst in eine Nachbardatei, dann umbenennen: Bricht der Strom mitten im
    Schreiben ab, bleibt die alte Datei ganz — statt einer halben."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    zwischen = pfad.with_name(pfad.name + ".neu")
    zwischen.write_text(inhalt, encoding="utf-8")
    if rechte is not None:
        zwischen.chmod(rechte)
    zwischen.replace(pfad)
