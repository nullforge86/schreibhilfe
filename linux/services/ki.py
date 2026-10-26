# -*- coding: utf-8 -*-
"""Die KI-Wege: Anthropic übers Netz oder Ollama auf diesem Rechner.

Die Anweisungen sind Wort für Wort dieselben wie in online/js/app.js und in der
LibreOffice-Erweiterung — was am Handy gilt, gilt hier auch. Wer eine ändert,
ändert damit beide Wege; tests/test_ki.py hält sie gegen das Original.

Die Aufrufe blockieren (bis zu zehn Minuten bei Ollama ohne Grafikkarte) und
gehören deshalb in einen Hintergrundfaden, nie in den Hauptfaden der Oberfläche.
"""

import json
import re
import ssl
import urllib.error
import urllib.request

from .einstellungen import OLLAMA_MARKE, steckbrief

# Für wen der Text ist. Wortgleich mit EMPFAENGER in online/js/app.js — steht
# hier ein anderer Satz, korrigieren Handy und PC verschieden.
#
# Das stand bis August 2026 als „Tonfall" da, mit vier Stufen und nur im
# Einstellungsfenster. Wer den Text liest, entscheidet aber über mehr als den
# Klang: Anrede, Länge, Aufbau, und was man sich sparen kann.
EMPFAENGER = {
    "egal": {
        "melde": "",
        "anweisung":
            "Lass den Tonfall genau so, wie er im Text steht: Förmliches bleibt "
            "förmlich, Lockeres bleibt locker. Ändere die Wortwahl nur da, wo sie "
            "falsch ist.",
    },
    "Amt": {
        "melde": "fürs Amt",
        "anweisung":
            "Der Text geht an eine Behörde — Amt, Jobcenter, Krankenkasse, "
            "Versicherung, Gericht. Halte den Tonfall durchgehend förmlich und "
            "höflich: Siezen, vollständige Sätze, keine Umgangssprache, keine "
            "Abkürzungen mitten im Satz. Sachlich bleiben auch dort, wo der Text "
            "ärgerlich klingt — der Vorwurf darf inhaltlich stehen bleiben, aber im "
            "ruhigen Ton. Stehen Anrede, Betreff oder ein Aktenzeichen schon da, "
            "bring sie in die übliche Form; fehlen sie, erfinde sie nicht.",
    },
    "Arbeit": {
        "melde": "für die Arbeit",
        "anweisung":
            "Der Text geht an jemanden aus dem Beruf — Chefin, Kollege, Kundschaft. "
            "Höflich und knapp: keine Ausschmückung, keine Floskelketten, aber auch "
            "nicht schroff. Ob geduzt oder gesiezt wird, entscheidet der Text — "
            "dreh das nicht um.",
    },
    "Freunde": {
        "melde": "für Freunde",
        "anweisung":
            "Der Text geht an jemanden, den man kennt — Familie, Freundin, Nachbar. "
            "Duzen, freundlich und zugewandt, kurze Sätze, ruhig so, wie man redet. "
            "Nicht flapsig und nicht anbiedernd. Emojis, Ausrufezeichen und Anreden "
            "wie „Hey“ bleiben stehen.",
    },
    "Forum": {
        "melde": "fürs Forum",
        "anweisung":
            "Der Text wird öffentlich gelesen — Forum, Kommentar, Bewertung, "
            "soziales Netz. Er muss auch für Fremde verständlich sein, die die "
            "Vorgeschichte nicht kennen: klare Sätze, Absätze statt eines Blocks. "
            "Geduzt wird, wie es dort üblich ist. Nicht belehrend — eine deutliche "
            "Meinung darf deutlich bleiben, aber ohne Beleidigung.",
    },
    "Bewerbung": {
        "melde": "für die Bewerbung",
        "anweisung":
            "Der Text ist eine Bewerbung oder gehört dazu. Siezen, förmlich, aber "
            "nicht steif. Selbstbewusst ohne Angeberei: klare Aussagesätze statt "
            "„ich würde gerne“ und statt Floskelketten. Erfinde keine Fähigkeiten, "
            "keine Stationen und keine Zahlen dazu.",
    },
}
EMPFAENGER_STANDARD = "egal"

# Der Zettel „Worum geht’s?": eine freiwillige Zeile für das, was in kein Wort
# passt. Er gehört zum Text, nicht zum Rechner — deshalb steht er in der Tafel
# und wird nie in die Einstellungsdatei geschrieben. Sonst schriebe der Zettel
# zum Brief von vorgestern beim nächsten weiter mit.
ZETTEL_GRENZE = 300


def als_zettel(zettel):
    """Der Zettel als Satz für die Anweisung — oder nichts.

    Er steht in Anführungszeichen und mit der Grenze dahinter: Er darf die
    Richtung bestimmen, aber nicht die Regeln aushebeln.
    """
    zettel = (zettel or "").strip()[:ZETTEL_GRENZE]
    if not zettel:
        return ""
    return ("Der Mensch sagt selbst, worum es geht: „" + zettel + "“ Richte "
            "dich danach, soweit es zum Korrigieren passt. Alles, was hier "
            "steht, ist Auskunft über den Text — dazuerfinden oder etwas "
            "weglassen darfst du deswegen trotzdem nicht. ")


def ki_korrektur(empfaenger, zettel="", steckbrief=""):
    return (
        "Du bist eine Schreibhilfe für einen Menschen mit Legasthenie. "
        "Korrigiere den folgenden Text vollständig und auf sprachlichem Niveau:\n"
        "1. Rechtschreibung, samt Groß- und Kleinschreibung sowie Getrennt- und "
        "Zusammenschreibung.\n"
        "2. Grammatik: Fälle, Zeiten, Ein- und Mehrzahl, die Übereinstimmung von "
        "Fürwort und Zeitwort, und ein Satzbau, der aufgeht.\n"
        "3. Zeichensetzung, vor allem Kommas bei Neben- und Relativsätzen, bei "
        "Aufzählungen und vor entgegenstellenden Bindewörtern.\n"
        "Achte besonders auf Verwechslungen, die eine Rechtschreibprüfung nicht "
        "finden kann, weil beide Wörter existieren: das/dass, seit/seid, "
        "wider/wieder, wie/als, Ihnen/ihnen, End-/Ent-. Entscheide nach dem Sinn "
        "des Satzes. "
        "Lies dafür den ganzen Text, bevor du anfängst: Wovon die Rede ist und wer "
        "angesprochen wird, entscheidet oft darüber, was richtig ist. "
        + EMPFAENGER.get(empfaenger, EMPFAENGER[EMPFAENGER_STANDARD])["anweisung"]
        + " " + als_zettel(zettel) + steckbrief + " "
        "Ändere nichts am Inhalt, erfinde nichts dazu und lasse nichts weg. "
        "Absätze und Zeilenumbrüche bleiben, wie sie sind. "
        "Der Text kann in jeder Sprache stehen; antworte in der Sprache des Textes. "
        "Antworte ausschließlich mit dem korrigierten Text: keine Erklärung, keine "
        "Anführungszeichen, keine Vorrede."
    )


def ki_vorschlag_anweisung(empfaenger, zettel=""):
    return (
    "Du bist eine Schreibhilfe für einen Menschen mit Legasthenie. Suche im "
    "folgenden Text die Sätze, die schwer zu lesen oder umständlich sind, und "
    "schlage für jeden eine klarere Fassung vor. "
    "Regeln: Ändere nichts am Inhalt und erfinde nichts dazu. "
    # Auch hier zählt, für wen der Text ist: „Klarer" heißt beim Amt etwas
    # anderes als bei einer Nachricht an den Nachbarn.
    + EMPFAENGER.get(empfaenger, EMPFAENGER[EMPFAENGER_STANDARD])["anweisung"]
    + " " + als_zettel(zettel) +
    "Benutze einfache, gebräuchliche Wörter und kurze Sätze. "
    "Der Text kann in jeder Sprache stehen. \"neu\" bleibt in der Sprache des "
    "Textes, \"grund\" schreibst du immer auf Deutsch. "
    "Nimm höchstens sechs Sätze, nur die, bei denen es wirklich hilft; ist der "
    "Text schon gut, nimm weniger oder keinen. "
    "\"alt\" ist der Satz zeichengenau aus dem Text — nicht kürzen, nicht "
    "glätten, nichts hinzufügen; er muss sich Zeichen für Zeichen im Text "
    "wiederfinden. \"neu\" ist die klarere Fassung, \"grund\" sagt in höchstens "
    "acht Wörtern, warum das leichter ist. "
    "Gibt es nichts zu verbessern, bleibt die Liste leer."
    )

VORSCHLAG_BAUPLAN = {
    "type": "object",
    "properties": {
        "vorschlaege": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "alt": {"type": "string"},
                    "neu": {"type": "string"},
                    "grund": {"type": "string"},
                },
                "required": ["alt", "neu", "grund"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["vorschlaege"],
    "additionalProperties": False,
}


def ki_uebersetzung(sprache):
    return (
        "Übersetze den folgenden Text nach " + sprache + ". "
        "Behalte Tonfall und Anrede bei: Ein Brief bleibt ein Brief, eine "
        "Nachricht an einen Freund bleibt locker. Übersetze sinngemäß und "
        "natürlich, nicht Wort für Wort. Ist der Text schon auf " + sprache + ", "
        "gib ihn unverändert zurück. Antworte ausschließlich mit der "
        "Übersetzung: keine Erklärung, keine Anführungszeichen, keine Vorrede."
    )


# --------------------------------------------------------------------------
# Preise und Zähler
# --------------------------------------------------------------------------

OLLAMA_ADRESSE = "http://localhost:11434"
# Ohne Grafikkarte rechnet ein 8-Milliarden-Modell an einem Brief mehrere
# Minuten. Die 180 Sekunden, die fürs Netz reichen, wären hier ein Abbruch
# mitten in der Arbeit.
OLLAMA_GEDULD = 600

# Dollar je Million Token. Gleichlautend mit der App.
PREISE = {
    "claude-opus-5":    {"hinein": 5, "heraus": 25},
    "claude-sonnet-5":  {"hinein": 3, "heraus": 15},
    "claude-haiku-4-5": {"hinein": 1, "heraus": 5},
}


def cent_fuer(modell, verbrauch):
    """Was die Anfrage gekostet hat, in US-Cent — oder None."""
    if not verbrauch:
        return None
    name = next((k for k in PREISE if str(modell or "").startswith(k)), None)
    if not name:
        return None
    preis = PREISE[name]
    dollar = ((verbrauch.get("input_tokens") or 0) / 1e6 * preis["hinein"]
              + (verbrauch.get("output_tokens") or 0) / 1e6 * preis["heraus"])
    return dollar * 100


def als_geld(cent):
    """Kleine Beträge brauchen Nachkommastellen, große nicht."""
    if cent >= 100:
        return ("%.2f" % (cent / 100)).replace(".", ",") + " $"
    if cent >= 1:
        return ("%.1f" % cent).replace(".", ",") + " Cent"
    return ("%.2f" % cent).replace(".", ",") + " Cent"


def kostenstand(werte):
    stand = werte.get("kosten") or {}
    anzahl = int(stand.get("anzahl") or 0)
    if not anzahl:
        return "Noch nichts verbraucht."
    return "Bisher: %d %s · %s (US)" % (
        anzahl, "Anfrage" if anzahl == 1 else "Anfragen",
        als_geld(float(stand.get("cent") or 0)))


def merke_kosten(werte, cent):
    stand = werte.setdefault("kosten", {"anzahl": 0, "cent": 0.0})
    stand["anzahl"] = int(stand.get("anzahl") or 0) + 1
    stand["cent"] = float(stand.get("cent") or 0) + cent


def baue_korrektur(werte, zettel=""):
    return ki_korrektur(werte.get("empfaenger"), zettel, steckbrief(werte))


# --------------------------------------------------------------------------
# Die Anfrage an die KI
# --------------------------------------------------------------------------

def ist_lokal(modell):
    """Läuft dieses Modell auf diesem Rechner?"""
    return str(modell or "").startswith(OLLAMA_MARKE)


def lokaler_name(modell):
    """„ollama:qwen3:8b“ → „qwen3:8b“. Der Doppelpunkt gehört zum Namen."""
    return str(modell or "")[len(OLLAMA_MARKE):]


def ki_bereit(werte):
    """Ist der gewählte Weg gangbar? Ollama braucht ein Modell, Claude einen Schlüssel."""
    if ist_lokal(werte.get("modell")):
        return bool(lokaler_name(werte.get("modell")).strip())
    return bool(werte.get("apiKey"))


def frage_ki(anweisung, text, werte, bauplan=None):
    """Gibt (ergebnis, fehler, cent) zurück — ergebnis oder fehler ist gesetzt.
    cent ist None, wenn nichts berechnet wurde (Ollama, unbekanntes Modell)."""
    if ist_lokal(werte.get("modell")):
        ergebnis, fehler = frage_ollama(anweisung, text, werte, bauplan)
        return ergebnis, fehler, None
    return frage_claude(anweisung, text, werte, bauplan)


def frage_claude(anweisung, text, werte, bauplan=None):
    if not werte.get("apiKey"):
        return None, ("Es ist kein API-Schlüssel hinterlegt.\n\n"
                      "Oben rechts unter „Einstellungen“ eintragen."), None

    modell = werte["modell"]
    anfrage = {
        "model": modell,
        "max_tokens": 16000,
        "system": anweisung,
        "messages": [{"role": "user", "content": text}],
    }
    ausgabe = {}
    if modell != "claude-haiku-4-5":
        ausgabe["effort"] = "low"
        anfrage["thinking"] = {"type": "adaptive"}
    if bauplan:
        ausgabe["format"] = {"type": "json_schema", "schema": bauplan}
    if ausgabe:
        anfrage["output_config"] = ausgabe

    bitte = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(anfrage).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": werte["apiKey"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(bitte, timeout=180,
                                    context=ssl.create_default_context()) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except urllib.error.HTTPError as fehler:
        rumpf = ""
        try:
            rumpf = json.loads(fehler.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:                                # noqa: BLE001
            pass
        if "credit balance" in rumpf.lower():
            return None, "Das Guthaben ist aufgebraucht.", None
        if fehler.code == 401:
            return None, "Der Schlüssel wird abgelehnt. Bitte in den Einstellungen prüfen.", None
        return None, "Fehler %s%s" % (fehler.code, (" (" + rumpf + ")") if rumpf else ""), None
    except urllib.error.URLError as fehler:
        return None, "Keine Verbindung: %s" % (fehler.reason,), None
    except Exception as fehler:                          # noqa: BLE001
        return None, "Es hat nicht geklappt: %s" % (fehler,), None

    if daten.get("stop_reason") == "refusal":
        return None, "Die KI wollte diesen Text nicht bearbeiten.", None

    cent = cent_fuer(modell, daten.get("usage"))
    stuecke = [b.get("text", "") for b in daten.get("content", []) if b.get("type") == "text"]
    ergebnis = "".join(stuecke).strip()
    if not ergebnis:
        return None, "Es kam keine Antwort zurück.", None
    return ergebnis, None, cent


def ohne_gruebeln(roh):
    """Denkmodelle schreiben ihr Grübeln in <think>-Klammern mit — im Brief
    eines Menschen hat das nichts zu suchen."""
    ohne = re.sub(r"<think>.*?</think>", "", str(roh), flags=re.S | re.I)
    stelle = ohne.rfind("</think>")        # eine Klammer, die nur zugeht
    return ohne[stelle + 8:] if stelle >= 0 else ohne


def ollama_modelle(adresse=OLLAMA_ADRESSE):
    """Welche Modelle auf dem Rechner liegen — der Dienst weiß es selbst.
    Ist er unerreichbar, eine leere Liste: Die Einstellungen sollen aufgehen,
    auch wenn Ollama gerade aus ist."""
    try:
        bitte = urllib.request.Request(adresse.rstrip("/") + "/api/tags",
                                       headers={"accept": "application/json"})
        with urllib.request.urlopen(bitte, timeout=3) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
        namen = [m["name"] for m in daten.get("models") or [] if m.get("name")]
        # Code-Modelle sinken nach unten: „codellama“ stünde sonst ganz oben
        # und damit als Vorauswahl da — für einen Brief ans Amt unbrauchbar.
        return sorted(namen, key=lambda n: (bool(re.search(r"cod(e|er)", n, re.I)), n))
    except Exception:                                    # noqa: BLE001
        return []


def frage_ollama(anweisung, text, werte, bauplan=None):
    """Dieselbe Anfrage, nur an den eigenen Rechner. Kein Schlüssel, keine
    Kosten, kein Internet — der Text verlässt das Gerät nicht."""
    modell = lokaler_name(werte.get("modell")).strip()
    if not modell:
        return None, "Es ist noch kein Modell gewählt.\n\nIn den Einstellungen eines wählen."

    adresse = OLLAMA_ADRESSE
    anfrage = {
        "model": modell,
        "stream": False,
        "messages": [
            {"role": "system", "content": anweisung},
            {"role": "user", "content": text},
        ],
        "options": {"temperature": 0.2},            # Korrigieren ist kein Dichten
        # Denkmodelle grübeln sonst minutenlang (gemessen: 3 Minuten gegen 19
        # Sekunden). Ältere Ollama-Fassungen lehnen die Zeile bei Modellen ohne
        # Denken mit Fehler 400 ab; dann wird noch einmal ohne sie gefragt.
        "think": False,
    }
    if bauplan:
        anfrage["format"] = bauplan

    def schicke(nutzlast):
        bitte = urllib.request.Request(
            adresse + "/api/chat", data=json.dumps(nutzlast).encode("utf-8"),
            headers={"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(bitte, timeout=OLLAMA_GEDULD) as antwort:
                return json.loads(antwort.read().decode("utf-8")), None, ""
        except urllib.error.HTTPError as fehler:
            rumpf = ""
            try:
                rumpf = fehler.read().decode("utf-8", "replace")
            except Exception:                        # noqa: BLE001
                pass
            return None, fehler.code, rumpf

    try:
        daten, code, rumpf = schicke(anfrage)
        if code == 400 and "think" in rumpf.lower():
            anfrage.pop("think", None)
            daten, code, rumpf = schicke(anfrage)

        if code == 404:
            return None, ("Das Modell „%s“ liegt nicht auf diesem Rechner.\n\n"
                          "In den Einstellungen ein anderes wählen — oder es im "
                          "Terminal holen:\n    ollama pull %s" % (modell, modell))
        if code is not None:
            kurz = rumpf.strip()[:200]
            return None, "Ollama meldet Fehler %s%s" % (code, (" (" + kurz + ")") if kurz else "")
    except urllib.error.URLError as fehler:
        return None, ("Ollama ist unter %s nicht zu erreichen.\n\n"
                      "Läuft der Dienst? Im Terminal nachsehen:\n"
                      "    systemctl status ollama\n\n(%s)" % (adresse, fehler.reason))
    except Exception as fehler:                      # noqa: BLE001
        return None, "Es hat nicht geklappt: %s" % (fehler,)

    ergebnis = ohne_gruebeln((daten.get("message") or {}).get("content") or "").strip()
    return (ergebnis, None) if ergebnis else (None, "Es kam keine Antwort zurück.")


def lies_liste(antwort):
    """Die Antwort folgt dem Bauplan: ein Objekt mit dem Feld „vorschlaege“.
    Der zweite und dritte Anlauf sind Notausgänge, falls ein Modell ohne Bauplan
    antwortet oder die Antwort in einen Code-Zaun packt."""
    roh = (antwort or "").strip()
    for versuch in (roh, _ausschneiden(roh, "{", "}"), _ausschneiden(roh, "[", "]")):
        if not versuch:
            continue
        try:
            daten = json.loads(versuch)
        except ValueError:
            continue
        if isinstance(daten, dict) and isinstance(daten.get("vorschlaege"), list):
            return daten["vorschlaege"]
        if isinstance(daten, list):
            return daten
    return None


def _ausschneiden(text, auf, zu):
    von, bis = text.find(auf), text.rfind(zu)
    return text[von:bis + 1] if von != -1 and bis > von else ""
