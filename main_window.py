"""
Main Window — ABB AI-Powered Electrical Energy Simulator

Layout
──────
Toolbar (ABB red)
├── [Left 180px]   Device Palette — ABB catalog grouped by category
├── [Center]       Canvas — drag-drop, connect, inspect
│   └── [Right 260px]  Properties Panel — selected device settings
└── [Bottom 290px] Results Tabs — Summary | Chart | AI Recommendations
"""

import sys
import os

# Ensure the saving_system folder is on the path when running from IDE
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QGroupBox,
    QFormLayout, QDoubleSpinBox, QSpinBox, QTextEdit, QTabWidget,
    QScrollArea, QFrame, QToolBar, QStatusBar, QSizePolicy,
    QAction, QGraphicsView,
)
from PyQt5.QtCore import Qt, QSize, QMimeData, QPointF, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon, QDrag

from devices import ABB_DEVICES, DEVICE_CATALOG, DeviceSpec, DeviceCategory
from canvas import CanvasView, CanvasScene, WireItem
from simulation import SimulationEngine, SimulationResult
from recommendations import RecommendationEngine, Recommendation

# ── ABB brand palette ───────────────────────────────────────────────────────
ABB_RED    = "#CC0000"
ABB_DARK   = "#1A1A1A"
ABB_LIGHT  = "#F4F6F9"
ABB_PANEL  = "#23272E"


# ════════════════════════════════════════════════════════════════════════════
# Device Palette (left panel)
# ════════════════════════════════════════════════════════════════════════════
class DevicePaletteWidget(QListWidget):
    """Draggable list of ABB devices grouped by category."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setMaximumWidth(195)
        self.setMinimumWidth(160)
        self.setSpacing(1)
        self._populate()
        self.setStyleSheet(f"""
            QListWidget {{
                background: {ABB_PANEL};
                border: none;
                color: #ECEFF1;
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid #2E3440;
            }}
            QListWidget::item:hover   {{ background: #2E3440; }}
            QListWidget::item:selected {{ background: {ABB_RED}; color: white; }}
        """)

    def _populate(self):
        categories: dict[str, list] = {}
        for d in ABB_DEVICES:
            categories.setdefault(d.category.value, []).append(d)

        for cat_name, devices in categories.items():
            hdr = QListWidgetItem(f"  {cat_name.upper()}")
            hdr.setFlags(Qt.NoItemFlags)
            hdr.setFont(QFont("Segoe UI", 8, QFont.Bold))
            hdr.setForeground(QColor("#90A4AE"))
            hdr.setBackground(QColor("#1A1F27"))
            self.addItem(hdr)

            for d in devices:
                item = QListWidgetItem(f"    {d.name}")
                item.setData(Qt.UserRole, d.name)
                item.setForeground(QColor(d.icon_color).lighter(200))
                item.setToolTip(
                    f"{d.model}\n{d.description}\n"
                    f"Rated: {d.rated_power_kw} kW   η={d.efficiency*100:.1f}%   "
                    f"PF={d.power_factor}"
                )
                self.addItem(item)

    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item and item.data(Qt.UserRole):
            mime = QMimeData()
            mime.setText(item.data(Qt.UserRole))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec_(Qt.CopyAction)


# ════════════════════════════════════════════════════════════════════════════
# Properties Panel (right panel)
# ════════════════════════════════════════════════════════════════════════════
class PropertiesPanel(QWidget):
    """Shows and edits the selected device's operating parameters."""

    property_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_device = None
        self.setMaximumWidth(275)
        self.setMinimumWidth(210)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        hdr = QLabel("  Device Properties")
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            f"background:{ABB_RED}; color:white; font-weight:bold; font-size:12px;"
        )
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:#FAFAFA;")

        self._body = QWidget()
        self._form = QFormLayout(self._body)
        self._form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._form.setContentsMargins(10, 10, 10, 10)
        self._form.setSpacing(7)
        scroll.setWidget(self._body)
        root.addWidget(scroll)

        self._show_placeholder()

    def _clear(self):
        while self._form.rowCount():
            self._form.removeRow(0)

    def _show_placeholder(self):
        self._clear()
        lbl = QLabel("Click a device on the\ncanvas to see its details.")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#90A4AE; font-size:11px; padding:20px;")
        self._form.addRow(lbl)

    def show_device(self, device_item):
        self.current_device = device_item
        self._clear()
        if device_item is None:
            self._show_placeholder()
            return

        spec: DeviceSpec = device_item.device_spec

        # ── Title ────────────────────────────────────────────────────────────
        name_lbl = QLabel(spec.name)
        name_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
        name_lbl.setStyleSheet(f"color:{spec.icon_color}; padding:2px 0;")
        self._form.addRow(name_lbl)

        model_lbl = QLabel(spec.model)
        model_lbl.setStyleSheet("color:#546E7A; font-size:9px; font-style:italic;")
        model_lbl.setWordWrap(True)
        self._form.addRow(model_lbl)

        desc_lbl = QLabel(spec.description)
        desc_lbl.setStyleSheet("color:#607D8B; font-size:9px;")
        desc_lbl.setWordWrap(True)
        self._form.addRow(desc_lbl)

        self._form.addRow(self._separator())
        self._form.addRow(self._section("Nameplate Data"))
        self._form.addRow("Rated Power:", QLabel(f"{spec.rated_power_kw} kW"))
        self._form.addRow("Efficiency:",  QLabel(f"{spec.efficiency*100:.1f} %"))
        self._form.addRow("Power Factor:", QLabel(f"{spec.power_factor:.2f}"))
        self._form.addRow("Voltage:",     QLabel(f"{spec.voltage_v} V"))
        self._form.addRow("Category:",    QLabel(spec.category.value))

        # ── Extra spec params ────────────────────────────────────────────────
        if spec.parameters:
            self._form.addRow(self._separator())
            self._form.addRow(self._section("Specifications"))
            for k, v in spec.parameters.items():
                if isinstance(v, (int, float, str, bool)):
                    lbl = k.replace("_", " ").title()
                    self._form.addRow(f"{lbl}:", QLabel(str(v)))

        # ── Editable operating settings ──────────────────────────────────────
        self._form.addRow(self._separator())
        self._form.addRow(self._section("Operating Settings"))

        self._lf_spin = QDoubleSpinBox()
        self._lf_spin.setRange(0.1, 1.0)
        self._lf_spin.setSingleStep(0.05)
        self._lf_spin.setDecimals(2)
        self._lf_spin.setValue(device_item.load_factor)
        self._lf_spin.setSuffix("  (0–1)")
        self._lf_spin.setToolTip(
            "Fraction of rated load the device runs at.\n"
            "1.0 = fully loaded, 0.5 = 50% loaded."
        )
        self._lf_spin.valueChanged.connect(self._on_lf)
        self._form.addRow("Load Factor:", self._lf_spin)

        self._oh_spin = QSpinBox()
        self._oh_spin.setRange(1, 24)
        self._oh_spin.setValue(device_item.operating_hours)
        self._oh_spin.setSuffix(" h/day")
        self._oh_spin.setToolTip("Hours per day this device is in operation.")
        self._oh_spin.valueChanged.connect(self._on_oh)
        self._form.addRow("Oper. Hours:", self._oh_spin)

    def _on_lf(self, v):
        if self.current_device:
            self.current_device.load_factor = v
            self.property_changed.emit()

    def _on_oh(self, v):
        if self.current_device:
            self.current_device.operating_hours = v
            self.property_changed.emit()

    @staticmethod
    def _separator() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setStyleSheet("color:#CFD8DC; margin:4px 0;")
        return f

    @staticmethod
    def _section(title: str) -> QLabel:
        lbl = QLabel(title)
        lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl.setStyleSheet("color:#37474F;")
        return lbl


# ════════════════════════════════════════════════════════════════════════════
# Embedded Matplotlib chart
# ════════════════════════════════════════════════════════════════════════════
class EnergyChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 3.6), dpi=90, facecolor=ABB_LIGHT)
        super().__init__(self.fig)
        self.setParent(parent)

    def plot(self, result: SimulationResult, device_list: list):
        self.fig.clear()

        if not result.time_hours:
            self.draw()
            return

        ax1 = self.fig.add_subplot(1, 2, 1)
        ax2 = self.fig.add_subplot(1, 2, 2)

        # ── Left: 24-hour total power profile ───────────────────────────────
        t = result.time_hours
        p = result.total_power_kw
        ax1.fill_between(t, p, alpha=0.25, color=ABB_RED)
        ax1.plot(t, p, color=ABB_RED, linewidth=2)
        ax1.set_title("Total Power Profile (24 h)", fontsize=10, fontweight="bold",
                      color="#263238")
        ax1.set_xlabel("Hour of Day")
        ax1.set_ylabel("Power (kW)")
        ax1.set_xlim(0, 24)
        ax1.set_xticks(range(0, 25, 4))
        ax1.grid(True, alpha=0.25)
        ax1.set_facecolor("#FAFBFD")

        if p:
            peak_t = t[p.index(max(p))]
            ax1.annotate(
                f"Peak\n{result.peak_power_kw:.1f} kW",
                xy=(peak_t, result.peak_power_kw),
                xytext=(peak_t + 1.5, result.peak_power_kw * 0.88),
                fontsize=7.5, color=ABB_RED,
                arrowprops=dict(arrowstyle="->", color=ABB_RED, lw=1.5),
            )

        # ── Right: energy by device ──────────────────────────────────────────
        names, energies = [], []
        palette = [
            "#CC0000","#1565C0","#2E7D32","#E65100","#4527A0",
            "#00695C","#6D4C41","#AD1457","#0277BD","#F9A825",
        ]
        for did, spec, item in device_list:
            e = result.device_energy_kwh.get(did, 0.0)
            if e > 0.05:
                n = spec.name if len(spec.name) <= 13 else spec.name[:12] + "…"
                names.append(n)
                energies.append(round(e, 2))

        if names:
            colors = [palette[i % len(palette)] for i in range(len(names))]
            bars = ax2.bar(names, energies, color=colors, alpha=0.88, zorder=3)
            ax2.set_title("Energy per Device (kWh/day)", fontsize=10, fontweight="bold",
                          color="#263238")
            ax2.set_ylabel("Energy (kWh)")
            ax2.tick_params(axis="x", rotation=40, labelsize=7.5)
            ax2.grid(True, alpha=0.25, axis="y", zorder=0)
            ax2.set_facecolor("#FAFBFD")
            for bar, val in zip(bars, energies):
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + max(energies) * 0.01,
                         f"{val:.1f}", ha="center", va="bottom",
                         fontsize=7, color="#263238")

        self.fig.tight_layout(pad=1.8)
        self.draw()


# ════════════════════════════════════════════════════════════════════════════
# Results Panel (bottom tabs)
# ════════════════════════════════════════════════════════════════════════════
class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid #CFD8DC; background: {ABB_LIGHT}; }}
            QTabBar::tab {{
                padding: 6px 20px; font-size: 11px; background: #E8EDF2;
                border: 1px solid #CFD8DC; margin-right: 2px;
            }}
            QTabBar::tab:selected {{ background: {ABB_RED}; color: white; }}
            QTabBar::tab:hover     {{ background: #D0D8E4; }}
        """)

        # ── Tab 1: Summary cards ─────────────────────────────────────────────
        summary_w = QWidget()
        sum_layout = QHBoxLayout(summary_w)
        sum_layout.setContentsMargins(12, 10, 12, 10)
        sum_layout.setSpacing(12)

        self._metric = {}
        for title, unit, color in [
            ("Total Energy",  "kWh/day",  "#CC0000"),
            ("Peak Power",    "kW",       "#E65100"),
            ("Energy Cost",   "USD/day",  "#2E7D32"),
            ("CO₂ Emissions", "kg/day",   "#4527A0"),
        ]:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    border: 2px solid {color};
                    border-radius: 8px;
                    background: white;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setSpacing(2)
            cl.setContentsMargins(14, 10, 14, 10)

            t_lbl = QLabel(title)
            t_lbl.setFont(QFont("Segoe UI", 8))
            t_lbl.setStyleSheet(f"color:{color}; border:none;")
            t_lbl.setAlignment(Qt.AlignCenter)

            v_lbl = QLabel("—")
            v_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
            v_lbl.setStyleSheet(f"color:{color}; border:none;")
            v_lbl.setAlignment(Qt.AlignCenter)
            self._metric[title] = v_lbl

            u_lbl = QLabel(unit)
            u_lbl.setFont(QFont("Segoe UI", 8))
            u_lbl.setStyleSheet("color:#90A4AE; border:none;")
            u_lbl.setAlignment(Qt.AlignCenter)

            cl.addWidget(t_lbl)
            cl.addWidget(v_lbl)
            cl.addWidget(u_lbl)
            sum_layout.addWidget(card)

        tabs.addTab(summary_w, "  📊 Summary  ")

        # ── Tab 2: Chart ────────────────────────────────────────────────────
        self.chart = EnergyChart()
        tabs.addTab(self.chart, "  📈 Energy Chart  ")

        # ── Tab 3: Recommendations ───────────────────────────────────────────
        self.recs_view = QTextEdit()
        self.recs_view.setReadOnly(True)
        self.recs_view.setStyleSheet(
            "QTextEdit { background:#FAFBFD; border:none; font-size:11px; }"
        )
        self.recs_view.setHtml(
            "<p style='color:#90A4AE; padding:20px; text-align:center;'>"
            "Run the simulation to generate AI recommendations.</p>"
        )
        tabs.addTab(self.recs_view, "  🤖 AI Recommendations  ")

        root.addWidget(tabs)

    # ── Public update ─────────────────────────────────────────────────────────
    def update_results(self, result: SimulationResult,
                       recs: list, device_list: list):
        # Cards
        self._metric["Total Energy"].setText(f"{result.total_energy_kwh:.1f}")
        self._metric["Peak Power"].setText(f"{result.peak_power_kw:.1f}")
        self._metric["Energy Cost"].setText(f"${result.energy_cost_usd:.2f}")
        self._metric["CO₂ Emissions"].setText(f"{result.co2_kg:.1f}")

        # Chart
        self.chart.plot(result, device_list)

        # Recommendations HTML
        self._render_recs(recs, result)

    def _render_recs(self, recs: list, result: SimulationResult):
        if not recs:
            self.recs_view.setHtml(
                "<div style='padding:24px; text-align:center;'>"
                "<span style='font-size:20px;'>✅</span><br/>"
                "<b style='color:#2E7D32;'>No major inefficiencies detected.</b><br/>"
                "<span style='color:#607D8B;'>Add more devices to get detailed advice.</span>"
                "</div>"
            )
            return

        total_day_kwh = sum(r.savings_kwh_day for r in recs)
        total_yr_kwh  = total_day_kwh * 365
        total_yr_usd  = total_yr_kwh * 0.12

        COLORS = {"HIGH": "#CC0000", "MEDIUM": "#E65100", "LOW": "#2E7D32"}
        ICONS  = {"HIGH": "🔴",       "MEDIUM": "🟡",       "LOW": "🟢"}

        html = (
            "<div style='font-family:Segoe UI,Arial; padding:8px;'>"
            "<h3 style='color:#1A1A1A; border-bottom:3px solid #CC0000;"
            " padding-bottom:6px; margin-bottom:12px;'>"
            "AI Energy-Saving Recommendations</h3>"
        )

        for r in recs:
            c = COLORS.get(r.priority, "#607D8B")
            i = ICONS.get(r.priority, "•")
            roi_txt = (f" &nbsp;·&nbsp; Payback ≈ {r.roi_years}&nbsp;yr"
                       if r.roi_years else "")
            savings_line = ""
            if r.savings_kwh_day > 0:
                savings_line = (
                    f"<div style='margin-top:6px; font-size:10px; color:#546E7A;'>"
                    f"💡 Potential: <b>{r.savings_kwh_day:.1f}&nbsp;kWh/day</b> "
                    f"({r.savings_pct:.0f}&nbsp;%)&nbsp;·&nbsp;"
                    f"${r.annual_usd:.0f}/yr{roi_txt}</div>"
                )
            html += (
                f"<div style='margin:8px 0; padding:12px 14px;"
                f" border-left:4px solid {c}; background:white;"
                f" border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,.08);'>"
                f"<div style='font-weight:bold; color:{c}; font-size:12px;'>"
                f"{i} [{r.priority}] {r.title}</div>"
                f"<div style='color:#37474F; margin-top:5px; line-height:1.55;'>"
                f"{r.description}</div>"
                f"{savings_line}"
                f"</div>"
            )

        # Summary footer
        html += (
            f"<div style='margin-top:14px; padding:12px 14px;"
            f" background:#E8F5E9; border-radius:8px;'>"
            f"<b style='color:#1B5E20;'>📊 Total Potential Savings</b><br/>"
            f"<span style='color:#2E7D32; font-size:15px; font-weight:bold;'>"
            f"{total_day_kwh:.1f}&nbsp;kWh/day &nbsp;·&nbsp; ${total_yr_usd:.0f}/yr</span><br/>"
            f"<span style='color:#546E7A; font-size:10px;'>"
            f"Annual: {total_yr_kwh:.0f}&nbsp;kWh &nbsp;·&nbsp; "
            f"{total_yr_kwh * 0.40:.0f}&nbsp;kg CO₂ avoided</span>"
            f"</div>"
            "</div>"
        )
        self.recs_view.setHtml(html)


# ════════════════════════════════════════════════════════════════════════════
# Main Window
# ════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ABB  |  AI-Powered Electrical Energy Simulator")
        self.setMinimumSize(1200, 760)
        self.resize(1480, 920)

        self._sim_engine = SimulationEngine()
        self._rec_engine = RecommendationEngine()

        self._build_ui()
        self._build_toolbar()
        self._apply_styles()
        self.statusBar().setStyleSheet(
            "background:#2C3E50; color:#B0BEC5; font-size:10px; padding:2px 6px;"
        )
        self.statusBar().showMessage(
            "Ready  —  Drag ABB devices from the left panel onto the canvas.  "
            "Use the Connect button to wire them together."
        )

    # ── UI construction ────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Outer vertical splitter: top (canvas area) | bottom (results)
        v_split = QSplitter(Qt.Vertical)

        # Top horizontal splitter: palette | canvas | properties
        h_split = QSplitter(Qt.Horizontal)

        # Left: palette
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        cat_hdr = QLabel("  ABB Device Catalog")
        cat_hdr.setFixedHeight(34)
        cat_hdr.setStyleSheet(
            f"background:{ABB_RED}; color:white; font-weight:bold; font-size:12px;"
        )
        lv.addWidget(cat_hdr)
        self.palette = DevicePaletteWidget()
        lv.addWidget(self.palette)
        drag_hint = QLabel("↑ Drag devices to canvas")
        drag_hint.setAlignment(Qt.AlignCenter)
        drag_hint.setStyleSheet(
            f"background:{ABB_PANEL}; color:#78909C; font-size:9px; padding:4px;"
        )
        lv.addWidget(drag_hint)
        h_split.addWidget(left_w)

        # Centre: canvas
        self.scene = CanvasScene()
        self.canvas = CanvasView(self.scene)
        h_split.addWidget(self.canvas)

        # Right: properties
        self.props = PropertiesPanel()
        h_split.addWidget(self.props)
        h_split.setSizes([185, 1000, 270])

        v_split.addWidget(h_split)

        # Bottom: results
        self.results = ResultsPanel()
        v_split.addWidget(self.results)
        v_split.setSizes([580, 290])

        vbox.addWidget(v_split)

        # Signals
        self.scene.device_selected.connect(self.props.show_device)
        self.props.property_changed.connect(
            lambda: self.statusBar().showMessage(
                "Property changed — press ▶ Run Simulation to refresh."
            )
        )

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setStyleSheet(f"""
            QToolBar {{
                background: {ABB_RED};
                border: none;
                padding: 4px 8px;
                spacing: 6px;
            }}
        """)

        # Branding
        logo = QLabel("  ⚡  ABB Energy Simulator  ")
        logo.setStyleSheet(
            "color:white; font-size:14px; font-weight:bold; padding:0 10px;"
        )
        tb.addWidget(logo)
        tb.addSeparator()

        def _btn(label, tooltip, color=None, checkable=False):
            b = QPushButton(label)
            b.setToolTip(tooltip)
            b.setCheckable(checkable)
            base = color or "#A30000"
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{base}; color:white;
                    border:1px solid rgba(0,0,0,.25);
                    padding:5px 14px; border-radius:4px;
                    font-weight:bold; font-size:11px;
                }}
                QPushButton:hover   {{ background: #D32F2F; }}
                QPushButton:pressed {{ background: #7F0000; }}
                QPushButton:checked {{ background: #2E7D32; border-color:#1B5E20; }}
            """)
            return b

        self.connect_btn = _btn(
            "🔌 Connect",
            "Toggle connection mode — click two devices to wire them",
            checkable=True,
        )
        self.connect_btn.toggled.connect(self._toggle_connect)
        tb.addWidget(self.connect_btn)

        tb.addWidget(_spacer(8))

        sample_btn = _btn("📋 Load Sample Circuit",
                          "Load a pre-built example circuit to explore the simulator")
        sample_btn.clicked.connect(self._load_sample)
        tb.addWidget(sample_btn)

        clear_btn = _btn("🗑 Clear Canvas",
                         "Remove all devices and wires from the canvas")
        clear_btn.clicked.connect(self._clear)
        tb.addWidget(clear_btn)

        tb.addWidget(_spacer(16))

        run_btn = _btn("▶  Run Simulation",
                       "Simulate 24-hour energy consumption and generate AI recommendations",
                       color="#1565C0")
        run_btn.setStyleSheet(run_btn.styleSheet().replace(
            "background:#1565C0",
            "background:#1565C0"
        ))
        run_btn.setStyleSheet("""
            QPushButton {
                background:#1565C0; color:white;
                border:1px solid #0D47A1;
                padding:5px 22px; border-radius:4px;
                font-weight:bold; font-size:12px;
            }
            QPushButton:hover   { background:#1976D2; }
            QPushButton:pressed { background:#0D47A1; }
        """)
        run_btn.clicked.connect(self._run_simulation)
        tb.addWidget(run_btn)

        # Zoom fit
        tb.addWidget(_spacer(8))
        fit_btn = _btn("⛶ Fit View", "Zoom canvas to fit all devices")
        fit_btn.clicked.connect(self._fit_view)
        tb.addWidget(fit_btn)

        # Spacer + help
        sp = QWidget()
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(sp)

        help_lbl = QLabel(
            "Drag from panel  →  Canvas  ·  Connect button to wire  "
            "·  Click device to edit  ·  Right-click to delete  "
        )
        help_lbl.setStyleSheet("color:rgba(255,255,255,.6); font-size:9.5px;")
        tb.addWidget(help_lbl)

        self.addToolBar(tb)

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background: #ECEFF1; }
            QSplitter::handle:horizontal { width: 2px;  background: #CFD8DC; }
            QSplitter::handle:vertical   { height: 2px; background: #CFD8DC; }
        """)

    # ── Toolbar actions ────────────────────────────────────────────────────
    def _toggle_connect(self, checked: bool):
        self.scene.set_connection_mode(checked)
        if checked:
            self.canvas.setDragMode(QGraphicsView.NoDrag)
            self.canvas.setCursor(Qt.CrossCursor)
            self.statusBar().showMessage(
                "Connection mode  —  click a device to start a wire, "
                "then click another device to complete the connection."
            )
        else:
            self.canvas.setDragMode(QGraphicsView.RubberBandDrag)
            self.canvas.setCursor(Qt.ArrowCursor)
            self.statusBar().showMessage("Ready")

    def _clear(self):
        self.scene.clear_all()          # also calls stop_flow_animation()
        self.props.show_device(None)
        self.connect_btn.setChecked(False)
        self.statusBar().showMessage("Canvas cleared.")

    def _fit_view(self):
        if self.scene.devices:
            r = self.scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
            self.canvas.fitInView(r, Qt.KeepAspectRatio)

    def _run_simulation(self):
        devs = self.scene.get_device_list()
        if not devs:
            self.statusBar().showMessage(
                "⚠  No devices on canvas — drag some devices to build a circuit."
            )
            return

        self.statusBar().showMessage("Running simulation …")
        conns = self.scene.get_connections()

        try:
            result = self._sim_engine.run(devs, conns)
            recs   = self._rec_engine.analyze(devs, conns, result)
            self.results.update_results(result, recs, devs)

            # ── Start animated electricity flow on wires ─────────────────
            # Build {device_id: average_kw} for colour-coding
            n_hours = len(result.time_hours) or 1
            avg_power = {
                did: sum(result.device_power.get(did, [0.0])) / n_hours
                for did, _, _ in devs
            }
            self.scene.start_flow_animation(avg_power)

            self.statusBar().showMessage(
                f"Simulation complete  ·  "
                f"Energy: {result.total_energy_kwh:.1f} kWh/day  ·  "
                f"Peak: {result.peak_power_kw:.1f} kW  ·  "
                f"Cost: ${result.energy_cost_usd:.2f}/day  ·  "
                f"{len(recs)} recommendation(s)"
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Simulation error: {exc}")

    # ── Sample circuit ─────────────────────────────────────────────────────
    def _load_sample(self):
        """
        Pre-built demo circuit:

        Grid ─── Transformer ─── Air CB ─── Motor IE2  (DOL, no VFD → triggers rec)
                                        |
                                        ├── VFD ACS580 ─── Motor IE3 ─── Pump
                                        |
                                        ├── Soft Starter ─── Motor IE4
                                        |
                                        ├── Energy Meter
                                        └── HVAC Unit
        """
        self._clear()

        C = DEVICE_CATALOG
        s = self.scene

        # Row 1
        grid   = s.add_device(C["Grid Supply"],      QPointF(60,  200))
        trafo  = s.add_device(C["Dry Transformer"],  QPointF(240, 200))
        acb    = s.add_device(C["Air Circuit Breaker"], QPointF(420, 200))

        # Branches
        m_ie2  = s.add_device(C["Motor IE2"],         QPointF(600,  80))
        vfd    = s.add_device(C["VFD ACS580"],         QPointF(600, 200))
        m_ie3  = s.add_device(C["Motor IE3"],          QPointF(780, 200))
        pump   = s.add_device(C["Pump"],               QPointF(960, 200))
        ss     = s.add_device(C["Soft Starter PSE"],   QPointF(600, 330))
        m_ie4  = s.add_device(C["Motor IE4"],          QPointF(780, 330))
        meter  = s.add_device(C["Energy Meter"],       QPointF(600, 460))
        hvac   = s.add_device(C["HVAC Unit"],          QPointF(780, 460))

        # Configure some devices
        m_ie2.operating_hours = 16
        m_ie3.operating_hours = 16
        pump.operating_hours  = 16
        hvac.operating_hours  = 10
        hvac.load_factor      = 0.7

        # Wire helper
        def wire(src, dst):
            w = WireItem(src.output_port, dst.input_port)
            s.addItem(w)
            s.wires.append(w)

        wire(grid,  trafo)
        wire(trafo, acb)
        wire(acb,   m_ie2)
        wire(acb,   vfd)
        wire(vfd,   m_ie3)
        wire(m_ie3, pump)
        wire(acb,   ss)
        wire(ss,    m_ie4)
        wire(acb,   meter)
        wire(acb,   hvac)

        self._fit_view()
        self.statusBar().showMessage(
            "Sample circuit loaded — press ▶ Run Simulation to see results and recommendations."
        )


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════
def _spacer(w: int) -> QWidget:
    sp = QWidget()
    sp.setFixedWidth(w)
    return sp
