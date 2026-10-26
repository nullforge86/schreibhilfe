# -*- coding: utf-8 -*-
"""Der Werkzeug-Kasten: Für wen? Worum geht's? und die drei KI-Wege."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk   # noqa: E402

from services import einstellungen as ein   # noqa: E402
from services import ki                      # noqa: E402


class KiKasten(Gtk.Expander):
    __gsignals__ = {
        "korrigieren": (GObject.SignalFlags.RUN_LAST, None, ()),
        "vorschlaege": (GObject.SignalFlags.RUN_LAST, None, ()),
        "uebersetzen": (GObject.SignalFlags.RUN_LAST, None, (str,)),
        "empfaenger-gewaehlt": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        super().__init__(label="KI-Werkzeuge")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(6)
        self.add(box)

        self.hinweis = Gtk.Label(xalign=0)
        self.hinweis.set_line_wrap(True)
        box.pack_start(self.hinweis, False, False, 0)

        # Für wen? — ein Tipp, mehr nicht: Anrede, Siezen oder Duzen, Länge.
        wer = Gtk.Box(spacing=6)
        wer.pack_start(Gtk.Label(label="Für wen?"), False, False, 0)
        self._knoepfe = {}
        erster = None
        for name in ki.EMPFAENGER:
            k = Gtk.RadioButton.new_with_label_from_widget(erster, name)
            k.set_mode(False)
            erster = erster or k
            k.connect("toggled", self._empfaenger_toggled, name)
            self._knoepfe[name] = k
            wer.pack_start(k, False, False, 0)
        box.pack_start(wer, False, False, 0)

        # Worum geht's? — gehört zum Text, nicht zum Rechner: wird nie gespeichert.
        zeile = Gtk.Box(spacing=6)
        zeile.pack_start(Gtk.Label(label="Worum geht’s? (freiwillig)"), False, False, 0)
        self.zettel = Gtk.Entry()
        self.zettel.set_max_length(ki.ZETTEL_GRENZE)
        self.zettel.set_placeholder_text("z. B. Widerspruch gegen die Kürzung — kurz und höflich")
        zeile.pack_start(self.zettel, True, True, 0)
        box.pack_start(zeile, False, False, 0)

        knoepfe = Gtk.Box(spacing=6)
        self.b_korrektur = Gtk.Button(label="KI-Korrektur")
        self.b_vorschlaege = Gtk.Button(label="Vorschläge")
        self.sprache = Gtk.ComboBoxText()
        for s in ein.SPRACHEN:
            self.sprache.append_text(s)
        self.b_uebersetzen = Gtk.Button(label="Übersetzen")
        self.b_korrektur.connect("clicked", lambda *_: self.emit("korrigieren"))
        self.b_vorschlaege.connect("clicked", lambda *_: self.emit("vorschlaege"))
        self.b_uebersetzen.connect("clicked", lambda *_: self.emit("uebersetzen", self.sprache.get_active_text() or "Englisch"))
        for w in (self.b_korrektur, self.b_vorschlaege, self.sprache, self.b_uebersetzen):
            knoepfe.pack_start(w, False, False, 0)
        box.pack_start(knoepfe, False, False, 0)
        self._sperre = False

    def _empfaenger_toggled(self, knopf, name):
        if knopf.get_active() and not self._sperre:
            self.emit("empfaenger-gewaehlt", name)

    def lade(self, werte):
        """Stellt den Kasten auf die gespeicherten Werte und sagt, ob die KI geht."""
        self._sperre = True
        self._knoepfe.get(werte["empfaenger"], self._knoepfe["egal"]).set_active(True)
        self._sperre = False
        try:
            self.sprache.set_active(ein.SPRACHEN.index(werte["sprache"]))
        except ValueError:
            self.sprache.set_active(0)
        bereit = ki.ki_bereit(werte)
        lokal = ki.ist_lokal(werte["modell"])
        for w in (self.b_korrektur, self.b_vorschlaege, self.b_uebersetzen, self.sprache):
            w.set_sensitive(bereit)
        if not bereit:
            self.hinweis.set_text("Braucht einen API-Schlüssel (oder Ollama) — oben rechts unter Einstellungen.")
        elif lokal:
            self.hinweis.set_text("Bleibt auf diesem Rechner (Ollama).")
        else:
            self.hinweis.set_text("Braucht Internet: Der Text geht an Anthropic.")

    def sperre(self, an):
        for w in (self.b_korrektur, self.b_vorschlaege, self.b_uebersetzen, self.sprache):
            w.set_sensitive(not an)
