#!/usr/bin/env python3
"""Check PyThesisPlot runtime dependencies."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
VENDOR_SITE = SKILL_DIR / "vendor" / "site-packages"
if VENDOR_SITE.exists():
    sys.path.insert(0, str(VENDOR_SITE))

REQUIRED_MODULES = {
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "openpyxl": "openpyxl",
}


def main() -> int:
    results = []
    missing = []
    for package, module in REQUIRED_MODULES.items():
        try:
            imported = importlib.import_module(module)
            version = getattr(imported, "__version__", "unknown")
            results.append({"package": package, "module": module, "status": "ok", "version": version})
        except Exception as exc:
            missing.append(package)
            results.append({
                "package": package,
                "module": module,
                "status": "missing",
                "error": str(exc),
            })

    payload = {
        "status": "ok" if not missing else "missing_dependencies",
        "skill_dir": str(SKILL_DIR),
        "vendor_site": str(VENDOR_SITE),
        "vendor_site_exists": VENDOR_SITE.exists(),
        "results": results,
        "missing": missing,
        "install_hint": "python scripts/install_dependencies.py" if missing else None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
