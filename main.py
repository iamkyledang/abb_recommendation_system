"""
ABB AI-Powered Electrical Energy Simulator
==========================================
Entry-point.  Run with:

    python main.py            (from saving_system/ folder)
    python saving_system/main.py  (from project root)

Requirements: PyQt5, matplotlib, numpy (all auto-installed if missing).
"""

import sys
import os

# Make sure imports from the same directory work regardless of cwd
_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# ── Auto-install missing packages before importing Qt ──────────────────────
def _ensure(pkg: str, import_name: str = None):
    import importlib
    try:
        importlib.import_module(import_name or pkg)
    except ImportError:
        import subprocess
        print(f"Installing {pkg} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("PyQt5")
_ensure("matplotlib")
_ensure("numpy")

# ── Launch ─────────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ABB Energy Simulator")
    app.setOrganizationName("ABB")
    app.setStyle("Fusion")

    # Default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
