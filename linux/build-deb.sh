#!/usr/bin/env bash
#
# build-deb.sh — baut das Debian-Paket stevie-schreibhilfe aus diesem Ordner.
#
# Baut NUR. Installiert nichts, braucht kein sudo, ändert nichts am System.
# Gebaut wird in einer Wegwerf-Kopie, damit linux/benutzer/ (Schlüssel, Text)
# und Build-Reste nie ins Paket oder in den Arbeitsbaum geraten.
#
# Aufruf:  ./linux/build-deb.sh            Paket nach linux/dist/
#          ./linux/build-deb.sh --pruefen   danach lintian und Dateiliste
#
# Braucht: dpkg-dev, debhelper, python3 (für die Tests beim Bauen)
#          und für --pruefen: lintian
#   sudo apt install dpkg-dev debhelper lintian

set -Eeuo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # …/linux
AUSGABE="$HIER/dist"

fehlt=()
for werkzeug in dpkg-buildpackage dh python3; do
  command -v "$werkzeug" >/dev/null 2>&1 || fehlt+=("$werkzeug")
done
if [ "${#fehlt[@]}" -gt 0 ]; then
  echo "Es fehlt: ${fehlt[*]}" >&2
  echo "Bitte installieren:  sudo apt install dpkg-dev debhelper python3" >&2
  exit 1
fi

VERSION="$(cd "$HIER" && dpkg-parsechangelog -S Version)"
ARBEIT="$(mktemp -d "${TMPDIR:-/tmp}/stevie-schreibhilfe-bau.XXXXXX")"
trap 'rm -rf -- "$ARBEIT"' EXIT

QUELLE="$ARBEIT/stevie-schreibhilfe-$VERSION"
mkdir -p "$QUELLE"
# Alles außer persönlichen Daten, Build-Ausgaben und Zwischenspeichern.
tar -C "$HIER" \
    --exclude=./benutzer --exclude=./dist --exclude='__pycache__' --exclude='*.pyc' \
    -cf - . | tar -C "$QUELLE" -xf -

echo "Baue stevie-schreibhilfe $VERSION …"
(cd "$QUELLE" && dpkg-buildpackage -b -us -uc --no-sign)

mkdir -p "$AUSGABE"
PAKET="stevie-schreibhilfe_${VERSION}_all.deb"
mv -f "$ARBEIT/$PAKET" "$AUSGABE/"
echo
echo "Fertig: $AUSGABE/$PAKET"
echo "Installieren:  sudo apt install $AUSGABE/$PAKET"

if [ "${1:-}" = "--pruefen" ]; then
  echo
  dpkg-deb --info "$AUSGABE/$PAKET"
  dpkg-deb --contents "$AUSGABE/$PAKET"
  if command -v lintian >/dev/null 2>&1; then
    lintian --info "$AUSGABE/$PAKET"
  else
    echo "lintian fehlt — Prüfung übersprungen (sudo apt install lintian)." >&2
  fi
fi
