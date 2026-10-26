# -*- coding: utf-8 -*-
"""GUI-Test der echten Oberfläche. Läuft NUR, wenn SCHREIBHILFE_GUI_TEST=1 gesetzt
ist und ein Bildschirm da ist — so öffnet sich nie ungefragt ein Fenster auf der
laufenden Sitzung. Am besten in einem eigenen Xephyr:

    Xephyr :9 -screen 1280x900 &  DISPLAY=:9 marco &
    DISPLAY=:9 GDK_BACKEND=x11 SCHREIBHILFE_GUI_TEST=1 \\
        python3 -m unittest discover -s linux/tests -t linux -v

Konfiguration und Daten gehen in einen Wegwerf-Ordner (siehe tests/__init__.py);
die echten bleiben unberührt.
"""

import os
import sys
import tempfile
import unittest

AKTIV = os.environ.get("SCHREIBHILFE_GUI_TEST") == "1" and bool(os.environ.get("DISPLAY"))

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HIER))

if AKTIV:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk


def pumpen(ms=50):
    """Lässt GTK Ereignisse abarbeiten (Timer, Neuzeichnen)."""
    ende = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < ende:
        while Gtk.events_pending():
            Gtk.main_iteration()


@unittest.skipUnless(AKTIV, "GUI-Test nicht angefordert (SCHREIBHILFE_GUI_TEST=1 und DISPLAY setzen)")
class TestOberflaeche(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from application import Schreibhilfe
        cls.app = Schreibhilfe()
        cls.app.register(None)
        cls.app.activate()
        pumpen(300)
        cls.fenster = cls.app.fenster

    @classmethod
    def tearDownClass(cls):
        cls.fenster.destroy()

    def setUp(self):
        f = self.fenster
        f.feld.set_text("", als_eine_aenderung=False)
        f._vergiss_zurueck()
        f.funde.leeren()
        f.gruen = []
        f.ki_liste = None
        f._aktualisiere_knoepfe()

    def test_kein_webkit_geladen(self):
        self.assertNotIn("gi.repository.WebKit2", sys.modules)
        self.assertNotIn("http.server", sys.modules)

    def test_fenster_ist_nativ(self):
        f = self.fenster
        self.assertEqual(f.get_title(), "Schreibhilfe")
        self.assertTrue(f.is_visible())
        self.assertIsInstance(f.feld.ansicht, Gtk.TextView)

    def test_pruefen_zeigt_karten_und_aendern_wirkt(self):
        f = self.fenster
        f.feld.set_text("Wir hat ein Problem.", als_eine_aenderung=False)
        f.b_pruefen.clicked()
        pumpen()
        self.assertIn("1 Stelle zum Ändern", f.status.get_text())
        self.assertTrue(f.funde.hat_aenderbares())
        fund = {"von": 0, "bis": 7, "alt": "Wir hat", "neu": "Wir haben", "grund": "x", "art": "fehler"}
        f._uebernimm(fund)
        pumpen()
        self.assertEqual(f.feld.get_text(), "Wir haben ein Problem.")
        self.assertTrue(f.b_zurueck.get_visible())
        f.b_zurueck.clicked()
        self.assertEqual(f.feld.get_text(), "Wir hat ein Problem.")

    def test_alles_aendern_und_rueckgaengig(self):
        f = self.fenster
        f.feld.set_text("Wir hat  ein Problem", als_eine_aenderung=False)
        f.b_alles.clicked()
        pumpen()
        self.assertEqual(f.feld.get_text().split()[0:2], ["Wir", "haben"])
        self.assertTrue(f.gruen)
        f.zurueckholen()
        self.assertEqual(f.feld.get_text(), "Wir hat  ein Problem")

    def test_loeschen_und_zurueckholen(self):
        f = self.fenster
        f.feld.set_text("Ein Brief", als_eine_aenderung=False)
        f._aktualisiere_knoepfe()
        f.b_leeren.clicked()
        self.assertEqual(f.feld.get_text(), "")
        self.assertIn("Zurückholen", f.b_leeren.get_label())
        f.b_leeren.clicked()
        self.assertEqual(f.feld.get_text(), "Ein Brief")

    def test_tippen_vergisst_zurueckstand(self):
        f = self.fenster
        f.feld.set_text("Ein Brief", als_eine_aenderung=False)
        f.b_leeren.clicked()
        f.feld.puffer.insert_at_cursor("neu")      # wie getippt (nicht intern)
        self.assertIsNone(f.vorheriger_text)

    def test_wortleiste(self):
        f = self.fenster
        f.feld.set_text("", als_eine_aenderung=False)
        f.feld.ansicht.grab_focus()
        f.feld.puffer.insert_at_cursor("Das ist wid")
        pumpen(400)
        knoepfe = [k.get_label() for k in f.leiste.get_children() if isinstance(k, Gtk.Button)]
        self.assertIn("widerspruch", knoepfe)
        k = [k for k in f.leiste.get_children() if isinstance(k, Gtk.Button) and k.get_label() == "widerspruch"][0]
        k.clicked()
        self.assertEqual(f.feld.get_text(), "Das ist widerspruch")

    def test_ki_ohne_schluessel_bleibt_gesperrt(self):
        f = self.fenster
        f.werte["apiKey"] = ""
        f.werte["modell"] = "claude-opus-5"
        f.kasten.lade(f.werte)
        self.assertFalse(f.kasten.b_korrektur.get_sensitive())

    def test_ki_fehler_wird_angezeigt(self):
        f = self.fenster
        f.werte["modell"] = "ollama:gibt-es-nicht"
        import services.ki as ki
        alt = ki.OLLAMA_ADRESSE
        ki.OLLAMA_ADRESSE = "http://127.0.0.1:9"          # dort lauscht niemand
        try:
            f.feld.set_text("Ein Text", als_eine_aenderung=False)
            f.kasten.lade(f.werte)
            f._ki_korrigieren()
            for _ in range(60):
                pumpen(100)
                if not f._beschaeftigt:
                    break
        finally:
            ki.OLLAMA_ADRESSE = alt
        self.assertFalse(f._beschaeftigt)
        self.assertIn("nicht zu erreichen", f.status.get_text())
        self.assertEqual(f.feld.get_text(), "Ein Text")     # unverändert

    def test_ki_antwort_ersetzt_text_und_ist_rueckholbar(self):
        f = self.fenster
        f.feld.set_text("ein text", als_eine_aenderung=False)
        f._ki_fertig(("Ein Text.", None, 0.24), lambda a, preis: f._ersetze_durch_ki(a, "ok" + preis))
        self.assertEqual(f.feld.get_text(), "Ein Text.")
        self.assertIn("0,24 Cent", f.status.get_text())
        f.zurueckholen()
        self.assertEqual(f.feld.get_text(), "ein text")

    def test_ki_vorschlaege_liste(self):
        f = self.fenster
        f.feld.set_text("Dies ist ein sehr langer Satz.", als_eine_aenderung=False)
        f.ki_liste = [{"alt": "Dies ist ein sehr langer Satz.", "neu": "Der Satz ist lang.",
                       "art": "vorschlag", "grund": "kürzer"}]
        f._zeige_ki_liste()
        self.assertTrue(f.funde.hat_aenderbares())
        f._uebernimm(f.ki_liste[0])
        self.assertEqual(f.feld.get_text(), "Der Satz ist lang.")
        self.assertIn("alle Vorschläge sind durch", f.status.get_text())

    def test_text_wird_gesichert(self):
        from services import pfade
        f = self.fenster
        f.feld.set_text("Gesichert?", als_eine_aenderung=False)
        f._text_speichern()
        with open(pfade.TEXT_DATEI, encoding="utf-8") as d:
            self.assertEqual(d.read(), "Gesichert?")

    def test_einstellungen_tauschen_die_ansicht_im_selben_fenster(self):
        f = self.fenster
        fenster_vorher = [w for w in Gtk.Window.list_toplevels() if w.get_visible()]
        f.einstellungen_oeffnen()
        pumpen(200)
        self.assertEqual(f.stapel.get_visible_child_name(), "einstellungen")
        # kein zweites Fenster, und die Schreibansicht ist ausgeblendet
        self.assertEqual([w for w in Gtk.Window.list_toplevels() if w.get_visible()], fenster_vorher)
        self.assertFalse(f.schreibseite.get_child_visible())
        seite = f.einstellungsseite
        seite.schluessel.set_text("sk-ant-test")
        self.assertEqual(f.werte["apiKey"], "")             # Arbeitskopie, noch nichts übernommen
        seite.speichern.clicked()
        pumpen(100)
        self.assertEqual(f.stapel.get_visible_child_name(), "schreiben")
        self.assertEqual(f.werte["apiKey"], "sk-ant-test")
        f.werte["apiKey"] = ""

    def test_einstellungen_abbrechen_verwirft(self):
        f = self.fenster
        f.einstellungen_oeffnen()
        f.einstellungsseite.schluessel.set_text("sk-verworfen")
        f.einstellungsseite.abbrechen.clicked()
        pumpen(100)
        self.assertEqual(f.stapel.get_visible_child_name(), "schreiben")
        self.assertEqual(f.werte["apiKey"], "")

    def test_schrift_und_thema(self):
        f = self.fenster
        f._bei_ansicht(schrift=1.5, thema="dunkel")
        self.assertEqual(f.feld.schrift, 1.5)
        self.assertTrue(Gtk.Settings.get_default().get_property("gtk-application-prefer-dark-theme"))
        f._bei_ansicht(schrift=1.0, thema="auto")


if __name__ == "__main__":
    unittest.main()
