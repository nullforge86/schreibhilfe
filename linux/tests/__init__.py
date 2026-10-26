# -*- coding: utf-8 -*-
# Tests dürfen NIE an die echten Nutzerdaten (Schlüssel, Text, Gedächtnis):
# Dieses Paket wird als Erstes geladen und lenkt den Benutzerordner in einen
# Wegwerf-Ordner um, bevor services/pfade.py seine Pfade festlegt.
import atexit
import os
import shutil
import tempfile

_WEG = tempfile.mkdtemp(prefix="schreibhilfe-test-")
os.environ["SCHREIBHILFE_BENUTZER"] = os.path.join(_WEG, "benutzer")
atexit.register(shutil.rmtree, _WEG, True)
