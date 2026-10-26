# -*- coding: utf-8 -*-
"""Wortvorschläge: Fortsetzen, Verbessern und Suchen nach dem Klang.

Übersetzung von koelnerPhonetik, klingtWie, vorschlaegeFuer und faengtAnMit aus
online/js/app.js — dieselben Regeln, dieselbe Reihenfolge. Die Vorschläge sind
Angebote, keine Funde: Der Klang findet mehr, aber auch mehr daneben. Die
Prüfung (pruefung.py) bleibt deshalb so eng, wie sie ist.
"""

import bisect
import re
import threading

from . import pruefung

# --------------------------------------------------------------------------
# Kölner Phonetik — was gleich klingt, ist gemeint
# --------------------------------------------------------------------------


def koelner_phonetik(wort):
    w = str(wort).upper()
    for alt, neu in (("Ä", "A"), ("Ö", "O"), ("Ü", "U"), ("ß", "SS"),
                     # „Qu“ spricht man „kw“, „Ph“ wie „F“ — die Kölner
                     # Phonetik sieht beides nicht vor.
                     ("QU", "KW"), ("PH", "F")):
        w = w.replace(alt, neu)
    w = re.sub(r"[^A-Z]", "", w)
    if not w:
        return ""

    laute = []
    for i, c in enumerate(w):
        vor = w[i - 1] if i > 0 else ""
        nach = w[i + 1] if i + 1 < len(w) else ""
        code = None

        if c in "AEIOUYJ":
            code = "0"
        elif c == "B":
            code = "1"
        elif c == "P":
            code = "3" if nach == "H" else "1"
        elif c in "DT":
            code = "8" if nach and nach in "CSZ" else "2"
        elif c in "FVW":
            code = "3"
        elif c in "GKQ":
            code = "4"
        elif c == "C":
            if i == 0:
                code = "4" if nach and nach in "AHKLOQRUX" else "8"
            elif vor in ("S", "Z"):
                code = "8"
            else:
                code = "4" if nach and nach in "AHKOQUX" else "8"
        elif c == "X":
            code = "8" if vor and vor in "CKQ" else "48"
        elif c == "L":
            code = "5"
        elif c in "MN":
            code = "6"
        elif c == "R":
            code = "7"
        elif c in "SZ":
            code = "8"
        # H trägt keinen eigenen Laut.

        if code is not None:
            laute.append(code)

    # Doppelte zusammenziehen, Nullen streichen — außer der ersten.
    aus = ""
    for laut in laute:
        for z in laut:
            if not aus or z != aus[-1]:
                aus += z
    return aus[0] + aus[1:].replace("0", "")


# --------------------------------------------------------------------------
# Was im Deutschen ständig vorkommt. Ohne diese Liste gewönne beim Vorschlagen
# der kürzere Abstand — „fileicht“ würde zu „flicht“ statt zu „vielleicht“.
# --------------------------------------------------------------------------

HAEUFIG = frozenset("""
    der die das den dem des ein eine einen einem einer eines und oder aber
    ich du er sie es wir ihr mich dich sich uns euch mir dir ihm ihnen mein
    dein sein unser ist sind war waren bin bist wird werden wurde wurden
    haben hat hatte hatten habe kann können konnte konnten muss müssen
    musste mussten will wollen wollte darf dürfen soll sollen sollte möchte
    mag nicht kein keine keinen nichts noch schon nur auch sehr mehr weniger
    viel viele vielen wenig alle alles jeder jede jedes man jemand niemand
    für mit von zu zum zur bei nach aus über unter vor hinter neben zwischen
    ohne gegen um auf an in im ins am seit bis durch wegen trotz während
    innerhalb außerhalb wenn dann weil dass ob wie was wer wo wann warum
    wieder immer nie oft manchmal heute gestern morgen jetzt bald später
    früher hier dort da dahin dorthin vielleicht sicher bestimmt wirklich
    eigentlich natürlich leider hoffentlich gut gute guten besser beste
    schlecht groß große klein kleine neu neue alt alte lang lange kurz kurze
    hoch hohe tief richtig falsch wichtig einfach schwierig jahr jahre monat
    monate woche wochen tag tage stunde minute zeit zeiten mensch menschen
    frau frauen mann männer kind kinder familie vater mutter haus häuser
    wohnung stadt land straße weg geld arbeit beruf schule brief antrag
    bescheid amt behörde termin termine unterlagen frist widerspruch anlage
    kopie original nachweis bestätigung mitteilung schreiben antwort sehr
    geehrte geehrter damen herren freundlichen grüßen hochachtungsvoll bitte
    danke gern gerne leid entschuldigung verzeihung machen macht gemacht tun
    getan geben gibt gegeben nehmen nimmt genommen sagen sagt gesagt sehen
    sieht gesehen kommen kommt gekommen gehen geht gegangen stehen steht
    gestanden liegen liegt gelegen bleiben bleibt geblieben finden findet
    gefunden bringen bringt gebracht halten hält gehalten sprechen spricht
    gesprochen schreiben schreibt geschrieben lesen liest gelesen verstehen
    versteht verstanden wissen weiß gewusst denken denkt gedacht brauchen
    braucht gebraucht helfen hilft geholfen fragen fragt gefragt arbeiten
    arbeitet gearbeitet warten wartet gewartet zahlen zahlt gezahlt bekommen
    bekommt erhalten erhält beantragen beantragt prüfen prüft geprüft
    stellen stellt gestellt setzen setzt gesetzt legen legt gelegt stimmt
    stimmen berechnung zahlung betrag summe kosten rechnung grund gründe
    fall fälle frage fragen sache sachen ding dinge teil teile seite seiten
    stelle stellen art weise möglichkeit grundlage wohl doch schon eben halt
    zwar also somit deshalb darum dafür dagegen qualität quittung quartal
""".split())


def wort_abstand_voll(a, b):
    """Einfügen, Löschen, Ersetzen — das gewohnte Maß (ohne Vertauschen)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    zeile = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        vorherige = zeile[0]
        zeile[0] = i
        for j in range(1, len(b) + 1):
            diagonal = vorherige
            vorherige = zeile[j]
            zeile[j] = min(zeile[j] + 1, zeile[j - 1] + 1,
                           diagonal + (0 if a[i - 1] == b[j - 1] else 1))
    return zeile[len(b)]


# --------------------------------------------------------------------------
# Die Klangtafel: einmal gebaut, dann nachgeschlagen. 355.000 Wörter durch die
# Phonetik zu schicken dauert in Python einige Sekunden — deshalb im
# Hintergrund, und bis sie fertig ist, gibt es eben nur die Nachbarsuche.
# --------------------------------------------------------------------------

_tafel = None
_sortiert = None          # alle Wörter alphabetisch — für die Suche nach dem Anfang
_tafel_sperre = threading.Lock()


def klangtafel_bauen():
    global _tafel, _sortiert
    with _tafel_sperre:
        if _tafel is not None:
            return _tafel
        tafel = {}
        sortiert = sorted(pruefung.lade_woerter())
        for wort in sortiert:
            if len(wort) < 4:      # zu kurz: klingt zu oft gleich
                continue
            klang = koelner_phonetik(wort)
            if klang:
                tafel.setdefault(klang, []).append(wort)
        _sortiert = sortiert
        _tafel = tafel
        return _tafel


def klangtafel_im_hintergrund():
    threading.Thread(target=klangtafel_bauen, daemon=True,
                     name="klangtafel").start()


def klingt_wie(wort, hoechstens=15):
    """Wörter, die so klingen wie das eingetippte — die ähnlichsten zuerst.
    Ist die Tafel noch nicht fertig, gibt es (noch) nichts."""
    if _tafel is None:
        return []
    w = str(wort).lower()
    if len(w) < 4:
        return []
    klang = koelner_phonetik(w)
    if not klang:
        return []
    gleiche = [k for k in _tafel.get(klang, ()) if k != w]
    if len(gleiche) <= 1:
        return gleiche

    def gewicht(k):
        return wort_abstand_voll(w, k) - (2 if k in HAEUFIG else 0)

    gleiche.sort(key=lambda k: (gewicht(k), abs(len(k) - len(w)),
                                pruefung._de_schluessel(k)))
    return gleiche[:hoechstens]


def _ist_teilfolge(kurz, lang):
    i = 0
    for c in lang:
        if i < len(kurz) and kurz[i] == c:
            i += 1
    return i == len(kurz)


def vorschlaege_fuer(wort, gelernt_wort=None, hoechstens=6):
    """Mehrere Verbesserungen zu einem Wort. gelernt_wort: die eigene
    Schreibweise, die dieser Mensch schon einmal gewählt hat (kommt nach oben)."""
    woerter = pruefung.lade_woerter()
    if not woerter:
        return []
    w = str(wort).lower()
    if len(w) < 2 or len(w) > 24 or w in woerter:
        return []

    treffer = [k for k in pruefung.nachbar_woerter(w) if k in woerter]
    klang = klingt_wie(w)
    for kandidat in klang:
        if kandidat not in treffer:
            treffer.append(kandidat)

    gelernt = gelernt_wort or None
    if gelernt and gelernt not in treffer:
        treffer.insert(0, gelernt)

    klang_gleich = set(klang)

    def rang(k):
        if k == gelernt:
            return -1
        if _ist_teilfolge(w, k):
            return 0
        if _ist_teilfolge(k, w):
            return 1
        return 1 if k in klang_gleich else 2

    def gleicher_anfang(k):
        i = 0
        while i < len(k) and i < len(w) and k[i] == w[i]:
            i += 1
        return i

    def gewicht(k):
        return wort_abstand_voll(w, k) - (2 if k in HAEUFIG else 0)

    treffer.sort(key=lambda k: (rang(k), gewicht(k), -gleicher_anfang(k),
                                len(k), pruefung._de_schluessel(k)))
    gesehen, aus = set(), []
    for k in treffer:
        if k not in gesehen:
            gesehen.add(k)
            aus.append(k)
    return aus[:hoechstens]


def faengt_an_mit(anfang, schon_gewaehlt=(), hoechstens=8):
    """Wörter, die so anfangen — zuerst, was dieser Mensch schon gewählt hat,
    dann was ständig vorkommt, dann kurze vor langen. „Kurz“ allein wäre falsch:
    Bei „wid“ kämen Widder und widern, während „Widerspruch“ fehlte."""
    woerter = pruefung.lade_woerter()
    if not woerter:
        return []
    a = str(anfang).lower()
    if len(a) < 3 or len(a) > 20:
        return []
    if _sortiert is not None:
        # Alphabetisch sortiert: alle Wörter mit diesem Anfang liegen nebeneinander.
        i = bisect.bisect_left(_sortiert, a)
        treffer = []
        while i < len(_sortiert) and _sortiert[i].startswith(a):
            if len(_sortiert[i]) > len(a):
                treffer.append(_sortiert[i])
            i += 1
    else:
        treffer = [w for w in woerter if len(w) > len(a) and w.startswith(a)]
    if not treffer:
        return []
    gewaehlt = set(schon_gewaehlt)
    treffer.sort(key=lambda x: (0 if x in gewaehlt else 1,
                                0 if x in HAEUFIG else 1,
                                len(x), pruefung._de_schluessel(x)))
    return treffer[:hoechstens]


# --------------------------------------------------------------------------
# Die Schreibweise des Getippten übernehmen
# --------------------------------------------------------------------------

# Diese Endungen sind im Deutschen ausnahmslos Hauptwörter (Wortbildung, keine
# Schätzung). Die Mindestlänge muss sein: „jung“ endet auf -ung und ist keines.
_HAUPTWORT_ENDE = re.compile(
    r"(ung|ungen|heit|heiten|keit|keiten|schaft|schaften|tion|tionen|tät|"
    r"täten|nis|nisse|tum|ismus|ment|mente)$")


def ist_hauptwort(wort):
    return len(wort) >= 7 and bool(_HAUPTWORT_ENDE.search(wort))


def mit_schreibweise(getippt, wort):
    if re.match(r"^[A-ZÄÖÜ]", wort):
        return wort
    if re.match(r"^[A-ZÄÖÜ]", getippt) or ist_hauptwort(wort):
        return wort[0].upper() + wort[1:]
    return wort
