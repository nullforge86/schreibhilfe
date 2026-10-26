#!/usr/bin/env bash
#
# run-app.sh — startet die native Schreibhilfe aus dem Arbeitsbaum (GTK 3,
# kein Browser, kein Server).
#
# Der Menüeintrag wird bei JEDEM Start über install.sh frisch geschrieben:
# Eine .desktop-Datei braucht feste Pfade, und verschiebt man den Ordner,
# zeigt der Eintrag sonst ins Leere. Einmal von hier starten genügt.
#
# Aufruf:  ./linux/run-app.sh                 startet die App
#          ./linux/run-app.sh --nur-eintrag   legt nur den Menüeintrag an
#          ./linux/run-app.sh --weg           nimmt Eintrag und Symbol zurück
#
# Für die Installation als Debian-Paket siehe build-deb.sh — das Paket
# braucht dieses Skript nicht.

set -Eeuo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # …/linux

case "${1:-}" in
  --weg|--nur-eintrag)
    exec "$HIER/install.sh" "$1" ;;
esac

"$HIER/install.sh" --nur-eintrag >/dev/null || \
  echo "Hinweis: Der Menüeintrag ließ sich nicht erneuern — die App startet trotzdem." >&2

# main.py prüft GTK selbst und nennt das fehlende Paket.
exec python3 "$HIER/main.py" "$@"
