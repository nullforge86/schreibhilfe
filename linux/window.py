# -*- coding: utf-8 -*-
"""Das Hauptfenster: Schreibfeld, Wortleiste, Fundkarten, KI-Kasten, Knöpfe.

Die Verarbeitung liegt in services/ — dieses Fenster verbindet nur. Alles, was
warten kann (KI, Vorlesen, Ollama-Liste), läuft in Hintergrundfäden und meldet
sich über GLib.idle_add zurück; der Hauptfaden bleibt frei.
"""

import json
import os
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk   # noqa: E402

from services import einstellungen as ein            # noqa: E402
from services import klang, ki, pfade, pruefung, vorlesen   # noqa: E402
from ui.editor import Schreibfeld                      # noqa: E402
from ui.einstellungen import EinstellungenSeite   # noqa: E402
from ui.funde import FundeListe                         # noqa: E402
from ui.ki_kasten import KiKasten                       # noqa: E402

FASSUNG = "Schreibhilfe 1.0 — Linux"


def _zusammenfassung(funde):
    hinweise = sum(1 for f in funde if f["art"] == "hinweis")
    aendern = len(funde) - hinweise
    teile = []
    if aendern:
        teile.append("1 Stelle zum Ändern" if aendern == 1 else "%d Stellen zum Ändern" % aendern)
    if hinweise:
        teile.append("1 Hinweis zum Satzbau" if hinweise == 1 else "%d Hinweise zum Satzbau" % hinweise)
    return " · ".join(teile) + "."


class Hauptfenster(Gtk.ApplicationWindow):
    def __init__(self, anwendung):
        super().__init__(application=anwendung, title="Schreibhilfe")
        self.set_icon_name("schreibhilfe")
        self.werte = ein.lies_einstellungen(empfaenger_namen=ki.EMPFAENGER)
        self.ansicht = ein.lies_ansicht()
        self._system_dunkel = Gtk.Settings.get_default().get_property("gtk-application-prefer-dark-theme")

        self.vorheriger_text = None       # Stand vor der letzten Änderung der App
        self.vorheriger_zettel = None
        self.zurueck_im_eimer = False     # „Löschen“ ist gerade ein Rückholpfeil
        self.ki_liste = None              # Vorschläge der KI, solange sie angezeigt werden
        self.gruen = []                   # Stellen der übernommenen Änderungen
        self._speicher_uhr = 0
        self._wort_uhr = 0
        self._beschaeftigt = False

        # Die Größe zuerst: Nach dem ersten Anzeigen ignoriert das Fenster sie.
        self._geometrie_laden()
        self._baue_kopfleiste()
        self._baue_inhalt()
        self._baue_aktionen()

        self.connect("delete-event", self._beim_schliessen)
        self.connect("key-press-event", self._taste)
        self._ansicht_anwenden()
        self.kasten.lade(self.werte)
        self._text_laden()
        klang.klangtafel_im_hintergrund()

    # ------------------------------------------------------------------ Bau
    def _baue_kopfleiste(self):
        """Klassisch, wie es zu Cinnamon passt: Titelleiste und Rahmen zeichnet
        der Fenstermanager (Muffin) im gewählten Theme; darunter Menüleiste und
        Werkzeugleiste — keine GNOME-Kopfleiste."""
        self.oben = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        menue = Gio.Menu()
        datei = Gio.Menu()
        datei.append("Text aus Datei _öffnen …", "win.oeffnen")
        datei.append("Text als Datei _speichern …", "win.speichern")
        datei.append("_Beenden", "app.quit")
        bearbeiten = Gio.Menu()
        bearbeiten.append("_Prüfen", "win.pruefen")
        bearbeiten.append("_Alles Eindeutige ändern", "win.alles")
        bearbeiten.append("_Einstellungen", "win.einstellungen")
        hilfe = Gio.Menu()
        hilfe.append("_Über Schreibhilfe", "win.ueber")
        menue.append_submenu("_Datei", datei)
        menue.append_submenu("_Bearbeiten", bearbeiten)
        menue.append_submenu("_Hilfe", hilfe)
        self.oben.pack_start(Gtk.MenuBar.new_from_model(menue), False, False, 0)

        leiste = Gtk.Toolbar()
        leiste.set_style(Gtk.ToolbarStyle.BOTH_HORIZ)

        def knopf(icon, text, tipp, fn=None, aktion=None):
            k = Gtk.ToolButton()
            k.set_icon_name(icon)
            k.set_label(text)
            k.set_is_important(True)
            k.set_tooltip_text(tipp)
            if aktion:
                k.set_action_name(aktion)
            else:
                k.connect("clicked", fn)
            leiste.insert(k, -1)
            return k

        self.b_einfuegen = knopf("edit-paste", "Einfügen",
                                 "Text aus der Zwischenablage einfügen und prüfen", self._einfuegen)
        self.b_kopieren = knopf("edit-copy", "Kopieren", "Ganzen Text kopieren", self._kopieren)
        # Nur sichtbar, wenn dieser Rechner überhaupt sprechen kann: ein toter
        # Knopf ist schlimmer als keiner.
        self.b_vorlesen = knopf("audio-volume-high", "Vorlesen",
                                "Text vorlesen — das Ohr stolpert über Fehler", self._vorlesen_umschalten)
        self.b_vorlesen.set_no_show_all(True)
        self.b_vorlesen.set_visible(vorlesen.kann_vorlesen())
        trenner = Gtk.SeparatorToolItem()
        trenner.set_draw(False)
        trenner.set_expand(True)
        leiste.insert(trenner, -1)
        knopf("preferences-system", "Einstellungen", "Einstellungen (Strg+,)", aktion="win.einstellungen")
        self.oben.pack_start(leiste, False, False, 0)

    def _baue_inhalt(self):
        # Ein Fenster, zwei Ansichten: Schreiben und Einstellungen tauschen
        # den Platz — die Einstellungen sind kein zweites Fenster.
        self.stapel = Gtk.Stack()
        self.stapel.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stapel.set_transition_duration(120)
        self.add(self.stapel)
        wurzel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.schreibseite = wurzel
        self.einstellungsseite = None
        self.stapel.add_named(wurzel, "schreiben")
        wurzel.pack_start(self.oben, False, False, 0)
        haupt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for r in ("top", "bottom", "start", "end"):
            getattr(haupt, "set_margin_" + r)(8)
        wurzel.pack_start(haupt, True, True, 0)

        self.feld = Schreibfeld()
        self.feld.connect("getippt", self._getippt)
        self.feld.connect("lage-geaendert", self._lage_geaendert)
        haupt.pack_start(self.feld, True, True, 0)

        # Wortleiste: „Weiter mit“ oder „Meintest du“
        self.leiste = Gtk.Box(spacing=6)
        self.leiste.get_style_context().add_class("wortleiste")
        self.leiste.set_no_show_all(True)
        haupt.pack_start(self.leiste, False, False, 0)

        self.funde = FundeListe(self._uebernimm)
        self.funde.set_no_show_all(True)
        haupt.pack_start(self.funde, False, False, 0)

        stand = Gtk.Box(spacing=6)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_selectable(True)
        stand.pack_start(self.status, True, True, 0)
        self.zaehler = Gtk.Label(xalign=1)
        self.zaehler.get_style_context().add_class("dim-label")
        stand.pack_end(self.zaehler, False, False, 0)
        haupt.pack_start(stand, False, False, 0)

        reihe = Gtk.Box(spacing=6)
        self.b_pruefen = Gtk.Button.new_with_mnemonic("_Prüfen")
        self.b_pruefen.set_image(Gtk.Image.new_from_icon_name("tools-check-spelling-symbolic", Gtk.IconSize.BUTTON))
        self.b_pruefen.set_always_show_image(True)
        self.b_pruefen.get_style_context().add_class("suggested-action")
        self.b_pruefen.set_tooltip_text("Zeigt jeden Fund als Karte (Strg+Eingabe)")
        self.b_pruefen.connect("clicked", lambda *_: self.pruefen())
        self.b_alles = Gtk.Button.new_with_mnemonic("_Alles ändern")
        self.b_alles.set_tooltip_text("Wendet alles Eindeutige auf einmal an; die Stellen leuchten grün")
        self.b_alles.connect("clicked", lambda *_: self.alles_aendern())
        self.b_zurueck = Gtk.Button.new_with_mnemonic("_Rückgängig")
        self.b_zurueck.connect("clicked", lambda *_: self.zurueckholen())
        self.b_leeren = Gtk.Button.new_with_mnemonic("_Löschen")
        self.b_leeren.get_style_context().add_class("destructive-action")
        self.b_leeren.connect("clicked", self._leeren_oder_zurueck)
        reihe.pack_start(self.b_pruefen, False, False, 0)
        reihe.pack_start(self.b_alles, False, False, 0)
        reihe.pack_start(self.b_zurueck, False, False, 0)
        reihe.pack_end(self.b_leeren, False, False, 0)
        haupt.pack_start(reihe, False, False, 0)

        self.kasten = KiKasten()
        self.kasten.connect("korrigieren", self._ki_korrigieren)
        self.kasten.connect("vorschlaege", self._ki_vorschlaege)
        self.kasten.connect("uebersetzen", self._ki_uebersetzen)
        self.kasten.connect("empfaenger-gewaehlt", self._empfaenger_gewaehlt)
        haupt.pack_start(self.kasten, False, False, 0)

        self.b_zurueck.set_no_show_all(True)
        self.stapel.show()
        wurzel.show_all()
        self.b_zurueck.set_visible(False)

    def _baue_aktionen(self):
        def aktion(name, fn, *tasten):
            a = Gio.SimpleAction.new(name, None)
            # In der Einstellungs-Ansicht ruht alles andere.
            a.connect("activate", lambda *_: fn() if name == "einstellungen" or not self.einstellungsseite else None)
            self.add_action(a)
            for t in tasten:
                self.get_application().set_accels_for_action("win." + name, [t])
        aktion("einstellungen", self.einstellungen_oeffnen, "<Primary>comma")
        aktion("ueber", self.ueber_zeigen)
        aktion("oeffnen", self.datei_oeffnen, "<Primary>o")
        aktion("speichern", self.datei_speichern, "<Primary>s")
        aktion("pruefen", self.pruefen, "<Primary>Return")
        aktion("alles", self.alles_aendern, "<Primary><Shift>Return")

    # ---------------------------------------------------------------- Ansicht
    def _ansicht_anwenden(self):
        self.feld.set_schrift(self.ansicht["schrift"])
        self.feld.setze_markierung(self.ansicht["wortmarker"])
        einst = Gtk.Settings.get_default()
        t = self.ansicht["thema"]
        einst.set_property("gtk-application-prefer-dark-theme",
                           True if t == "dunkel" else False if t == "hell" else self._system_dunkel)

    def _bei_ansicht(self, **aenderung):
        self.ansicht.update(aenderung)
        self._ansicht_anwenden()
        try:
            ein.schreib_ansicht(self.ansicht)
        except OSError as fehler:
            self.melde("Die Ansicht ließ sich nicht speichern: %s" % fehler)

    # ------------------------------------------------------------------- Text
    def _text_laden(self):
        try:
            with open(pfade.TEXT_DATEI, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = ""
        self.feld.set_text(text, als_eine_aenderung=False)
        self._aktualisiere_knoepfe()
        self.feld.fokus()

    def _text_speichern(self):
        self._speicher_uhr = 0
        try:
            pfade.schreibe_atomar(pfade.TEXT_DATEI, self.feld.get_text())
        except OSError as fehler:
            self.melde("Der Text ließ sich nicht sichern: %s" % fehler)
        return False

    def _getippt(self, *_):
        # Wer weiterschreibt, wirft den Rückholstand weg: Er stammt von vorher,
        # und ihn zurückzuholen würde das Neugeschriebene vernichten.
        self._vergiss_zurueck()
        self.ki_liste = None
        self.gruen = []
        if self._speicher_uhr:
            GLib.source_remove(self._speicher_uhr)
        self._speicher_uhr = GLib.timeout_add(600, self._text_speichern)
        self._aktualisiere_knoepfe()

    def _aktualisiere_knoepfe(self):
        text = self.feld.get_text()
        woerter = len(text.split())
        self.zaehler.set_text("" if not woerter else "1 Wort" if woerter == 1 else "%d Wörter" % woerter)
        leer = not text.strip()
        for b in (self.b_pruefen, self.b_alles, self.b_kopieren, self.b_vorlesen):
            b.set_sensitive(not leer and not self._beschaeftigt)
        pfeil = self.zurueck_im_eimer and self.vorheriger_text is not None
        self.b_leeren.set_label("_Zurückholen" if pfeil else "_Löschen")
        self.b_leeren.set_use_underline(True)
        self.b_leeren.set_sensitive(bool(text) or pfeil)
        self.b_zurueck.set_visible(self.vorheriger_text is not None and not self.zurueck_im_eimer)
        self.b_einfuegen.set_sensitive(not self._beschaeftigt)

    def melde(self, text, gut=False):
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        (ctx.add_class if gut else ctx.remove_class)("status-gut")

    # ------------------------------------------------------ Rückgängig, Löschen
    def _merke_fuer_zurueck(self, text, im_eimer=False):
        self.vorheriger_text = text
        self.vorheriger_zettel = self.kasten.zettel.get_text() if im_eimer else None
        self.zurueck_im_eimer = im_eimer

    def _vergiss_zurueck(self):
        self.vorheriger_text = None
        self.vorheriger_zettel = None
        self.zurueck_im_eimer = False

    def zurueckholen(self):
        if self.vorheriger_text is None:
            return
        if self.vorheriger_zettel:
            self.kasten.zettel.set_text(self.vorheriger_zettel)
        text = self.vorheriger_text
        self._vergiss_zurueck()
        self.feld.set_text(text)
        self.funde.leeren()
        self.ki_liste = None
        self.gruen = []
        self.melde("")
        self._text_speichern()
        self._aktualisiere_knoepfe()
        self.feld.fokus()

    def _leeren_oder_zurueck(self, *_):
        if self.zurueck_im_eimer and self.vorheriger_text is not None:
            self.zurueckholen()
            return
        text = self.feld.get_text()
        if not text:
            return
        self._merke_fuer_zurueck(text, im_eimer=True)
        self.feld.set_text("")
        self.kasten.zettel.set_text("")          # der Zettel gehört zum Text
        self.funde.leeren()
        self.ki_liste = None
        self.gruen = []
        self.melde("Text gelöscht. „Zurückholen“ bringt ihn wieder.")
        self._text_speichern()
        self._aktualisiere_knoepfe()

    # ------------------------------------------------------------------ Prüfen
    def _gelernt(self):
        return ein.gelernt_fuer_pruefung(self.werte)

    def _werte_sichern(self):
        try:
            ein.schreib_einstellungen(self.werte)
        except OSError as fehler:
            self.melde("Die Einstellungen ließen sich nicht speichern: %s" % fehler)

    def pruefen(self):
        self.ki_liste = None
        self.funde.leeren()
        text = self.feld.get_text()
        if not text.strip():
            self.melde("Es steht noch kein Text da.")
            return
        try:
            funde = pruefung.finde_probleme(text, self._gelernt())
        except Exception as fehler:                       # noqa: BLE001
            self.melde("Die Prüfung ist fehlgeschlagen: %s" % fehler)
            return
        if not funde:
            self.melde("Nichts gefunden.")
        else:
            self.funde.zeichne(funde)
            self.melde(_zusammenfassung(funde))
            if ein.merke_gezeigt(funde, self.werte):
                self._werte_sichern()
        self._aktualisiere_knoepfe()

    def alles_aendern(self):
        """Alles Eindeutige auf einmal; die geänderten Stellen leuchten grün."""
        text = self.feld.get_text()
        if not text.strip():
            self.melde("Es steht noch nichts da.")
            return
        funde = sorted((f for f in pruefung.finde_probleme(text, self._gelernt())
                        if f["art"] != "hinweis" and f["alt"] and f["neu"]),
                       key=lambda f: f["von"])
        ergebnis, versatz, stellen = text, 0, []
        for f in funde:
            von, bis = f["von"] + versatz, f["bis"] + versatz
            if ergebnis[von:bis] != f["alt"]:
                continue
            ergebnis = ergebnis[:von] + f["neu"] + ergebnis[bis:]
            stellen.append({"von": von, "bis": von + len(f["neu"])})
            versatz += len(f["neu"]) - len(f["alt"])
        hinweise = [f for f in pruefung.finde_probleme(ergebnis, self._gelernt()) if f["art"] == "hinweis"]
        self.funde.leeren()
        if stellen:
            self._merke_fuer_zurueck(text)
            self.feld.set_text(ergebnis)
            self.gruen = stellen
            self.feld.zeige_gruen(stellen)
            self._text_speichern()
        if hinweise:
            self.funde.zeichne(hinweise)
        self.melde("Nichts zu ändern." if not stellen and hinweise else
                   "Alles in Ordnung." if not stellen else
                   "1 Stelle verbessert" if len(stellen) == 1 else "%d Stellen verbessert" % len(stellen),
                   gut=bool(stellen))
        self._aktualisiere_knoepfe()

    def _uebernimm(self, fund):
        jetzt = self.feld.get_text()
        if jetzt[fund["von"]:fund["bis"]] != fund["alt"]:          # Stelle passt nicht mehr
            self._neu_zeichnen()
            return
        # Die einzige Stelle, an der zweifelsfrei feststeht, was der Mensch wollte.
        if ein.merke_aenderung(fund, self.werte):
            self._werte_sichern()
        self._merke_fuer_zurueck(jetzt)
        self.feld.ersetze(fund["von"], fund["bis"], fund["neu"])
        versatz = len(fund["neu"]) - len(fund["alt"])
        self.gruen = sorted(
            [({"von": s["von"] + versatz, "bis": s["bis"] + versatz} if s["von"] >= fund["bis"] else s)
             for s in self.gruen] + [{"von": fund["von"], "bis": fund["von"] + len(fund["neu"])}],
            key=lambda s: s["von"])
        self.feld.zeige_gruen(self.gruen)
        if self.ki_liste is not None:
            self.ki_liste = [v for v in self.ki_liste if v is not fund]
        self._neu_zeichnen()
        self._text_speichern()
        self._aktualisiere_knoepfe()

    def _neu_zeichnen(self):
        if self.ki_liste is not None:
            self._zeige_ki_liste()
        else:
            gruen = list(self.gruen)
            self.pruefen()
            self.gruen = gruen

    def _zeige_ki_liste(self):
        """Die Vorschläge der KI suchen ihre Stellen selbst: Nach jeder
        Änderung sitzen die übrigen woanders. Was sich nicht mehr wörtlich
        findet, fällt still weg."""
        text = self.feld.get_text()
        liste = []
        for v in self.ki_liste or []:
            von = text.find(v["alt"])
            if von == -1:
                continue
            v.update(von=von, bis=von + len(v["alt"]))
            liste.append(v)
        self.ki_liste = liste
        if not liste:
            self.funde.leeren()
            self.melde("Fertig — alle Vorschläge sind durch.")
            return
        self.funde.zeichne(pruefung.ohne_ueberschneidung(liste))
        self.melde("1 Vorschlag. „Nehmen“ setzt ihn ein." if len(liste) == 1
                   else "%d Vorschläge. Jeden einzeln mit „Nehmen“ einsetzen." % len(liste))

    # --------------------------------------------------------------- Wortleiste
    def _lage_geaendert(self, *_):
        if self._wort_uhr:
            GLib.source_remove(self._wort_uhr)
            self._wort_uhr = 0
        # Sofort weg, sobald der Zeiger die Lage verlässt: ein stehengebliebener
        # Vorschlag zum vorigen Wort ist schlimmer als gar keiner.
        if self.feld.wort_am_zeiger() is None:
            self._leiste_leeren()
            return
        self._wort_uhr = GLib.timeout_add(180, self._leiste_zeigen)

    def _leiste_leeren(self):
        for k in self.leiste.get_children():
            self.leiste.remove(k)
        self.leiste.set_visible(False)

    def _leiste_zeigen(self):
        self._wort_uhr = 0
        lage = self.feld.wort_am_zeiger()
        if lage is None:
            self._leiste_leeren()
            return False
        von, bis, wort = lage
        # Gibt es Wörter, die so anfangen, ist das Getippte ein Anfang und wird
        # fortgesetzt. Gibt es keine, ist es zu Ende getippt und offenbar falsch.
        weiter = klang.faengt_an_mit(wort, ein.schon_gewaehlt(self.werte), 5)
        unbekannt = not weiter
        woerter = weiter or klang.vorschlaege_fuer(wort, ein.eigenes_wort(self.werte, wort), 5)
        self._leiste_leeren()
        if not woerter:
            return False
        was = Gtk.Label(label="Meintest du" if unbekannt else "Weiter mit")
        was.get_style_context().add_class("wortleiste-was")
        self.leiste.pack_start(was, False, False, 0)
        for w in woerter:
            neu = klang.mit_schreibweise(wort, w)
            k = Gtk.Button(label=neu)
            k.set_focus_on_click(False)           # der Fokus bleibt im Schreibfeld
            k.connect("clicked", lambda _b, v=von, b=bis, n=neu: self._wort_nehmen(v, b, n))
            self.leiste.pack_start(k, False, False, 0)
        self.leiste.show_all()
        return False

    def _wort_nehmen(self, von, bis, neu):
        self.feld.ersetze(von, bis, neu)
        ende = self.feld.puffer.get_iter_at_offset(von + len(neu))
        self.feld.puffer.place_cursor(ende)
        self._leiste_leeren()
        self._getippt()
        self.funde.leeren()
        self.feld.fokus()

    # --------------------------------------------------------------------- KI
    def _beschaeftigt_setzen(self, an, text=""):
        self._beschaeftigt = an
        self.kasten.sperre(an)
        if not an:
            self.kasten.lade(self.werte)
        if text:
            self.melde(text)
        self._aktualisiere_knoepfe()

    def _ki_starten(self, anweisung, laeuft, bauplan, fertig):
        text = self.feld.get_text().strip()
        if not text:
            self.melde("Es steht noch kein Text da.")
            return
        self.funde.leeren()
        self._beschaeftigt_setzen(True, laeuft)
        werte = ein.kopie(self.werte)      # der Faden arbeitet auf einer Kopie

        def lauf():
            try:
                ergebnis = ki.frage_ki(anweisung, text, werte, bauplan)
            except Exception as fehler:                     # noqa: BLE001
                ergebnis = (None, "Es hat nicht geklappt: %s" % fehler, None)
            GLib.idle_add(self._ki_fertig, ergebnis, fertig)
        threading.Thread(target=lauf, daemon=True, name="ki").start()

    def _ki_fertig(self, ergebnis, fertig):
        antwort, fehler, cent = ergebnis
        self._beschaeftigt_setzen(False)
        if fehler:
            self.melde(fehler)
            return False
        if cent is not None:
            ki.merke_kosten(self.werte, cent)
            self._werte_sichern()
        preis = (" · " + ki.als_geld(cent)) if cent is not None else ""
        fertig(antwort, preis)
        return False

    def _ersetze_durch_ki(self, neu, meldung):
        self._merke_fuer_zurueck(self.feld.get_text())
        self.feld.set_text(neu)
        self.gruen = []
        self._text_speichern()
        self.melde(meldung)
        self._aktualisiere_knoepfe()

    def _ki_korrigieren(self, *_):
        empf = self.werte["empfaenger"]
        zettel = self.kasten.zettel.get_text()
        melde = ki.EMPFAENGER.get(empf, {}).get("melde", "")
        wort = ("Fertig korrigiert" + (" · " + melde if melde else "")
                + (" · nach deinem Zettel" if zettel.strip() else "")
                + ". Nicht einverstanden? „Rückgängig“ darunter.")
        self._ki_starten(ki.baue_korrektur(self.werte, zettel), "Die KI liest deinen Text … einen Moment.",
                         None, lambda a, preis: self._ersetze_durch_ki(a, wort + preis))

    def _ki_uebersetzen(self, _k, sprache):
        self.werte["sprache"] = sprache
        self._werte_sichern()
        self._ki_starten(ki.ki_uebersetzung(sprache), "Die KI übersetzt … einen Moment.", None,
                         lambda a, preis: self._ersetze_durch_ki(
                             a, "Übersetzt nach %s. Das Original holt „Rückgängig“ wieder.%s" % (sprache, preis)))

    def _ki_vorschlaege(self, *_):
        anweisung = ki.ki_vorschlag_anweisung(self.werte["empfaenger"], self.kasten.zettel.get_text())

        def fertig(antwort, preis):
            roh = ki.lies_liste(antwort)
            if roh is None:
                self.melde("Die Antwort war nicht zu lesen. Bitte noch einmal versuchen.")
                return
            jetzt = self.feld.get_text()
            # Nur was zeichengenau im Text steht, lässt sich sicher ersetzen.
            self.ki_liste = [
                {"alt": v["alt"], "neu": v["neu"], "art": "vorschlag",
                 "grund": str(v.get("grund") or "Leichter zu lesen.")}
                for v in roh if isinstance(v, dict) and isinstance(v.get("alt"), str)
                and isinstance(v.get("neu"), str) and v["alt"] != v["neu"] and v["alt"] in jetzt]
            if not self.ki_liste:
                self.ki_liste = None
                self.melde("Die KI hatte nichts zu verbessern." + preis)
                return
            self._zeige_ki_liste()
            self.status.set_text(self.status.get_text() + preis)
        self._ki_starten(anweisung, "Die KI liest deinen Text … einen Moment.", ki.VORSCHLAG_BAUPLAN, fertig)

    def _empfaenger_gewaehlt(self, _k, name):
        self.werte["empfaenger"] = name
        self._werte_sichern()

    # --------------------------------------------------------- Zwischenablage
    def _kopieren(self, *_):
        text = self.feld.get_text().strip()
        if not text:
            self.melde("Es steht noch kein Text da.")
            return
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).store()
        self.melde("Kopiert — du kannst ihn jetzt irgendwo einfügen.", gut=True)

    def _einfuegen(self, *_):
        def da(_clip, text):
            if not text or not text.strip():
                self.melde("In der Zwischenablage steht kein Text.")
                return
            alt = self.feld.get_text()
            if alt.strip():
                self._merke_fuer_zurueck(alt)
            self.feld.set_text(text)
            self._text_speichern()
            self._aktualisiere_knoepfe()
            self.pruefen()             # gleich prüfen, wie bei der Handy-App
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).request_text(da)

    # ------------------------------------------------------------------ Dateien
    def _dateidialog(self, titel, aktion, knopf):
        d = Gtk.FileChooserNative.new(titel, self, aktion, knopf, "Abbrechen")
        f = Gtk.FileFilter()
        f.set_name("Textdateien")
        f.add_mime_type("text/plain")
        d.add_filter(f)
        return d

    def datei_oeffnen(self):
        d = self._dateidialog("Text öffnen", Gtk.FileChooserAction.OPEN, "Öffnen")
        if d.run() == Gtk.ResponseType.ACCEPT:
            try:
                with open(d.get_filename(), "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError as fehler:
                self.melde("Die Datei ließ sich nicht lesen: %s" % fehler)
                return
            alt = self.feld.get_text()
            if alt.strip():
                self._merke_fuer_zurueck(alt)
            self.feld.set_text(text)
            self._text_speichern()
            self._aktualisiere_knoepfe()
            self.melde("Geöffnet: %s" % os.path.basename(d.get_filename()))

    def datei_speichern(self):
        d = self._dateidialog("Text speichern", Gtk.FileChooserAction.SAVE, "Speichern")
        d.set_current_name("Text.txt")
        d.set_do_overwrite_confirmation(True)
        if d.run() == Gtk.ResponseType.ACCEPT:
            try:
                pfade.schreibe_atomar(d.get_filename(), self.feld.get_text())
            except OSError as fehler:
                self.melde("Die Datei ließ sich nicht schreiben: %s" % fehler)
                return
            self.melde("Gespeichert: %s" % os.path.basename(d.get_filename()), gut=True)

    # ------------------------------------------------------------------ Vorlesen
    def _vorlesen_umschalten(self, *_):
        def lauf():
            if vorlesen.spricht():
                vorlesen.vorlesen_beenden()
                GLib.idle_add(self.b_vorlesen.set_tooltip_text, "Text vorlesen")
            else:
                ok = vorlesen.vorlesen(self.feld.get_text(), self.ansicht["stimme"], self.ansicht["tempo"])
                if not ok:
                    GLib.idle_add(self.melde, "Vorlesen ging nicht.")
        threading.Thread(target=lauf, daemon=True, name="vorlesen").start()

    def _probe(self):
        threading.Thread(target=lambda: vorlesen.vorlesen(
            "So klingt die Stimme. Wir haben das Wort richtig geschrieben.",
            self.ansicht["stimme"], self.ansicht["tempo"]), daemon=True).start()

    # ------------------------------------------------------------------- Dialoge
    def einstellungen_oeffnen(self):
        """Blendet die Schreibansicht aus und die Einstellungen im selben
        Fenster ein."""
        if self.einstellungsseite:
            return
        seite = EinstellungenSeite(self.werte, self.ansicht, self._bei_ansicht, self._probe)
        seite.connect("fertig", self._einstellungen_fertig)
        self.einstellungsseite = seite
        self.stapel.add_named(seite, "einstellungen")
        seite.show_all()
        self.stapel.set_visible_child_name("einstellungen")

    def _einstellungen_fertig(self, seite, speichern):
        if speichern:
            self.werte = seite.ergebnis()
            self._werte_sichern()
            self.kasten.lade(self.werte)
            self.melde("Einstellungen gespeichert.", gut=True)
        self.einstellungsseite = None
        self.stapel.set_visible_child_name("schreiben")
        # Sofort aus dem Stapel nehmen: Der Stapel überblendet das Ausgeblendete
        # selbst zu Ende, und ein stehengebliebener Name würde die nächste
        # Einstellungs-Ansicht verdrängen.
        self.stapel.remove(seite)
        self.feld.fokus()

    def _taste(self, _w, ereignis):
        if ereignis.keyval == Gdk.KEY_Escape and self.einstellungsseite:
            self.einstellungsseite.emit("fertig", False)
            return True
        return False

    def ueber_zeigen(self):
        d = Gtk.AboutDialog(transient_for=self, modal=True)
        d.set_program_name("Schreibhilfe")
        d.set_version("1.0")
        d.set_comments("Findet die Fehler, die ein Rechtschreibprüfer nicht finden kann.\n"
                       "Native GTK-Fassung für Linux — ohne Browser, ohne Webserver.")
        d.set_logo_icon_name("schreibhilfe")
        d.set_website("https://github.com/nullforge86/schreibhilfe")
        d.set_license_type(Gtk.License.MIT_X11)
        d.run()
        d.destroy()

    # ----------------------------------------------------------------- Fenster
    def _geometrie_laden(self):
        b, h = 1000, 780
        try:
            with open(pfade.FENSTER_DATEI, "r", encoding="utf-8") as f:
                g = json.load(f)
            b = max(480, int(g.get("b", b)))
            h = max(420, int(g.get("h", h)))
            # Auf den Bildschirm begrenzen: Ein Monitor, der nicht mehr da ist,
            # darf das Fenster nicht ins Leere stellen.
            anzeige = Gdk.Display.get_default()
            monitor = anzeige.get_primary_monitor() or anzeige.get_monitor(0)
            if monitor:
                fl = monitor.get_workarea()
                b, h = min(b, fl.width), min(h, fl.height)
            self.set_default_size(b, h)
            if g.get("max"):
                self.maximize()
            return
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        self.set_default_size(b, h)

    def _geometrie_speichern(self):
        if self.is_maximized():
            alt = {}
            try:
                with open(pfade.FENSTER_DATEI, "r", encoding="utf-8") as f:
                    alt = json.load(f)
            except (OSError, ValueError):
                pass
            alt["max"] = True
            daten = alt
        else:
            b, h = self.get_size()
            x, y = self.get_position()
            daten = {"max": False, "b": b, "h": h, "x": x, "y": y}
        try:
            pfade.schreibe_atomar(pfade.FENSTER_DATEI, json.dumps(daten))
        except OSError:
            pass

    def _beim_schliessen(self, *_):
        vorlesen_ende = threading.Thread(target=vorlesen.vorlesen_beenden, daemon=True)
        vorlesen_ende.start()
        self._text_speichern()
        self._geometrie_speichern()
        return False
