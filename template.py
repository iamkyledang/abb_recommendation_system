"""
template.py — ABB AI-Powered Electrical Energy Simulator
=========================================================
Pre-built industrial factory circuit template.

Run directly:
    python template.py        (from saving_system/ folder)

The window opens with a complete electrical system already on the canvas.
Just press  ▶ Run Simulation  to instantly get energy analysis and
AI-powered recommendations.

Circuit topology
────────────────

  [Grid Supply]
       │
  [Dry Transformer 630 kVA]
       │
  [Air Circuit Breaker 1250 A]
       ├── [Motor IE2  7.5 kW]  ← DOL, no drive  → recommendation triggered
       │
       ├── [VFD ACS580 11 kW] ── [Motor IE3  7.5 kW] ── [Pump 11 kW]
       │
       ├── [VFD ACS880 18.5 kW] ── [SynRM IE5  11 kW]
       │
       ├── [Soft Starter PSE  11 kW] ── [Motor IE4  7.5 kW]
       │
       ├── [Compressor  15 kW]
       │
       ├── [HVAC Unit   20 kW]
       │
       ├── [LED Lighting  5 kW]
       │
       ├── [Conveyor      5.5 kW]
       │
       ├── [Contactor AF40]
       │
       └── [Energy Meter B24]

Typical recommendations generated:
  • Add VFD to IE2 motor (DOL, variable-torque load)
  • Upgrade IE2 → IE4/IE5 SynRM
  • Review power factor
  • Peak demand management
"""

import sys
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QPointF
from PyQt5.QtGui import QFont

from main_window import MainWindow
from canvas import WireItem
from devices import DEVICE_CATALOG


# ════════════════════════════════════════════════════════════════════════════
# Template builder
# ════════════════════════════════════════════════════════════════════════════
def build_template(window: MainWindow) -> None:
    """Populate the canvas with the factory template circuit."""

    C = DEVICE_CATALOG
    s = window.scene

    # ── Row layout (x, y) — horizontal bus at y=280 ────────────────────────
    #   Source → Trafo → ACB  then branches drop down or continue right
    grid  = s.add_device(C["Grid Supply"],          QPointF(60,  280))
    trafo = s.add_device(C["Dry Transformer"],       QPointF(250, 280))
    acb   = s.add_device(C["Air Circuit Breaker"],   QPointF(450, 280))

    # Branch 1 — Motor IE2, direct-on-line (no VFD)
    m_ie2 = s.add_device(C["Motor IE2"],             QPointF(660,  80))

    # Branch 2 — VFD ACS580 → Motor IE3 → Pump
    vfd_a = s.add_device(C["VFD ACS580"],            QPointF(660, 200))
    m_ie3 = s.add_device(C["Motor IE3"],             QPointF(860, 200))
    pump  = s.add_device(C["Pump"],                  QPointF(1060, 200))

    # Branch 3 — VFD ACS880 → SynRM IE5
    vfd_b = s.add_device(C["VFD ACS880"],            QPointF(660, 310))
    synrm = s.add_device(C["SynRM IE5"],             QPointF(860, 310))

    # Branch 4 — Soft Starter → Motor IE4
    ss    = s.add_device(C["Soft Starter PSE"],      QPointF(660, 420))
    m_ie4 = s.add_device(C["Motor IE4"],             QPointF(860, 420))

    # Branch 5 — Compressor
    comp  = s.add_device(C["Compressor"],            QPointF(660, 530))

    # Branch 6 — HVAC
    hvac  = s.add_device(C["HVAC Unit"],             QPointF(860, 530))

    # Branch 7 — LED Lighting
    led   = s.add_device(C["LED Lighting"],          QPointF(660, 640))

    # Branch 8 — Conveyor
    conv  = s.add_device(C["Conveyor"],              QPointF(860, 640))

    # Branch 9 — Contactor + Energy Meter
    cont  = s.add_device(C["Contactor"],             QPointF(660, 750))
    meter = s.add_device(C["Energy Meter"],          QPointF(860, 750))

    # ── Operating parameters ───────────────────────────────────────────────
    # Heavier loads — run most of the day
    m_ie2.operating_hours  = 20;  m_ie2.load_factor  = 0.90   # DOL, always loaded
    vfd_a.operating_hours  = 18;  vfd_a.load_factor  = 0.75
    m_ie3.operating_hours  = 18;  m_ie3.load_factor  = 0.75
    pump.operating_hours   = 18;  pump.load_factor   = 0.75

    vfd_b.operating_hours  = 16;  vfd_b.load_factor  = 0.80
    synrm.operating_hours  = 16;  synrm.load_factor  = 0.80

    ss.operating_hours     = 12;  ss.load_factor     = 0.85
    m_ie4.operating_hours  = 12;  m_ie4.load_factor  = 0.85

    comp.operating_hours   = 14;  comp.load_factor   = 0.80
    hvac.operating_hours   = 10;  hvac.load_factor   = 0.70
    led.operating_hours    = 12;  led.load_factor    = 1.00
    conv.operating_hours   = 10;  conv.load_factor   = 0.65
    cont.operating_hours   = 18
    meter.operating_hours  = 24   # always on

    # ── Wire helper ─────────────────────────────────────────────────────────
    def wire(src, dst):
        w = WireItem(src.output_port, dst.input_port)
        s.addItem(w)
        s.wires.append(w)

    # Main bus
    wire(grid,  trafo)
    wire(trafo, acb)

    # Branch 1
    wire(acb,  m_ie2)

    # Branch 2
    wire(acb,  vfd_a)
    wire(vfd_a, m_ie3)
    wire(m_ie3, pump)

    # Branch 3
    wire(acb,  vfd_b)
    wire(vfd_b, synrm)

    # Branch 4
    wire(acb,  ss)
    wire(ss,   m_ie4)

    # Branch 5
    wire(acb,  comp)

    # Branch 6
    wire(acb,  hvac)

    # Branch 7
    wire(acb,  led)

    # Branch 8
    wire(acb,  conv)

    # Branch 9
    wire(acb,  cont)
    wire(cont, meter)


# ════════════════════════════════════════════════════════════════════════════
# Entry-point
# ════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ABB Energy Simulator — Factory Template")
    app.setOrganizationName("ABB")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))

    window = MainWindow()

    # Override window title to reflect template mode
    window.setWindowTitle(
        "ABB  |  AI-Powered Electrical Energy Simulator  ·  Factory Template"
    )

    # Populate the canvas before the window is shown
    build_template(window)

    window.show()

    # Fit the canvas to the loaded circuit after the event loop starts
    QTimer.singleShot(120, window._fit_view)

    # Update the status bar with a clear call-to-action
    window.statusBar().showMessage(
        "✅  Factory template loaded — 13 devices, pre-configured.  "
        "Press  ▶ Run Simulation  to see the 24-hour energy analysis and AI recommendations."
    )

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
