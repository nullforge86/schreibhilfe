# -*- coding: utf-8 -*-
"""Vorlesen über Piper (gute Stimme, offline) oder den Sprachdienst des Rechners.

Im Browser gibt es dafür speechSynthesis; hier spricht der Arbeitsplatz selbst.
Über einen Fehler liest das Auge hinweg, das Ohr stolpert darüber — deshalb
gehört das Vorlesen in ein Schreibprogramm.

Alle Aufrufe kehren sofort zurück: gesprochen wird in Kindprozessen.
"""

import json
import os
import shutil
import subprocess
import threading

from . import pfade

# Was gerade vorgelesen wird — damit ein zweiter Antipp es anhalten kann.
VORLESER = {"lauf": None, "rechner": None}

# Eine Stimme, die nicht nach Maschine klingt.
#
# speech-dispatcher spricht hier über espeak-ng, und das ist ein
# Formantsynthesizer: Er rechnet Laute zusammen, statt sie aus Aufnahmen zu
# setzen. Er KANN nicht menschlich klingen — das ist Bauart, nicht Einstellung.
# Wer sich seinen Brief vorlesen lässt, um Fehler zu hören, hört sonst vor
# allem espeak.
#
# Piper ist ein neuronaler Synthesizer, läuft offline auf der CPU und braucht
# für viereinhalb Sekunden Ton eine Viertelsekunde. Er liegt außerhalb des
# Projekts unter ~/.local/share/schreibhilfe/piper — 90 MB gehören nicht ins
# Repo. Ist er da, spricht er; sonst bleibt es bei spd-say.
PIPER_ORT = pfade.PIPER_ORT
PIPER = PIPER_ORT / "piper" / "piper"

# Wie die Dateinamen auf Deutsch heißen. Wer „de_DE-eva_k-x_low" liest, weiß
# nicht, ob das eine Frau ist — und genau danach sucht man in einer Liste.
PIPER_NAMEN = {
    "de_DE-thorsten-medium":  "Thorsten (männlich)",
    "de_DE-thorsten-high":    "Thorsten, feiner (männlich)",
    "de_DE-thorsten-low":     "Thorsten, gröber (männlich)",
    "de_DE-karlsson-low":     "Karlsson (männlich)",
    "de_DE-pavoque-low":      "Pavoque (männlich)",
    "de_DE-kerstin-low":      "Kerstin (weiblich)",
    "de_DE-ramona-low":       "Ramona (weiblich)",
    "de_DE-eva_k-x_low":      "Eva (weiblich)",
    "de_DE-mls-medium":       "Gemischt (mehrere Sprecher)",
    "de_DE-thorsten_emotional-medium": "Thorsten mit Gefühl (männlich)",
}


def piper_stimmen():
    """Die eingerichteten Stimmen, mit lesbarem Namen. Beste zuerst.

    „high" vor „medium" vor „low": Die Stufe steckt im Dateinamen und sagt,
    wie fein das Modell rechnet. Wer die Liste aufklappt, soll oben das Beste
    finden und nicht die Reihenfolge des Alphabets.
    """
    if not (PIPER.is_file() and os.access(PIPER, os.X_OK)):
        return []
    stufe = {"high": 0, "medium": 1, "low": 2, "x_low": 3}
    gefunden = []
    for datei in sorted(PIPER_ORT.glob("*.onnx")):
        kennung = datei.stem
        gefunden.append((stufe.get(kennung.rsplit("-", 1)[-1], 9), kennung,
                         PIPER_NAMEN.get(kennung, kennung.replace("de_DE-", ""))))
    gefunden.sort(key=lambda e: (e[0], e[2]))
    return [{"kennung": k, "name": n} for _, k, n in gefunden]


def piper_stimme(kennung=""):
    """Die Stimmdatei zur Kennung — oder die erste beste."""
    if kennung:
        pfad = PIPER_ORT / (kennung + ".onnx")
        if pfad.is_file():
            return str(pfad)
    stimmen = piper_stimmen()
    return str(PIPER_ORT / (stimmen[0]["kennung"] + ".onnx")) if stimmen else None


def piper_da():
    """Ist eine gute Stimme eingerichtet — und lässt sie sich abspielen?"""
    return bool(piper_stimme()
                and (shutil.which("paplay") or shutil.which("aplay")))


def piper_abtastrate(stimme):
    """Die Abtastrate steht neben dem Modell (…onnx.json). Die kleinen Stimmen
    rechnen mit 16000, die größeren mit 22050 — mit der falschen Rate klänge
    jede zu schnell oder zu tief."""
    try:
        with open(stimme + ".json", "r", encoding="utf-8") as datei:
            rate = int(json.load(datei)["audio"]["sample_rate"])
        if 8000 <= rate <= 48000:
            return rate
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return 22050


def piper_laenge(tempo):
    """Das Tempo (−100 bis 100) in Pipers Maß übersetzen.

    Piper rechnet umgekehrt: „length_scale" ist die Länge eines Lautes, größer
    heißt langsamer. 0 bleibt 1,0; −100 wird zu 1,5 und +100 zu 0,6.
    """
    t = max(-100, min(100, int(tempo or 0)))
    return 1.0 - t * (0.4 / 100) if t > 0 else 1.0 - t * (0.5 / 100)


def vorlesen_mit_piper(text, kennung="", tempo=0):
    """Piper schreibt rohen Ton, das Abspielprogramm nimmt ihn direkt entgegen.

    Über eine Zwischendatei zu gehen hieße: erst den ganzen Brief rechnen, dann
    anfangen. So beginnt der Ton nach dem ersten Satz.
    """
    stimme = piper_stimme(kennung)
    if not stimme:
        return False
    rate = str(piper_abtastrate(stimme))
    if shutil.which("paplay"):
        abspielen = ["paplay", "--raw", "--rate=" + rate,
                     "--format=s16le", "--channels=1"]
    else:
        abspielen = ["aplay", "-q", "-r", rate, "-f", "S16_LE", "-c", "1",
                     "-t", "raw", "-"]

    sprechen = subprocess.Popen(
        [PIPER, "--model", stimme, "--output_raw",
         "--length_scale", "%.2f" % piper_laenge(tempo)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, start_new_session=True)
    ton = subprocess.Popen(abspielen, stdin=sprechen.stdout,
                           stderr=subprocess.DEVNULL, start_new_session=True)
    # Sonst bekäme piper kein SIGPIPE, wenn das Abspielen abbricht.
    sprechen.stdout.close()

    def fuettern():
        try:
            sprechen.stdin.write(text.encode("utf-8"))
            sprechen.stdin.close()
        except (OSError, ValueError):
            pass

    threading.Thread(target=fuettern, daemon=True).start()
    VORLESER["lauf"] = ton
    VORLESER["rechner"] = sprechen
    return True


def vorlesen(text, kennung="", tempo=0):
    """Liest den Text laut vor, über den Sprachdienst des Arbeitsplatzes.

    Im Browser gibt es dafür speechSynthesis. WebKitGTK bringt das nicht mit —
    in diesem Fenster gäbe es die Sprachausgabe also gar nicht, ausgerechnet
    dort, wo ein längerer Brief geschrieben wird. Über einen Fehler liest das
    Auge hinweg; das Ohr stolpert darüber. Deshalb hier derselbe Weg wie im
    Schreibprogramm: spd-say.
    """
    vorlesen_beenden()

    if not piper_da() and not shutil.which("spd-say"):
        return False

    # Nicht endlos: Der Dienst nimmt ohnehin nur begrenzt viel auf einmal.
    text = text.strip()[:20000]
    if not text:
        return False

    if piper_da():
        return vorlesen_mit_piper(text, kennung, tempo)

    befehl = ["spd-say", "-l", "de", "-w",
              "-r", str(max(-100, min(100, int(tempo or 0))))]
    if kennung:
        befehl += ["-y", kennung]
    befehl.append(text)
    VORLESER["lauf"] = subprocess.Popen(befehl, start_new_session=True)
    return True


def vorlesen_beenden():
    """Hält das Vorlesen an — auch das, was noch in der Warteschlange steht."""
    # Bei Piper sind es zwei Prozesse: einer rechnet, einer spielt ab. Nur den
    # zweiten anzuhalten hieße, dass der erste weiterrechnet.
    for schluessel in ("lauf", "rechner"):
        vorgang = VORLESER.get(schluessel)
        VORLESER[schluessel] = None
        if vorgang and vorgang.poll() is None:
            try:
                vorgang.terminate()
                # Abholen, sonst bleibt ein Zombie stehen, bis zufällig das
                # nächste Vorlesen ihn einsammelt.
                vorgang.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                pass
    if shutil.which("spd-say"):
        try:
            subprocess.run(["spd-say", "-C"], timeout=5)     # Warteschlange leeren
        except (OSError, subprocess.SubprocessError):
            pass


def kann_vorlesen():
    """Kann auf diesem Rechner überhaupt jemand sprechen? Sonst bleibt der Knopf
    weg — ein toter Knopf ist schlimmer als keiner."""
    return piper_da() or bool(shutil.which("spd-say"))


def spricht():
    """Läuft gerade noch ein Vorlesen?"""
    lauf = VORLESER.get("lauf")
    return bool(lauf and lauf.poll() is None)
