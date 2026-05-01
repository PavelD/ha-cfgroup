"""Pytest-Setup für die Integration.

Die Datei `custom_components/cfgroup_heatpump/__init__.py` importiert von
Home Assistant. Da HA in dieser Test-Umgebung nicht installiert ist, laden
wir nur die Module, die wir wirklich testen wollen (`api`, `const`),
und mounten sie unter dem schlanken Paket-Alias `cfgroup_heatpump`.
Damit funktionieren die relativen Imports in `api.py`, ohne dass HA
geladen werden muss.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "custom_components" / "cfgroup_heatpump"

# Synthetisches Paket aufbauen, das auf das echte Verzeichnis zeigt, aber
# das HA-abhängige __init__.py nicht ausführt.
_package = types.ModuleType("cfgroup_heatpump")
_package.__path__ = [str(PACKAGE_DIR)]
sys.modules.setdefault("cfgroup_heatpump", _package)

# `const` zuerst, weil `api.py` es per relativem Import braucht.
for _module_name in ("const", "api"):
    _spec = importlib.util.spec_from_file_location(
        f"cfgroup_heatpump.{_module_name}",
        PACKAGE_DIR / f"{_module_name}.py",
    )
    assert _spec is not None and _spec.loader is not None
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[f"cfgroup_heatpump.{_module_name}"] = _module
    _spec.loader.exec_module(_module)
