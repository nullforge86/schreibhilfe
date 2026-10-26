# -*- coding: utf-8 -*-
"""Die Einstellungen als eigene Ansicht IM Hauptfenster — kein zweites Fenster.
Das Hauptfenster blendet die Schreibansicht kurz aus und diese hier ein.
Schlüssel und Modell gelten erst nach „Speichern“; Schrift, Thema und Stimme
wirken sofort (und gelten auch bei „Zurück“ weiter — sie sind Ansicht, keine
Verpflichtung)."""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, GObject, Gtk   # noqa: E402

from services import einstellungen as ein   # noqa: E402
from services import ki, vorlesen            # noqa: E402

LINK_SCHLUESSEL = "https://platform.claude.com/settings/keys"
LINK_GUTHABEN = "https://platform.claude.com/settings/billing"


def _gruppe(titel):
    rahmen = Gtk.Frame()
    rahmen.set_shadow_type(Gtk.ShadowType.NONE)
    kopf = Gtk.Label(xalign=0)
    kopf.set_markup("<b>%s</b>" % GLib.markup_escape_text(titel))
    rahmen.set_label_widget(kopf)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.set_margin_top(6)
    box.set_margin_start(12)
    rahmen.add(box)
    return rahmen, box


def _hinweis(text):
    l = Gtk.Label(label=text, xalign=0)
    l.set_line_wrap(True)
    l.get_style_context().add_class("dim-label")
    return l


class EinstellungenSeite(Gtk.Box):
    __gsignals__ = {
        # True = Speichern, False = Abbrechen / Zurück
        "fertig": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self, werte, ansicht, bei_ansicht, bei_probe):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.werte = ein.kopie(werte)          # Arbeitskopie, erst „Speichern“ übernimmt
        self.ansicht = ansicht
        self._bei_ansicht = bei_ansicht
        self._probe = bei_probe
        self._ladend = False
        self._zerstoert = False
        self.connect("destroy", lambda *_: setattr(self, "_zerstoert", True))

        # Kopf: Pfeil zurück und Überschrift, wie in der Handy-App
        kopf = Gtk.Box(spacing=8)
        for r in ("top", "bottom", "start", "end"):
            getattr(kopf, "set_margin_" + r)(8)
        self.zurueck = Gtk.Button.new_from_icon_name("go-previous", Gtk.IconSize.BUTTON)
        self.zurueck.set_tooltip_text("Zurück zum Text")
        self.zurueck.connect("clicked", lambda *_: self.emit("fertig", False))
        titel = Gtk.Label(xalign=0)
        titel.set_markup("<big><b>Einstellungen</b></big>")
        kopf.pack_start(self.zurueck, False, False, 0)
        kopf.pack_start(titel, False, False, 0)
        self.pack_start(kopf, False, False, 0)
        self.pack_start(Gtk.Separator(), False, False, 0)

        rolle = Gtk.ScrolledWindow()
        rolle.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(rolle, True, True, 0)
        seite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for r in ("top", "bottom", "start", "end"):
            getattr(seite, "set_margin_" + r)(12)
        rolle.add(seite)

        # Fuß: Speichern / Abbrechen
        self.pack_start(Gtk.Separator(), False, False, 0)
        fuss = Gtk.Box(spacing=6)
        for r in ("top", "bottom", "start", "end"):
            getattr(fuss, "set_margin_" + r)(8)
        self.abbrechen = Gtk.Button.new_with_mnemonic("_Abbrechen")
        self.abbrechen.connect("clicked", lambda *_: self.emit("fertig", False))
        self.speichern = Gtk.Button.new_with_mnemonic("_Speichern")
        self.speichern.get_style_context().add_class("suggested-action")
        self.speichern.connect("clicked", lambda *_: self.emit("fertig", True))
        fuss.pack_end(self.speichern, False, False, 0)
        fuss.pack_end(self.abbrechen, False, False, 0)
        self.pack_start(fuss, False, False, 0)

        self._ki_gruppe(seite)
        self._vorlesen_gruppe(seite)
        self._schreiben_gruppe(seite)
        self._gedaechtnis_gruppe(seite)
        self._darstellung_gruppe(seite)
        self.show_all()
        self._modelle_nachtragen()

    # ----------------------------------------------------------------- KI
    def _ki_gruppe(self, seite):
        rahmen, box = _gruppe("KI-Werkzeuge")
        box.pack_start(Gtk.Label(label="API-Schlüssel (für Korrigieren und Übersetzen)", xalign=0), False, False, 0)
        self.schluessel = Gtk.Entry()
        self.schluessel.set_visibility(False)
        self.schluessel.set_property("caps-lock-warning", False)     # sonst kollidiert es mit dem Auge-Symbol
        self.schluessel.set_placeholder_text("sk-ant-…")
        self.schluessel.set_text(self.werte["apiKey"])
        self.schluessel.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
        self.schluessel.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Anzeigen / verbergen")
        self.schluessel.connect("icon-press", lambda e, *_: e.set_visibility(not e.get_visibility()))
        self.schluessel.connect("changed", lambda *_: self._zeige_schluessel_stand())
        box.pack_start(self.schluessel, False, False, 0)
        self.schluessel_stand = _hinweis("")
        box.pack_start(self.schluessel_stand, False, False, 0)
        reihe = Gtk.Box(spacing=6)
        kopieren = Gtk.Button(label="Schlüssel kopieren")
        kopieren.connect("clicked", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(
            self.schluessel.get_text(), -1))
        weg = Gtk.Button(label="Schlüssel löschen")
        weg.connect("clicked", lambda *_: self.schluessel.set_text(""))
        reihe.pack_start(kopieren, False, False, 0)
        reihe.pack_start(weg, False, False, 0)
        reihe.pack_end(Gtk.LinkButton.new_with_label(LINK_SCHLUESSEL, "Schlüssel erstellen ↗"), False, False, 0)
        box.pack_start(reihe, False, False, 0)

        box.pack_start(Gtk.Label(label="KI-Modell", xalign=0), False, False, 0)
        self.modell = Gtk.ComboBoxText()
        self._modell_ids = []
        for m in ein.MODELLE:
            self.modell.append_text("Claude · " + ein.MODELL_NAMEN[m])
            self._modell_ids.append(m)
        box.pack_start(self.modell, False, False, 0)
        self.modell_hinweis = _hinweis("")
        box.pack_start(self.modell_hinweis, False, False, 0)
        self.modell.connect("changed", self._modell_gewaehlt)

        box.pack_start(Gtk.Label(label="Verbrauch", xalign=0), False, False, 0)
        zeile = Gtk.Box(spacing=6)
        self.kosten = _hinweis(ki.kostenstand(self.werte))
        zeile.pack_start(self.kosten, True, True, 0)
        z = Gtk.Button(label="zurücksetzen")
        z.connect("clicked", self._kosten_weg)
        zeile.pack_end(z, False, False, 0)
        zeile.pack_end(Gtk.LinkButton.new_with_label(LINK_GUTHABEN, "Guthaben aufladen ↗"), False, False, 0)
        box.pack_start(zeile, False, False, 0)
        seite.pack_start(rahmen, False, False, 0)
        self._zeige_schluessel_stand()
        self._waehle_modell(self.werte["modell"])

    def _zeige_schluessel_stand(self):
        n = len(self.schluessel.get_text().strip())
        self.schluessel_stand.set_text("Ein Schlüssel ist gespeichert (%d Zeichen)." % n if n
                                       else "Noch kein Schlüssel hinterlegt.")

    def _kosten_weg(self, *_):
        self.werte["kosten"] = {"anzahl": 0, "cent": 0.0}
        self.kosten.set_text(ki.kostenstand(self.werte))

    def _waehle_modell(self, ident):
        if ident not in self._modell_ids and ki.ist_lokal(ident):
            # Ein gespeichertes lokales Modell steht in der Liste, auch wenn
            # Ollama gerade nicht antwortet.
            self.modell.append_text("Auf diesem Rechner · " + ki.lokaler_name(ident))
            self._modell_ids.append(ident)
        self._ladend = True
        try:
            self.modell.set_active(self._modell_ids.index(ident) if ident in self._modell_ids else 0)
        finally:
            self._ladend = False
        self._zeige_modell_hinweis()

    def _modell_gewaehlt(self, *_):
        i = self.modell.get_active()
        if i >= 0 and not self._ladend:
            self.werte["modell"] = self._modell_ids[i]
        self._zeige_modell_hinweis()

    def _zeige_modell_hinweis(self):
        i = self.modell.get_active()
        lokal = i >= 0 and ki.ist_lokal(self._modell_ids[i])
        self.modell_hinweis.set_text(
            "Läuft auf diesem Rechner — kostenlos, ohne Internet, der Text verlässt das Gerät nicht."
            if lokal else "Läuft im Netz bei Anthropic — braucht Schlüssel und Guthaben.")

    def _modelle_nachtragen(self):
        """Was installiert ist, weiß nur Ollama selbst — also fragen, ohne das
        Fenster warten zu lassen."""
        def lauf():
            namen = ki.ollama_modelle()
            GLib.idle_add(self._modelle_da, namen)
        threading.Thread(target=lauf, daemon=True).start()

    def _modelle_da(self, namen):
        if self._zerstoert:                 # die Ansicht ist schon wieder weg
            return False
        aktuell = self.werte["modell"]
        for n in namen:
            ident = ein.OLLAMA_MARKE + n
            if ident not in self._modell_ids:
                self.modell.append_text("Auf diesem Rechner · " + n)
                self._modell_ids.append(ident)
        self._waehle_modell(aktuell)
        return False

    # ------------------------------------------------------------ Vorlesen
    def _vorlesen_gruppe(self, seite):
        if not vorlesen.kann_vorlesen():
            return
        rahmen, box = _gruppe("Vorlesen")
        box.pack_start(Gtk.Label(label="Stimme", xalign=0), False, False, 0)
        self.stimme = Gtk.ComboBoxText()
        self._stimmen = [""]
        self.stimme.append_text("Standard des Rechners" if not vorlesen.piper_da() else "Beste verfügbare")
        for s in vorlesen.piper_stimmen():
            self.stimme.append_text(s["name"])
            self._stimmen.append(s["kennung"])
        self.stimme.set_active(self._stimmen.index(self.ansicht["stimme"]) if self.ansicht["stimme"] in self._stimmen else 0)
        self.stimme.connect("changed", self._stimme_geaendert)
        box.pack_start(self.stimme, False, False, 0)
        box.pack_start(_hinweis("Wer mehr Stimmen will: ./stimme-holen.sh im Projektordner."
                                if not vorlesen.piper_da() else
                                "Langsamer hilft beim Mithören oft mehr als eine andere Stimme."), False, False, 0)
        zeile = Gtk.Box(spacing=8)
        zeile.pack_start(Gtk.Label(label="Tempo"), False, False, 0)
        self.tempo = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -60, 60, 10)
        self.tempo.set_value(self.ansicht["tempo"])
        self.tempo.set_draw_value(False)
        self.tempo.add_mark(0, Gtk.PositionType.BOTTOM, "normal")
        self.tempo.connect("value-changed", self._tempo_geaendert)
        zeile.pack_start(self.tempo, True, True, 0)
        box.pack_start(zeile, False, False, 0)
        probe = Gtk.Button(label="Probe hören")
        probe.connect("clicked", lambda *_: self._probe())
        probe.set_halign(Gtk.Align.START)
        box.pack_start(probe, False, False, 0)
        seite.pack_start(rahmen, False, False, 0)

    def _stimme_geaendert(self, *_):
        self._bei_ansicht(stimme=self._stimmen[max(0, self.stimme.get_active())])

    def _tempo_geaendert(self, *_):
        self._bei_ansicht(tempo=int(self.tempo.get_value()))

    # ---------------------------------------------------------- Schreiben
    def _schreiben_gruppe(self, seite):
        rahmen, box = _gruppe("Beim Schreiben")
        self.marker = Gtk.CheckButton(label="Wort hervorheben — ein farbiger Streifen zeigt, wo du gerade bist")
        self.marker.set_active(self.ansicht["wortmarker"])
        self.marker.connect("toggled", lambda b: self._bei_ansicht(wortmarker=b.get_active()))
        box.pack_start(self.marker, False, False, 0)
        seite.pack_start(rahmen, False, False, 0)

    # ----------------------------------------------------------- Gedächtnis
    def _gedaechtnis_gruppe(self, seite):
        rahmen, box = _gruppe("Gedächtnis")
        box.pack_start(Gtk.Label(label="Gelernte Schreibweisen — bleiben auf diesem Rechner", xalign=0), False, False, 0)
        zeile = Gtk.Box(spacing=6)
        self.gelernt = _hinweis(ein.gedaechtnis_stand(self.werte))
        zeile.pack_start(self.gelernt, True, True, 0)
        v = Gtk.Button(label="vergessen")
        v.connect("clicked", self._vergessen)
        zeile.pack_end(v, False, False, 0)
        box.pack_start(zeile, False, False, 0)

        reihe = Gtk.Box(spacing=6)
        sichern = Gtk.Button(label="Sichern (in Zwischenablage)")
        sichern.connect("clicked", self._sichern)
        einspielen = Gtk.Button(label="Einspielen (aus Zwischenablage)")
        einspielen.connect("clicked", self._einspielen_klick)
        reihe.pack_start(sichern, False, False, 0)
        reihe.pack_start(einspielen, False, False, 0)
        box.pack_start(reihe, False, False, 0)
        box.pack_start(_hinweis("Der Sicherungs-Text passt auch zur Handy-App. "
                                "Der API-Schlüssel ist bewusst nicht darin."), False, False, 0)
        seite.pack_start(rahmen, False, False, 0)

    def _vergessen(self, *_):
        ein.vergiss_alles(self.werte)
        self.gelernt.set_text(ein.gedaechtnis_stand(self.werte))

    def _sichern(self, *_):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(ein.baue_sicherung(self.werte), -1)
        self.gelernt.set_text("Gesichert — liegt in der Zwischenablage.")

    def _einspielen_klick(self, *_):
        roh = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() or ""
        ergebnis, fehler = ein.spiele_sicherung_ein(roh, self.werte, ki.EMPFAENGER)
        if fehler:
            self.gelernt.set_text(fehler)
            return
        self.gelernt.set_text("Eingespielt: %d neue Schreibweisen, %d neue Ruhe-Wörter. %s"
                              % (ergebnis[0], ergebnis[1], ein.gedaechtnis_stand(self.werte)))
        self._waehle_modell(self.werte["modell"])

    # ------------------------------------------------------------ Darstellung
    def _darstellung_gruppe(self, seite):
        rahmen, box = _gruppe("Darstellung")
        zeile = Gtk.Box(spacing=6)
        k = Gtk.Button(label="A− kleiner")
        g = Gtk.Button(label="A+ größer")
        k.connect("clicked", lambda *_: self._schrift(-0.1))
        g.connect("clicked", lambda *_: self._schrift(+0.1))
        zeile.pack_start(k, False, False, 0)
        zeile.pack_start(g, False, False, 0)
        zeile.pack_start(Gtk.Label(label="Hell/Dunkel"), False, False, 8)
        self.thema = Gtk.ComboBoxText()
        for t, n in (("auto", "Wie das System"), ("hell", "Immer hell"), ("dunkel", "Immer dunkel")):
            self.thema.append(t, n)
        self.thema.set_active_id(self.ansicht["thema"])
        self.thema.connect("changed", lambda c: self._bei_ansicht(thema=c.get_active_id()))
        zeile.pack_start(self.thema, False, False, 0)
        box.pack_start(zeile, False, False, 0)
        self.schriftstand = _hinweis("")
        box.pack_start(self.schriftstand, False, False, 0)
        self._zeige_schrift()
        seite.pack_start(rahmen, False, False, 0)

    def _schrift(self, delta):
        neu = round(max(ein.SCHRIFT_MIN, min(ein.SCHRIFT_MAX, self.ansicht["schrift"] + delta)), 2)
        self._bei_ansicht(schrift=neu)
        self._zeige_schrift()

    def _zeige_schrift(self):
        s = self.ansicht["schrift"]
        t = "Schriftgröße: %d %%" % round(s * 100)
        if s >= ein.SCHRIFT_MAX:
            t += " — größer geht nicht"
        elif s <= ein.SCHRIFT_MIN:
            t += " — kleiner geht nicht"
        self.schriftstand.set_text(t)

    # ------------------------------------------------------------ Ergebnis
    def ergebnis(self):
        """Die Arbeitskopie mit den Eingaben dieses Fensters."""
        self.werte["apiKey"] = self.schluessel.get_text().strip()
        i = self.modell.get_active()
        if i >= 0:
            self.werte["modell"] = self._modell_ids[i]
        return self.werte
