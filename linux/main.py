#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Einstiegspunkt der nativen Linux-Fassung (GTK 3, kein Browser, kein Server)."""

import sys
from pathlib import Path

# Die Module liegen neben dieser Datei; der Aufruf soll von überall gehen —
# auch über einen Symlink wie /usr/bin/schreibhilfe, deshalb resolve().
HIER = Path(__file__).resolve().parent
if str(HIER) not in sys.path:
    sys.path.insert(0, str(HIER))


def pruefe_umgebung():
    """Fehlt etwas, eine verständliche Meldung statt eines Python-Tracebacks."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk                    # noqa: F401
    except (ImportError, ValueError) as fehler:
        sys.stderr.write(
            "Schreibhilfe braucht GTK 3 für Python. Bitte installieren:\n"
            "    sudo apt install python3-gi gir1.2-gtk-3.0\n(%s)\n" % fehler)
        return False
    return True


def main():
    if not pruefe_umgebung():
        return 1
    from application import starten
    return starten()


if __name__ == "__main__":
    sys.exit(main())
