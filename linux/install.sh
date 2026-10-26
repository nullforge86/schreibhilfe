#!/usr/bin/env bash
#
# install.sh — richtet die native Schreibhilfe für Linux Mint (Cinnamon) ein.
#
# Was passiert:   · prüft Python, GTK 3 und die Wörterliste (mit klarer Meldung,
#                   welches Paket fehlt)
#                 · legt den Menüeintrag und das Symbol im eigenen Benutzerordner an
# Was NICHT:      · kein sudo, nichts im System, keine Cinnamon-Einstellung,
#                   kein Dienst, kein Webserver
#
# Aufruf:  ./linux/install.sh                 einrichten
#          ./linux/install.sh --nur-eintrag   nur den Menüeintrag erneuern
#          ./linux/install.sh --weg           Eintrag und Symbol entfernen
#                                             (Texte und Einstellungen bleiben)

set -uo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATEN="${XDG_DATA_HOME:-$HOME/.local/share}"
EINTRAG="$DATEN/applications/schreibhilfe.desktop"
SYMBOL_PNG="$DATEN/icons/hicolor/512x512/apps/schreibhilfe.png"
SYMBOL_SVG="$DATEN/icons/hicolor/scalable/apps/schreibhilfe.svg"

aktualisieren() {
  update-desktop-database "$DATEN/applications" 2>/dev/null || true
  gtk-update-icon-cache -f -t "$DATEN/icons/hicolor" 2>/dev/null || true
}

if [ "${1:-}" = "--weg" ]; then
  rm -f "$EINTRAG" "$SYMBOL_PNG" "$SYMBOL_SVG"
  aktualisieren
  echo "Menüeintrag und Symbol entfernt. Texte und Einstellungen bleiben erhalten."
  exit 0
fi

eintrag_schreiben() {
  mkdir -p "$(dirname "$EINTRAG")" "$(dirname "$SYMBOL_PNG")" "$(dirname "$SYMBOL_SVG")" || return 1
  cp -f "$HIER/resources/schreibhilfe.png" "$SYMBOL_PNG" || return 1
  cp -f "$HIER/resources/schreibhilfe.svg" "$SYMBOL_SVG" || return 1
  sed "s|@HIER@|$HIER|g" "$HIER/schreibhilfe.desktop" > "$EINTRAG.neu" || return 1
  mv -f "$EINTRAG.neu" "$EINTRAG" || return 1
  chmod +x "$EINTRAG" "$HIER/run-app.sh" "$HIER/main.py" "$HIER/install.sh"
  aktualisieren
}

if [ "${1:-}" = "--nur-eintrag" ]; then
  eintrag_schreiben || { echo "Der Menüeintrag ließ sich nicht anlegen." >&2; exit 1; }
  echo "Menüeintrag „Schreibhilfe“ zeigt jetzt auf: $HIER"
  exit 0
fi

fehlt=()
echo "Prüfe die Voraussetzungen …"

if command -v python3 >/dev/null 2>&1; then
  echo "  ✔ Python $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
else
  echo "  ✘ Python 3 fehlt"; fehlt+=(python3)
fi

if python3 -c "import gi" 2>/dev/null; then
  if python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null; then
    echo "  ✔ GTK 3 für Python"
  else
    echo "  ✘ GTK 3 (gir1.2-gtk-3.0) fehlt"; fehlt+=(gir1.2-gtk-3.0)
  fi
else
  echo "  ✘ PyGObject (python3-gi) fehlt"; fehlt+=(python3-gi gir1.2-gtk-3.0)
fi

if python3 -c "import gi; gi.require_version('GtkSource','3.0'); from gi.repository import GtkSource" 2>/dev/null; then
  echo "  ✔ GtkSourceView (Rückgängig mit Strg+Z im Textfeld)"
else
  echo "  ○ GtkSourceView fehlt — es geht auch ohne, nur ohne Strg+Z im Textfeld"
  echo "    (sudo apt install gir1.2-gtksource-3.0)"
fi

if [ -s "$HIER/daten/woerter.txt" ] && [ -s "$HIER/daten/regeln.js" ]; then
  echo "  ✔ Wörterliste und Regeln (linux/daten/)"
else
  echo "  ✘ linux/daten/woerter.txt oder regeln.js fehlt — Ordner linux unvollständig"
  fehlt+=(PROJEKTORDNER)
fi

for opt in spd-say paplay; do
  command -v "$opt" >/dev/null 2>&1 && echo "  ✔ $opt (Vorlesen)" \
    || echo "  ○ $opt fehlt — Vorlesen steht dann nur mit Piper zur Verfügung (./stimme-holen.sh)"
done

if [ "${#fehlt[@]}" -gt 0 ]; then
  echo
  pakete=()
  for f in "${fehlt[@]}"; do [ "$f" != "PROJEKTORDNER" ] && pakete+=("$f"); done
  echo "Es fehlt etwas. Es wurde nichts eingerichtet." >&2
  [ "${#pakete[@]}" -gt 0 ] && echo "Bitte installieren und danach noch einmal starten:
    sudo apt install ${pakete[*]}" >&2
  [[ " ${fehlt[*]} " == *" PROJEKTORDNER "* ]] && echo "Den Ordner linux vollständig von GitHub holen." >&2
  exit 1
fi

eintrag_schreiben || { echo "Der Menüeintrag ließ sich nicht anlegen." >&2; exit 1; }
echo
echo "Fertig. „Schreibhilfe“ steht jetzt im Anwendungsmenü (Büro)."
echo "Starten ohne Menü:  $HIER/run-app.sh"
