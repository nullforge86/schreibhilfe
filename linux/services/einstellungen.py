# -*- coding: utf-8 -*-
"""Einstellungen und Gedächtnis.

Gelesen und geschrieben wird dieselbe Datei wie in der LibreOffice-Erweiterung
(~/.config/schreibhilfe/einstellungen.json), im selben Format: Wer dort schon
einen Schlüssel eingetragen oder Wörter gelernt hat, findet sie hier wieder.
Der Sicherungs-Text ist wortgleich mit dem der Handy-App.

Was nur dieses Fenster betrifft (Schrift, Hell/Dunkel, Stimme), liegt in
linux.json daneben — LibreOffice stutzt die gemeinsame Datei beim Schreiben auf
die Felder zurück, die es kennt.
"""

import copy
import json
import re

from . import pfade, pruefung

MODELLE = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]
MODELL_NAMEN = {
    "claude-opus-5": "Beste Qualität · Opus 5",
    "claude-sonnet-5": "Mittelweg · Sonnet 5",
    "claude-haiku-4-5": "Günstig & schnell · Haiku 4.5",
}
SPRACHEN = ["Englisch", "Deutsch", "Türkisch", "Russisch", "Ukrainisch",
            "Polnisch", "Rumänisch", "Arabisch", "Französisch", "Spanisch",
            "Italienisch", "Griechisch", "Niederländisch", "Portugiesisch"]

OLLAMA_MARKE = "ollama:"

EMPFAENGER_STANDARD = "egal"
# Wer den alten Tonfall eingestellt hatte, behält seine Wahl.
TONFALL_ALT = {
    "Wie geschrieben": "egal",
    "Förmlich (Amt)": "Amt",
    "Freundlich": "Freunde",
    "Kurz und sachlich": "egal",
}

# So oft darf ein Kasten ungenutzt erscheinen, bevor die App das Wort in Ruhe lässt.
LERN_SCHWELLE = 5
SICHERUNG_GRENZE = 2000
GELERNTES_WORT = re.compile(r"^[a-zäöüß-]{1,40}$")


def standard():
    return {
        "apiKey": "",
        "modell": "claude-opus-5",
        "empfaenger": EMPFAENGER_STANDARD,
        "sprache": "Englisch",
        "gelernt": {"woerter": {}, "inRuhe": {}},
        "kosten": {"anzahl": 0, "cent": 0.0},
    }


def lies_einstellungen(datei=None, empfaenger_namen=None):
    """Liest die gemeinsame Einstellungsdatei. Fehlt sie oder ist sie kaputt,
    gilt die Vorgabe — das Fenster soll in jedem Fall aufgehen.

    empfaenger_namen: die gültigen Empfänger (aus ki.EMPFAENGER); ohne Angabe
    wird nur auf einen Text geprüft.
    """
    werte = standard()
    try:
        with open(datei or pfade.EINSTELLUNGEN_DATEI, "r", encoding="utf-8") as f:
            gespeichert = json.load(f)
    except (OSError, ValueError):
        return werte
    if not isinstance(gespeichert, dict):
        return werte

    for name in ("apiKey", "modell", "empfaenger", "sprache"):
        if isinstance(gespeichert.get(name), str):
            werte[name] = gespeichert[name]
    # Eine Datei von vor August 2026 kennt nur „tonfall“.
    if not isinstance(gespeichert.get("empfaenger"), str):
        werte["empfaenger"] = TONFALL_ALT.get(gespeichert.get("tonfall"),
                                              EMPFAENGER_STANDARD)
    if empfaenger_namen is not None and werte["empfaenger"] not in empfaenger_namen:
        werte["empfaenger"] = EMPFAENGER_STANDARD

    gelernt = gespeichert.get("gelernt")
    if isinstance(gelernt, dict):
        if isinstance(gelernt.get("woerter"), dict):
            werte["gelernt"]["woerter"] = gelernt["woerter"]
        if isinstance(gelernt.get("inRuhe"), dict):
            werte["gelernt"]["inRuhe"] = gelernt["inRuhe"]
        if isinstance(gelernt.get("gezeigt"), dict):
            werte["gelernt"]["gezeigt"] = gelernt["gezeigt"]
    kosten = gespeichert.get("kosten")
    if isinstance(kosten, dict):
        if isinstance(kosten.get("anzahl"), (int, float)):
            werte["kosten"]["anzahl"] = int(kosten["anzahl"])
        if isinstance(kosten.get("cent"), (int, float)):
            werte["kosten"]["cent"] = float(kosten["cent"])
    return werte


def schreib_einstellungen(werte, datei=None):
    """Der Schlüssel steht da drin — niemand sonst muss die Datei lesen können."""
    pfade.schreibe_atomar(datei or pfade.EINSTELLUNGEN_DATEI,
                          json.dumps(werte, ensure_ascii=False, indent=1),
                          rechte=0o600)


# --------------------------------------------------------------------------
# Ansicht: nur für dieses Fenster
# --------------------------------------------------------------------------

ANSICHT_STANDARD = {
    "schrift": 1.0,          # Faktor; 1.0 = 13 pt im Schreibfeld
    "thema": "auto",         # auto | hell | dunkel
    "wortmarker": True,      # Streifen hinter dem Wort, an dem man schreibt
    "stimme": "",
    "tempo": 0,
}
SCHRIFT_MIN, SCHRIFT_MAX = 0.8, 2.2


def lies_ansicht(datei=None):
    ansicht = dict(ANSICHT_STANDARD)
    try:
        with open(datei or pfade.ANSICHT_DATEI, "r", encoding="utf-8") as f:
            gespeichert = json.load(f)
    except (OSError, ValueError):
        return ansicht
    if not isinstance(gespeichert, dict):
        return ansicht
    if isinstance(gespeichert.get("schrift"), (int, float)):
        ansicht["schrift"] = max(SCHRIFT_MIN, min(SCHRIFT_MAX, float(gespeichert["schrift"])))
    if gespeichert.get("thema") in ("auto", "hell", "dunkel"):
        ansicht["thema"] = gespeichert["thema"]
    if isinstance(gespeichert.get("wortmarker"), bool):
        ansicht["wortmarker"] = gespeichert["wortmarker"]
    if isinstance(gespeichert.get("stimme"), str):
        ansicht["stimme"] = gespeichert["stimme"]
    if isinstance(gespeichert.get("tempo"), (int, float)):
        ansicht["tempo"] = max(-100, min(100, int(gespeichert["tempo"])))
    return ansicht


def schreib_ansicht(ansicht, datei=None):
    pfade.schreibe_atomar(datei or pfade.ANSICHT_DATEI,
                          json.dumps(ansicht, ensure_ascii=False, indent=1))


# --------------------------------------------------------------------------
# Das Gedächtnis: gesammelt wird an genau einer Stelle — beim Annehmen einer
# Änderung. Dort ist zweifelsfrei bekannt, was der Mensch wollte.
# --------------------------------------------------------------------------

def _gedaechtnis(werte):
    g = werte.setdefault("gelernt", {})
    g.setdefault("woerter", {})
    g.setdefault("inRuhe", {})
    g.setdefault("gezeigt", {})
    return g


def ist_wortebene(fund):
    """Ein Fund taugt nur zum Lernen, wenn er sich auf das WORT bezieht und
    nicht auf die Stelle: Ein fehlendes Komma gilt nur dort, wo es gefunden wurde."""
    alt, neu = fund.get("alt"), fund.get("neu")
    return (bool(fund.get("wortEbene")) and isinstance(alt, str) and isinstance(neu, str)
            and re.match(r"^[A-Za-zÄÖÜäöüß-]+$", alt) is not None
            and neu != "" and neu.strip() == neu)


def merke_aenderung(fund, werte):
    """Gelernt wird nur, was der Mensch selbst NICHT richtig geschrieben hat:
    Steht „alt“ im Wörterbuch, hängt die Korrektur am Satz und nicht am Wort."""
    if not ist_wortebene(fund):
        return False
    wort = fund["alt"].lower()
    if wort in pruefung.lade_woerter():
        return False
    # Was mit dem Wort nichts zu tun hat, war nie eine Korrektur.
    if not pruefung.ist_korrektur(wort, fund["neu"]):
        return False
    g = _gedaechtnis(werte)
    g["woerter"][wort] = fund["neu"]
    g["gezeigt"].pop(wort, None)
    g["inRuhe"].pop(wort, None)
    return True


def merke_gezeigt(funde, werte):
    """Wer denselben Kasten wieder und wieder stehen lässt, sagt damit: Das Wort
    ist richtig so. Nach LERN_SCHWELLE Malen kommt es auf die Ruhe-Liste."""
    g = _gedaechtnis(werte)
    geaendert = False
    for fund in funde:
        if not ist_wortebene(fund):
            continue
        wort = fund["alt"].lower()
        if wort in g["woerter"] or wort in g["inRuhe"]:
            continue
        g["gezeigt"][wort] = g["gezeigt"].get(wort, 0) + 1
        if g["gezeigt"][wort] >= LERN_SCHWELLE:
            g["inRuhe"][wort] = True
            del g["gezeigt"][wort]
        geaendert = True
    return geaendert


def gelernt_fuer_pruefung(werte):
    g = _gedaechtnis(werte)
    return {"woerter": g["woerter"], "inRuhe": g["inRuhe"]}


def eigenes_wort(werte, wort):
    """Die eigene Schreibweise für ein Wort — oder nichts."""
    w = str(wort).lower()
    gemerkt = _gedaechtnis(werte)["woerter"].get(w)
    if not gemerkt:
        return None
    if not pruefung.ist_korrektur(w, gemerkt):
        _gedaechtnis(werte)["woerter"].pop(w, None)       # aufräumen
        return None
    return gemerkt


def schon_gewaehlt(werte):
    return set(_gedaechtnis(werte)["woerter"].values())


def vergiss_alles(werte):
    werte["gelernt"] = {"woerter": {}, "inRuhe": {}, "gezeigt": {}}


def gedaechtnis_stand(werte):
    g = _gedaechtnis(werte)
    if not g["woerter"] and not g["inRuhe"]:
        return "Noch nichts gelernt."
    teile = []
    if g["woerter"]:
        teile.append("%d %s gelernt" % (len(g["woerter"]),
                     "Schreibweise" if len(g["woerter"]) == 1 else "Schreibweisen"))
    if g["inRuhe"]:
        teile.append("%d %s in Ruhe" % (len(g["inRuhe"]),
                     "Wort" if len(g["inRuhe"]) == 1 else "Wörter"))
    return " · ".join(teile)


def steckbrief(werte):
    """Was die App über diesen Menschen weiß — geht als ein Satz an die KI."""
    g = _gedaechtnis(werte)
    woerter = list(g["woerter"].items())[-12:]
    ruhe = list(g["inRuhe"].keys())[:12]
    teile = []
    if woerter:
        teile.append("Dieser Mensch schreibt erfahrungsgemäß diese Wörter falsch — "
                     "achte besonders darauf: "
                     + ", ".join("%s statt %s" % (f, r) for f, r in woerter) + ".")
    if ruhe:
        teile.append("Diese Wörter sind so gewollt und bleiben unangetastet: "
                     + ", ".join(ruhe) + ".")
    return (" " + " ".join(teile)) if teile else ""


# --------------------------------------------------------------------------
# Sicherungs-Text — wortgleich mit der Handy-App
# --------------------------------------------------------------------------

def baue_sicherung(werte):
    """Der API-Schlüssel bleibt bewusst draußen, der Zettel ebenso."""
    g = _gedaechtnis(werte)
    return json.dumps({
        "schreibhilfe": 1,
        "woerter": g["woerter"],
        "inRuhe": g["inRuhe"],
        "einstellungen": {n: werte[n] for n in ("empfaenger", "modell", "sprache")},
    }, ensure_ascii=False)


def spiele_sicherung_ein(roh, werte, empfaenger_namen=None):
    """Nimmt einen Sicherungs-Text auf. Gibt ((neue_woerter, neue_ruhe), None)
    oder (None, Fehlertext) zurück. Alles Ankommende ist ungeprüft, deshalb
    wird jeder Eintrag einzeln angesehen."""
    try:
        daten = json.loads((roh or "").strip())
    except ValueError:
        return None, "Das war kein Sicherungs-Text."
    if not isinstance(daten, dict) or daten.get("schreibhilfe") != 1:
        return None, "Das ist kein Sicherungs-Text der Schreibhilfe."

    g = _gedaechtnis(werte)
    woerter, ruhe = g["woerter"], g["inRuhe"]
    neu_w = neu_r = 0

    gesendet = daten.get("woerter")
    for falsch, richtig in (gesendet.items() if isinstance(gesendet, dict) else ()):
        if len(woerter) >= SICHERUNG_GRENZE:
            break
        if not isinstance(falsch, str) or not GELERNTES_WORT.match(falsch):
            continue
        if not isinstance(richtig, str) or not richtig.strip() or len(richtig) > 60:
            continue
        if woerter.get(falsch) != richtig:
            neu_w += 1
        woerter[falsch] = richtig

    gesendet = daten.get("inRuhe")
    for wort in (gesendet if isinstance(gesendet, dict) else ()):
        if len(ruhe) >= SICHERUNG_GRENZE:
            break
        if not isinstance(wort, str) or not GELERNTES_WORT.match(wort):
            continue
        if not ruhe.get(wort):
            neu_r += 1
        ruhe[wort] = True

    einst = daten.get("einstellungen")
    einst = einst if isinstance(einst, dict) else {}
    for name in ("empfaenger", "modell", "sprache"):
        if isinstance(einst.get(name), str):
            werte[name] = einst[name]
    if not isinstance(einst.get("empfaenger"), str) and isinstance(einst.get("tonfall"), str):
        werte["empfaenger"] = TONFALL_ALT.get(einst["tonfall"], EMPFAENGER_STANDARD)
    if empfaenger_namen is not None and werte["empfaenger"] not in empfaenger_namen:
        werte["empfaenger"] = EMPFAENGER_STANDARD
    return (neu_w, neu_r), None


def kopie(werte):
    return copy.deepcopy(werte)
