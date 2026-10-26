# -*- coding: utf-8 -*-
"""Die Fundkarten: was geändert würde und warum. Nichts ändert sich von allein."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango   # noqa: E402

SORTEN = {"tipp": "Kommt drauf an", "hinweis": "Zum Nachdenken", "vorschlag": "Vorschlag"}


def kuerze(satz, hoechstens=70):
    return satz if len(satz) <= hoechstens else satz[:hoechstens].rstrip() + " …"


def zeige_leer(text):
    """Leerzeichen sichtbar machen, damit „zwei Leerzeichen → eins“ lesbar ist."""
    return text.replace(" ", "␣") if text.strip() == "" else text


def _label(text, *klassen, wrap=True):
    l = Gtk.Label(label=text)
    l.set_xalign(0)
    l.set_line_wrap(wrap)
    l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    l.set_selectable(False)
    for k in klassen:
        l.get_style_context().add_class(k)
    return l


class FundeListe(Gtk.ScrolledWindow):
    def __init__(self, bei_aendern):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_shadow_type(Gtk.ShadowType.NONE)
        self.set_min_content_height(0)
        self.set_propagate_natural_height(True)
        self.set_max_content_height(260)
        self.kasten = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.kasten.set_margin_start(2)
        self.kasten.set_margin_end(6)
        self.add(self.kasten)
        self._bei_aendern = bei_aendern

    def leeren(self):
        for kind in self.kasten.get_children():
            self.kasten.remove(kind)
        self.set_visible(False)

    def hat_aenderbares(self):
        return any(k.aenderbar for k in self.kasten.get_children() if hasattr(k, "aenderbar"))

    def zeichne(self, funde):
        self.leeren()
        for fund in funde:
            self.kasten.pack_start(self._karte(fund), False, False, 0)
        self.kasten.show_all()
        self.set_visible(bool(funde))
        self.get_vadjustment().set_value(0)

    def _karte(self, fund):
        art = fund.get("art", "fehler")
        karte = Gtk.Box(spacing=10)
        karte.aenderbar = art != "hinweis"
        ctx = karte.get_style_context()
        ctx.add_class("fund")
        ctx.add_class("fund-" + art)

        inhalt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        # Die Sorte steht als Wort da — eine Farbe allein müsste man erst lernen.
        inhalt.pack_start(_label(SORTEN.get(art, "Sicher falsch"), "fund-sorte"), False, False, 0)

        if art == "hinweis":
            if fund.get("stelle"):
                inhalt.pack_start(_label("„" + kuerze(fund["stelle"]) + "“"), False, False, 0)
        elif art == "vorschlag":
            inhalt.pack_start(_label(fund["alt"], "fund-satz-alt"), False, False, 0)
            inhalt.pack_start(_label(fund["neu"], "fund-satz-neu"), False, False, 0)
        else:
            zeile = Gtk.Box(spacing=8)
            zeile.pack_start(_label(zeige_leer(fund["alt"]), "fund-falsch", wrap=False), False, False, 0)
            zeile.pack_start(Gtk.Label(label="→"), False, False, 0)
            zeile.pack_start(_label(zeige_leer(fund["neu"]), "fund-richtig", wrap=False), False, False, 0)
            inhalt.pack_start(zeile, False, False, 0)
        inhalt.pack_start(_label(fund.get("grund", ""), "fund-grund"), False, False, 0)
        karte.pack_start(inhalt, True, True, 0)

        if karte.aenderbar:
            knopf = Gtk.Button.new_with_mnemonic("_Nehmen" if art == "vorschlag" else "_Ändern")
            knopf.set_image(Gtk.Image.new_from_icon_name("object-select-symbolic", Gtk.IconSize.BUTTON))
            knopf.set_always_show_image(True)
            knopf.set_valign(Gtk.Align.CENTER)
            knopf.get_style_context().add_class("suggested-action")
            knopf.connect("clicked", lambda *_a, f=fund: self._bei_aendern(f))
            karte.pack_end(knopf, False, False, 0)
        return karte
