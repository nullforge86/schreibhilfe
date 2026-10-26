# -*- coding: utf-8 -*-
"""Tests für die Dienste (ohne Oberfläche, ohne Netz).  Aufruf:
    python3 -m unittest discover -s linux/tests -t linux -v
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HIER = os.path.dirname(os.path.abspath(__file__))
LINUX = os.path.dirname(HIER)
WURZEL = os.path.dirname(LINUX)
sys.path.insert(0, LINUX)

from services import einstellungen as ein   # noqa: E402
from services import ki, klang, pfade, pruefung   # noqa: E402


class TestPruefung(unittest.TestCase):
    def test_wortliste_und_regeln_liegen_im_linux_ordner(self):
        self.assertGreater(len(pruefung.lade_woerter()), 300000)
        self.assertIn("WOERTERBUCH", pruefung._REGELN)
        for datei in ("woerter.txt", "regeln.js"):
            self.assertTrue(os.path.isfile(os.path.join(LINUX, "daten", datei)), datei)

    def test_daten_gleich_wie_online(self):
        """linux/daten ist eine Kopie von online/daten — sie darf nicht still abweichen."""
        for datei in ("woerter.txt", "regeln.js"):
            quelle = os.path.join(WURZEL, "online", "daten", datei)
            if not os.path.isfile(quelle):
                self.skipTest("online/daten fehlt")
            with open(quelle, "rb") as a, open(os.path.join(LINUX, "daten", datei), "rb") as b:
                self.assertEqual(a.read(), b.read(), datei + " weicht von online/daten ab — neu kopieren")

    def test_kongruenz_wir_hat(self):
        funde = pruefung.finde_probleme("Wir hat ein Problem.")
        self.assertTrue(any(f["alt"] == "Wir hat" and f["neu"] == "Wir haben" for f in funde))

    def test_seit_seid_und_dass(self):
        funde = pruefung.finde_probleme("Ich glaube das es gut wird. Ihr seit nett.")
        paare = {(f["alt"], f["neu"]) for f in funde}
        self.assertIn(("glaube das", "glaube, dass"), paare)
        self.assertIn(("Ihr seit", "ihr seid"), paare)

    def test_richtiger_satz_bleibt_in_ruhe(self):
        self.assertEqual([f for f in pruefung.finde_probleme("Das Buch, das ich gelesen habe, ist gut.")
                          if f["art"] != "hinweis"], [])

    def test_doppeltes_wort_und_leerzeichen(self):
        arten = {f["grund"] for f in pruefung.finde_probleme("Das das ist  doppelt.")}
        self.assertIn("Das Wort steht doppelt da", arten)
        self.assertIn("Mehrere Leerzeichen hintereinander", arten)

    def test_zusammengeschrieben(self):
        funde = pruefung.finde_probleme("Es ist am besten so.")
        self.assertEqual([f for f in funde if f["art"] != "hinweis"], [])
        funde = pruefung.finde_probleme("Das ist ambesten so.")
        self.assertTrue(any(f["neu"] == "am besten" for f in funde))

    def test_gelerntes_wort_wird_angewendet(self):
        gelernt = {"woerter": {"kanst": "kannst"}, "inRuhe": {}}
        funde = pruefung.finde_probleme("Du kanst das.", gelernt)
        self.assertTrue(any(f["alt"] == "kanst" and f["neu"] == "kannst" for f in funde))

    def test_gleich_wie_libreoffice(self):
        """Die Abschrift darf nicht still vom Original abweichen."""
        original = os.path.join(WURZEL, "libreoffice", "schreibhilfe", "pruefung.py")
        if not os.path.isfile(original):
            self.skipTest("LibreOffice-Ordner fehlt")
        import importlib.util
        spec = importlib.util.spec_from_file_location("pruefung_lo", original)
        lo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lo)
        lo.lade_woerter(os.path.join(WURZEL, "online", "daten", "woerter.txt"))
        saetze = ["Wir hat ein Problem. glaube das wird gut", "Ihr seit nett, und du hast recht wie ich.",
                  "Das ist ambesten  so,aber nicht immer.", "kwalitaet ist wichtig, weil es gibt viele Fehler",
                  "Er könnten das, sie machen es, ich glaube dass es geht."]
        for satz in saetze:
            self.assertEqual(pruefung.finde_probleme(satz), lo.finde_probleme(satz), satz)


class TestKlang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        klang.klangtafel_bauen()

    def test_phonetik_gleicher_klang(self):
        self.assertEqual(klang.koelner_phonetik("kwalität"), klang.koelner_phonetik("Qualität"))
        self.assertEqual(klang.koelner_phonetik("Müller"), "657")

    def test_klangsuche_findet_vielleicht(self):
        self.assertEqual(klang.vorschlaege_fuer("fileicht")[0], "vielleicht")

    def test_wortvorhersage(self):
        self.assertEqual(klang.faengt_an_mit("wid", hoechstens=3), ["widerspruch", "wider", "widme"])

    def test_schreibweise(self):
        self.assertEqual(klang.mit_schreibweise("Fileicht", "vielleicht"), "Vielleicht")
        self.assertEqual(klang.mit_schreibweise("berechnu", "berechnung"), "Berechnung")
        self.assertEqual(klang.mit_schreibweise("wid", "widerspruch"), "widerspruch")


class TestKi(unittest.TestCase):
    def test_anweisungen_wortgleich_mit_libreoffice(self):
        quelle = os.path.join(WURZEL, "libreoffice", "schreibhilfe", "schreibhilfe.py")
        if not os.path.isfile(quelle):
            self.skipTest("LibreOffice-Ordner fehlt")
        with open(quelle, encoding="utf-8") as f:
            baum = ast.parse(f.read())
        werte = {}
        for knoten in baum.body:
            if isinstance(knoten, ast.Assign) and isinstance(knoten.targets[0], ast.Name):
                if knoten.targets[0].id in ("EMPFAENGER", "VORSCHLAG_BAUPLAN", "PREISE", "ZETTEL_GRENZE"):
                    werte[knoten.targets[0].id] = ast.literal_eval(knoten.value)
        self.assertEqual(ki.EMPFAENGER, werte["EMPFAENGER"])
        self.assertEqual(ki.VORSCHLAG_BAUPLAN, werte["VORSCHLAG_BAUPLAN"])
        self.assertEqual(ki.PREISE, werte["PREISE"])
        self.assertEqual(ki.ZETTEL_GRENZE, werte["ZETTEL_GRENZE"])

    def test_korrektur_enthaelt_empfaenger_zettel_steckbrief(self):
        text = ki.ki_korrektur("Amt", "Widerspruch", " Steckbrief.")
        self.assertIn("Behörde", text)
        self.assertIn("Widerspruch", text)
        self.assertIn("Steckbrief.", text)

    def test_kosten(self):
        cent = ki.cent_fuer("claude-haiku-4-5", {"input_tokens": 1000000, "output_tokens": 0})
        self.assertAlmostEqual(cent, 100)
        self.assertEqual(ki.als_geld(0.24), "0,24 Cent")
        self.assertIsNone(ki.cent_fuer("ollama:x", {"input_tokens": 5}))

    def test_ollama_denkklammern(self):
        self.assertEqual(ki.ohne_gruebeln("<think>hm</think>Fertig."), "Fertig.")
        self.assertEqual(ki.ohne_gruebeln("hm</think>Fertig."), "Fertig.")

    def test_liste_lesen(self):
        self.assertEqual(ki.lies_liste('```json\n{"vorschlaege":[{"alt":"a","neu":"b","grund":"c"}]}\n```')[0]["neu"], "b")
        self.assertIsNone(ki.lies_liste("kein json"))

    def test_ohne_schluessel_kein_netzzugriff(self):
        antwort, fehler, cent = ki.frage_ki("x", "y", {"modell": "claude-opus-5", "apiKey": ""})
        self.assertIsNone(antwort)
        self.assertIn("Schlüssel", fehler)

    def test_ollama_nicht_erreichbar_meldet_verstaendlich(self):
        orig = ki.OLLAMA_ADRESSE
        # Ein Port, auf dem niemand lauscht — es darf kein Traceback entstehen.
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        ki.OLLAMA_ADRESSE = "http://127.0.0.1:%d" % port
        try:
            # frage_ollama liest die Adresse aus dem Modul
            antwort, fehler = ki.frage_ollama("a", "b", {"modell": "ollama:qwen3:8b"})
        finally:
            ki.OLLAMA_ADRESSE = orig
        self.assertIsNone(antwort)
        self.assertIn("nicht zu erreichen", fehler)

    def test_bereit(self):
        self.assertFalse(ki.ki_bereit({"modell": "claude-opus-5", "apiKey": ""}))
        self.assertTrue(ki.ki_bereit({"modell": "claude-opus-5", "apiKey": "sk"}))
        self.assertTrue(ki.ki_bereit({"modell": "ollama:qwen3:8b", "apiKey": ""}))


class TestEinstellungen(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.datei = os.path.join(self.ordner.name, "einstellungen.json")

    def tearDown(self):
        self.ordner.cleanup()

    def _schreibe(self, text):
        with open(self.datei, "w", encoding="utf-8") as f:
            f.write(text)

    def test_fehlende_datei_gibt_vorgabe(self):
        self.assertEqual(ein.lies_einstellungen(self.datei)["modell"], "claude-opus-5")

    def test_kaputte_datei_gibt_vorgabe(self):
        self._schreibe("{kaputt")
        self.assertEqual(ein.lies_einstellungen(self.datei)["empfaenger"], "egal")

    def test_schreiben_und_lesen_mit_rechten(self):
        w = ein.standard()
        w["apiKey"] = "sk-test"
        w["gelernt"]["woerter"]["kanst"] = "kannst"
        ein.schreib_einstellungen(w, self.datei)
        self.assertEqual(oct(os.stat(self.datei).st_mode & 0o777), "0o600")
        self.assertEqual(ein.lies_einstellungen(self.datei)["gelernt"]["woerter"], {"kanst": "kannst"})

    def test_alter_tonfall(self):
        self._schreibe(json.dumps({"tonfall": "Förmlich (Amt)"}))
        self.assertEqual(ein.lies_einstellungen(self.datei, ki.EMPFAENGER)["empfaenger"], "Amt")

    def test_lernen_nur_was_nicht_im_woerterbuch_steht(self):
        w = ein.standard()
        fund = {"alt": "kanst", "neu": "kannst", "wortEbene": True}
        self.assertTrue(ein.merke_aenderung(fund, w))
        self.assertEqual(w["gelernt"]["woerter"]["kanst"], "kannst")
        self.assertFalse(ein.merke_aenderung({"alt": "wir", "neu": "wird", "wortEbene": True}, ein.standard()))
        self.assertFalse(ein.merke_aenderung({"alt": "Zahnriemenspanner-Kettenrolle",
                                              "neu": "Unannehmlichkeiten", "wortEbene": True}, ein.standard()))
        self.assertFalse(ein.merke_aenderung({"alt": "kanst", "neu": "kannst", "wortEbene": False}, ein.standard()))

    def test_ruhe_nach_schwelle(self):
        w = ein.standard()
        fund = {"alt": "Siebke", "neu": "Sieben", "wortEbene": True}
        for _ in range(ein.LERN_SCHWELLE):
            ein.merke_gezeigt([fund], w)
        self.assertTrue(w["gelernt"]["inRuhe"].get("siebke"))

    def test_sicherung_rundreise_ohne_schluessel(self):
        w = ein.standard()
        w["apiKey"] = "sk-geheim"
        w["gelernt"]["woerter"]["kanst"] = "kannst"
        text = ein.baue_sicherung(w)
        self.assertNotIn("sk-geheim", text)
        neu = ein.standard()
        stand, fehler = ein.spiele_sicherung_ein(text, neu, ki.EMPFAENGER)
        self.assertIsNone(fehler)
        self.assertEqual(stand, (1, 0))
        self.assertEqual(neu["gelernt"]["woerter"]["kanst"], "kannst")

    def test_sicherung_ungepruefte_eintraege(self):
        w = ein.standard()
        roh = json.dumps({"schreibhilfe": 1, "woerter": {"../x": "y", "gut": "besser", "a": 5},
                          "inRuhe": ["liste"], "einstellungen": {"empfaenger": "gibtsnicht"}})
        stand, fehler = ein.spiele_sicherung_ein(roh, w, ki.EMPFAENGER)
        self.assertEqual(w["gelernt"]["woerter"], {"gut": "besser"})
        self.assertEqual(w["empfaenger"], "egal")
        self.assertEqual(ein.spiele_sicherung_ein("quatsch", w)[1], "Das war kein Sicherungs-Text.")
        self.assertIn("kein Sicherungs-Text", ein.spiele_sicherung_ein('{"a":1}', w)[1])

    def test_ansicht(self):
        d = os.path.join(self.ordner.name, "linux.json")
        ein.schreib_ansicht({"schrift": 9.0, "thema": "dunkel", "wortmarker": False, "stimme": "", "tempo": 0}, d)
        a = ein.lies_ansicht(d)
        self.assertEqual(a["schrift"], ein.SCHRIFT_MAX)       # begrenzt
        self.assertEqual(a["thema"], "dunkel")
        self.assertFalse(a["wortmarker"])


class TestPfade(unittest.TestCase):
    def test_alles_im_linux_ordner(self):
        for ziel in (pfade.DATEN_QUELLE, pfade.RESSOURCEN):
            self.assertTrue(str(ziel).startswith(os.path.realpath(LINUX)), ziel)
            self.assertTrue(ziel.is_dir(), ziel)
        # unter den Tests: der Wegwerf-Ordner, sonst linux/benutzer
        self.assertTrue(str(pfade.TEXT_DATEI).startswith(os.environ["SCHREIBHILFE_BENUTZER"]))

    def test_orte_aus_dem_arbeitsbaum(self):
        with tempfile.TemporaryDirectory() as t:
            hier = Path(t) / "linux"
            (hier / "benutzer").mkdir(parents=True)
            konfig, daten, umgelenkt = pfade.waehle_orte(hier, {})
            self.assertEqual((konfig, daten, umgelenkt), (hier / "benutzer", hier / "benutzer", False))

    def test_orte_installiert_nach_xdg(self):
        """Gehört der Programmordner root (wie unter /opt), nie hineinschreiben."""
        hier = Path("/usr/lib")                       # gehört root, liegt überall
        umgebung = {"XDG_CONFIG_HOME": "/k", "XDG_DATA_HOME": "/d"}
        konfig, daten, _ = pfade.waehle_orte(hier, umgebung)
        self.assertEqual(konfig, Path("/k/schreibhilfe"))
        self.assertEqual(daten, Path("/d/schreibhilfe"))
        # relative XDG-Werte zählen nach Spezifikation nicht
        konfig, daten, _ = pfade.waehle_orte(hier, {"XDG_CONFIG_HOME": "rel"})
        self.assertEqual(konfig, Path.home() / ".config" / "schreibhilfe")
        self.assertEqual(daten, Path.home() / ".local/share" / "schreibhilfe")

    def test_start_ueber_symlink_aus_fremdem_ordner(self):
        """main.py findet seine Module auch über einen Link und von woanders aus."""
        with tempfile.TemporaryDirectory() as t:
            link = Path(t) / "schreibhilfe"
            link.symlink_to(Path(LINUX) / "main.py")
            ausgabe = subprocess.run(
                [sys.executable, "-c",
                 "import runpy, sys; m = runpy.run_path(sys.argv[1]); print(m['HIER'])", str(link)],
                cwd=t, capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(ausgabe, os.path.realpath(LINUX))

    def test_alte_daten_werden_nur_kopiert(self):
        # Unter den Tests ist die Übernahme aus den echten Ordnern abgeschaltet.
        self.assertEqual(pfade.uebernehme_alte_daten(), [])

    def test_atomar(self):
        with tempfile.TemporaryDirectory() as t:
            ziel = os.path.join(t, "u", "d.txt")
            pfade.schreibe_atomar(ziel, "inhalt")
            with open(ziel, encoding="utf-8") as f:
                self.assertEqual(f.read(), "inhalt")
            self.assertFalse(os.path.exists(ziel + ".neu"))


if __name__ == "__main__":
    unittest.main()
