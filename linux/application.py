# -*- coding: utf-8 -*-
"""GTK-Initialisierung: eine Anwendung, ein Fenster.

Gtk.Application sorgt für den zweiten Start von selbst: Läuft die Schreibhilfe
schon, holt er das vorhandene Fenster nach vorn, statt ein zweites zu öffnen.
Beim Beenden ist die Kennung wieder frei — der nächste Start kommt zuverlässig.
"""

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk   # noqa: E402

from services import pfade   # noqa: E402

# Der Name, unter dem Cinnamon das Fenster dem Menüeintrag zuordnet
# (StartupWMClass=schreibhilfe in der .desktop-Datei). Ohne diese Zeilen
# hieße das Fenster „main.py“, und in der Leiste stünde das Programm zweimal.
GLib.set_prgname(pfade.APP_NAME)
GLib.set_application_name("Schreibhilfe")
Gdk.set_program_class(pfade.APP_NAME)


class Schreibhilfe(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=pfade.APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.fenster = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        pfade.uebernehme_alte_daten()
        self._symbole_einrichten()
        self._css_laden()
        beenden = Gio.SimpleAction.new("quit", None)
        beenden.connect("activate", lambda *_: self.fenster and self.fenster.close())
        self.add_action(beenden)
        self.set_accels_for_action("app.quit", ["<Primary>q"])

    def do_activate(self):
        if self.fenster is None:
            from window import Hauptfenster          # erst hier: braucht ein laufendes GTK
            self.fenster = Hauptfenster(self)
        self.fenster.present()

    def _symbole_einrichten(self):
        """Läuft die App aus dem Projektordner und ist noch nicht installiert,
        kennt das Theme das Symbol „schreibhilfe“ nicht — dann aus dem Ordner."""
        theme = Gtk.IconTheme.get_default()
        if not theme.has_icon("schreibhilfe"):
            theme.append_search_path(pfade.RESSOURCEN)
        png = os.path.join(pfade.RESSOURCEN, "schreibhilfe.png")
        if os.path.isfile(png):
            try:
                Gtk.Window.set_default_icon_from_file(png)
            except GLib.Error:
                pass

    def _css_laden(self):
        css = Gtk.CssProvider()
        try:
            css.load_from_path(os.path.join(pfade.RESSOURCEN, "schreibhilfe.css"))
        except GLib.Error as fehler:
            print("Die Gestaltung fehlt (%s) — es geht ohne." % fehler.message, file=sys.stderr)
            return
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def starten(argv=None):
    return Schreibhilfe().run(argv if argv is not None else sys.argv)
