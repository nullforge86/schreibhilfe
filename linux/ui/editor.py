# -*- coding: utf-8 -*-
"""Das Schreibfeld: ein echtes GTK-Textfeld mit Rückgängig, Wortstreifen und
grüner Anzeige der zuletzt geänderten Stellen."""

import re

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GObject, Gtk   # noqa: E402

try:
    gi.require_version("GtkSource", "3.0")
    from gi.repository import GtkSource
except (ValueError, ImportError):                          # pragma: no cover
    GtkSource = None

WORT_ZEICHEN = re.compile(r"[A-Za-zÄÖÜäöüß0-9'’-]")


class Schreibfeld(Gtk.Overlay):
    __gsignals__ = {
        # Der MENSCH hat getippt (nicht die App).
        "getippt": (GObject.SignalFlags.RUN_LAST, None, ()),
        # Der Zeiger hat sich bewegt oder der Text geändert — Wortleiste auffrischen.
        "lage-geaendert": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self):
        super().__init__()
        if GtkSource:
            self.puffer = GtkSource.Buffer()
            self.puffer.set_max_undo_levels(200)
            self.ansicht = GtkSource.View.new_with_buffer(self.puffer)
        else:
            self.puffer = Gtk.TextBuffer()
            self.ansicht = Gtk.TextView.new_with_buffer(self.puffer)
        self.ansicht.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.ansicht.set_left_margin(12)
        self.ansicht.set_right_margin(12)
        self.ansicht.set_top_margin(10)
        self.ansicht.set_bottom_margin(10)
        self.ansicht.set_accepts_tab(False)
        self.ansicht.set_pixels_below_lines(3)
        self.ansicht.get_accessible().set_name("Dein Text")

        rolle = Gtk.ScrolledWindow()
        rolle.set_shadow_type(Gtk.ShadowType.IN)
        rolle.add(self.ansicht)
        self.add(rolle)

        self.platzhalter = Gtk.Label(label="Hier schreiben oder diktieren.")
        self.platzhalter.set_halign(Gtk.Align.START)
        self.platzhalter.set_valign(Gtk.Align.START)
        self.platzhalter.set_margin_start(14)
        self.platzhalter.set_margin_top(10)
        self.platzhalter.get_style_context().add_class("dim-label")
        self.add_overlay(self.platzhalter)
        self.set_overlay_pass_through(self.platzhalter, True)

        self.marker = self.puffer.create_tag("marker", background_rgba=Gdk.RGBA(0.35, 0.55, 0.95, 0.22))
        self.gruen = self.puffer.create_tag("neu", background_rgba=Gdk.RGBA(0.12, 0.56, 0.24, 0.30))
        self._intern = 0            # >0, solange die App selbst den Text setzt
        self._markiere = True
        self._schrift_css = Gtk.CssProvider()
        self.ansicht.get_style_context().add_provider(
            self._schrift_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.set_schrift(1.0)

        self.puffer.connect("changed", self._geaendert)
        self.puffer.connect("notify::cursor-position", lambda *a: self._lage())
        self.ansicht.connect("focus-in-event", lambda *a: self._lage() or False)

    # ---------------------------------------------------------------- Text
    def get_text(self):
        return self.puffer.get_text(self.puffer.get_start_iter(), self.puffer.get_end_iter(), True)

    def set_text(self, text, als_eine_aenderung=True):
        """Setzt den Text von Programms wegen (Löschen, Ändern, KI). Löst
        'getippt' nicht aus und lässt sich mit Strg+Z zurücknehmen."""
        self._intern += 1
        try:
            if als_eine_aenderung:
                self.puffer.begin_user_action()
            self.puffer.set_text(text)
            if als_eine_aenderung:
                self.puffer.end_user_action()
        finally:
            self._intern -= 1
        self.platzhalter.set_visible(not text)
        self.entferne_gruen()
        self._lage()

    def ersetze(self, von, bis, neu):
        """Ersetzt ein Stück (Zeichenstellen) im Text, ohne 'getippt'."""
        self._intern += 1
        try:
            self.puffer.begin_user_action()
            a = self.puffer.get_iter_at_offset(von)
            b = self.puffer.get_iter_at_offset(bis)
            self.puffer.delete(a, b)
            self.puffer.insert(self.puffer.get_iter_at_offset(von), neu)
            self.puffer.end_user_action()
        finally:
            self._intern -= 1
        self.platzhalter.set_visible(not self.get_text())

    def fokus(self):
        self.ansicht.grab_focus()

    def _geaendert(self, *_):
        self.platzhalter.set_visible(self.puffer.get_char_count() == 0)
        if not self._intern:
            self.entferne_gruen()
            self.emit("getippt")
        self._lage()

    # --------------------------------------------------------------- Grün
    def zeige_gruen(self, stellen):
        self.entferne_gruen()
        for st in stellen:
            self.puffer.apply_tag(self.gruen, self.puffer.get_iter_at_offset(st["von"]),
                                  self.puffer.get_iter_at_offset(st["bis"]))

    def entferne_gruen(self):
        self.puffer.remove_tag(self.gruen, self.puffer.get_start_iter(), self.puffer.get_end_iter())

    # ------------------------------------------------------ Wort am Zeiger
    def setze_markierung(self, an):
        self._markiere = an
        self._lage()

    def wort_am_zeiger(self):
        """(von, bis, wort) des Wortes links vom Zeiger — nur am Wortende, ohne
        Auswahl; sonst None."""
        if self.puffer.get_has_selection():
            return None
        text = self.get_text()
        bis = self.puffer.get_iter_at_mark(self.puffer.get_insert()).get_offset()
        if bis < len(text) and WORT_ZEICHEN.match(text[bis]):
            return None
        von = bis
        while von > 0 and WORT_ZEICHEN.match(text[von - 1]):
            von -= 1
        if bis - von < 3:
            return None
        return von, bis, text[von:bis]

    def _lage(self):
        self.puffer.remove_tag(self.marker, self.puffer.get_start_iter(), self.puffer.get_end_iter())
        if self._markiere and self.ansicht.has_focus():
            text = self.get_text()
            stelle = self.puffer.get_iter_at_mark(self.puffer.get_insert()).get_offset()
            von = bis = stelle
            while von > 0 and WORT_ZEICHEN.match(text[von - 1]):
                von -= 1
            while bis < len(text) and WORT_ZEICHEN.match(text[bis]):
                bis += 1
            if bis > von:
                self.puffer.apply_tag(self.marker, self.puffer.get_iter_at_offset(von),
                                      self.puffer.get_iter_at_offset(bis))
        self.emit("lage-geaendert")

    # --------------------------------------------------------------- Schrift
    def set_schrift(self, faktor):
        self._schrift_css.load_from_data(
            ("textview { font-size: %.1fpt; }" % (13 * faktor)).encode("utf-8"))
        self.schrift = faktor
