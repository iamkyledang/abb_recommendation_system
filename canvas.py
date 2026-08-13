"""
Canvas module — QGraphicsScene + QGraphicsView for the electrical system editor.

Features:
  • Drag-and-drop devices from the palette list
  • DeviceItem: rendered box with ABB colours, category symbol, ports
  • DevicePort: green (output) / red (input) circles on each device
  • WireItem: cubic-Bezier bezier wire connecting two ports
  • Connection mode: click device→device to wire them
  • Right-click context menus for delete
  • Scroll-wheel zoom, background dot-grid
"""

import math
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsPathItem,
    QMenu,
)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QPen, QBrush, QColor, QPainterPath, QFont, QPainter, QTransform,
)

# ── Flow animation constants ─────────────────────────────────────────────────
_FLOW_TICK_MS   = 28    # timer interval (ms)  — ~35 fps
_PARTICLE_R     = 4.5   # radius of the travelling dot (px)
_PARTICLE_COUNT = 3     # dots per wire

from devices import DeviceSpec, DeviceCategory, DEVICE_CATALOG

# ── geometry constants ──────────────────────────────────────────────────────
PORT_R   = 7      # port circle radius (px)
DEVICE_W = 112    # device box width
DEVICE_H = 80     # device box height
LABEL_H  = 18     # label area below box


# ════════════════════════════════════════════════════════════════════════════
# Port
# ════════════════════════════════════════════════════════════════════════════
class DevicePort(QGraphicsEllipseItem):
    """A small circle attached to a DeviceItem representing an electrical terminal."""

    def __init__(self, x: float, y: float, port_type: str, parent_device: "DeviceItem"):
        r = PORT_R
        super().__init__(-r, -r, r * 2, r * 2, parent_device)
        self.setPos(x, y)
        self.port_type = port_type          # 'input' | 'output'
        self.parent_device = parent_device
        self.connected_wires: list = []

        color = QColor("#43A047") if port_type == "output" else QColor("#E53935")
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.white, 1.5))
        self.setZValue(3)
        self.setCursor(Qt.CrossCursor)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setToolTip(f"{'Output' if port_type=='output' else 'Input'} terminal\n"
                        "Click in Connect mode to wire")

    def scene_center(self) -> QPointF:
        return self.mapToScene(QPointF(0.0, 0.0))


# ════════════════════════════════════════════════════════════════════════════
# Device Item
# ════════════════════════════════════════════════════════════════════════════
class DeviceItem(QGraphicsItem):
    """Visual block representing one electrical device on the canvas."""

    W = DEVICE_W
    H = DEVICE_H

    def __init__(self, spec: DeviceSpec, device_id: str):
        super().__init__()
        self.device_spec  = spec
        self.device_id    = device_id
        self.load_factor  = 1.0   # 0.1 – 1.0
        self.operating_hours = 8  # h / day

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip(
            f"{spec.model}\n{spec.description}\n"
            f"Rated: {spec.rated_power_kw} kW  η={spec.efficiency*100:.1f}%  PF={spec.power_factor}"
        )

        # Ports
        self.input_port  = DevicePort(0,       self.H // 2, "input",  self)
        self.output_port = DevicePort(self.W,  self.H // 2, "output", self)

        # Name label (below the box)
        self._label = QGraphicsTextItem(spec.name, self)
        self._label.setDefaultTextColor(QColor("#37474F"))
        self._label.setFont(QFont("Segoe UI", 7, QFont.Bold))
        lw = self._label.boundingRect().width()
        self._label.setPos((self.W - lw) / 2, self.H + 1)

    # ── Qt required methods ─────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:
        return QRectF(
            -PORT_R, -PORT_R,
            self.W + PORT_R * 2,
            self.H + PORT_R * 2 + LABEL_H,
        )

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        base = QColor(self.device_spec.icon_color)

        # ── outer border (highlight when selected) ──────────────────────────
        border_pen = (QPen(QColor("#E53935"), 2.5) if self.isSelected()
                      else QPen(base.darker(160), 1.5))
        painter.setPen(border_pen)

        # ── body ────────────────────────────────────────────────────────────
        painter.setBrush(QBrush(base.lighter(185)))
        painter.drawRoundedRect(0, 0, self.W, self.H, 8, 8)

        # ── header stripe ───────────────────────────────────────────────────
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(base))
        header_path = QPainterPath()
        header_path.addRoundedRect(0, 0, self.W, 30, 8, 8)
        header_path.addRect(0, 18, self.W, 12)
        painter.drawPath(header_path)

        # ── category symbol ─────────────────────────────────────────────────
        painter.setPen(QPen(Qt.white, 2))
        self._draw_symbol(painter, self.device_spec.category)

        # ── power / model text ───────────────────────────────────────────────
        painter.setPen(QPen(QColor("#263238"), 1))
        painter.setFont(QFont("Segoe UI", 7))
        pw = self.device_spec.rated_power_kw
        painter.drawText(6, 44, f"{pw} kW" if pw > 0 else "Control")

        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(QPen(QColor("#546E7A"), 1))
        model = self.device_spec.model
        if len(model) > 19:
            model = model[:18] + "…"
        painter.drawText(5, 56, model)

        # ── efficiency badge ────────────────────────────────────────────────
        eff = self.device_spec.efficiency
        if 0 < eff < 1:
            painter.setPen(QPen(QColor("#00695C"), 1))
            painter.setFont(QFont("Segoe UI", 6))
            painter.drawText(5, 68, f"η {eff*100:.1f}%   PF {self.device_spec.power_factor:.2f}")

    # ── category symbols ────────────────────────────────────────────────────
    def _draw_symbol(self, painter: QPainter, cat: DeviceCategory):
        cx, cy = self.W // 2, 14

        if cat == DeviceCategory.MOTOR:
            painter.drawEllipse(QPointF(cx, cy), 9, 9)
            painter.setFont(QFont("Arial", 7, QFont.Bold))
            painter.drawText(cx - 6, cy + 4, "M~")

        elif cat == DeviceCategory.DRIVE:
            painter.drawRect(cx - 14, cy - 8, 28, 16)
            painter.setFont(QFont("Arial", 5, QFont.Bold))
            painter.drawText(cx - 12, cy + 4, "≈ VFD / SS ≈")

        elif cat == DeviceCategory.SOURCE:
            painter.drawEllipse(QPointF(cx, cy), 9, 9)
            painter.drawLine(cx - 6, cy, cx + 6, cy)
            painter.drawLine(cx, cy - 6, cx, cy + 6)

        elif cat == DeviceCategory.PROTECTION:
            # Zig-zag (breaker symbol)
            pts = [
                QPointF(cx - 12, cy),
                QPointF(cx - 6,  cy - 8),
                QPointF(cx,      cy + 8),
                QPointF(cx + 6,  cy - 8),
                QPointF(cx + 12, cy),
            ]
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])

        elif cat == DeviceCategory.TRANSFORMER:
            painter.drawEllipse(QPointF(cx - 7, cy), 7, 7)
            painter.drawEllipse(QPointF(cx + 7, cy), 7, 7)

        elif cat == DeviceCategory.METER:
            painter.drawEllipse(QPointF(cx, cy), 9, 9)
            painter.drawLine(cx, cy, cx + 7, cy - 7)
            painter.drawLine(cx - 8, cy + 3, cx + 8, cy + 3)

        elif cat == DeviceCategory.LOAD:
            painter.drawRect(cx - 10, cy - 8, 20, 16)
            zigzag = [
                QPointF(cx - 7, cy + 4),
                QPointF(cx - 3, cy - 4),
                QPointF(cx + 3, cy + 4),
                QPointF(cx + 7, cy - 4),
            ]
            for i in range(len(zigzag) - 1):
                painter.drawLine(zigzag[i], zigzag[i + 1])

    # ── Wire update on move ─────────────────────────────────────────────────
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for w in self.input_port.connected_wires + self.output_port.connected_wires:
                w.update_path()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        del_act = menu.addAction("🗑  Delete Device")
        action = menu.exec_(event.screenPos())
        if action == del_act:
            s = self.scene()
            if s:
                s.remove_device(self)


# ════════════════════════════════════════════════════════════════════════════
# Wire
# ════════════════════════════════════════════════════════════════════════════
class WireItem(QGraphicsPathItem):
    """Cubic-Bezier wire connecting two DevicePort objects."""

    def __init__(self, start_port: DevicePort, end_port: DevicePort = None):
        super().__init__()
        self.start_port = start_port
        self.end_port   = end_port
        self._end_pt: QPointF = None

        pen = QPen(QColor("#37474F"), 2.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(1)

        # ── flow animation state ──────────────────────────────────────────
        self._flow_active  = False
        self._flow_timer   = QTimer()
        self._flow_timer.timeout.connect(self._tick_flow)
        self._particles: list = []
        self._offsets  = [i / _PARTICLE_COUNT for i in range(_PARTICLE_COUNT)]
        self._speed    = 0.012

        if end_port is not None:
            start_port.connected_wires.append(self)
            end_port.connected_wires.append(self)
            self.update_path()

    # ── path geometry ─────────────────────────────────────────────────────
    def update_path(self):
        if self.end_port is not None:
            p1 = self.start_port.scene_center()
            p2 = self.end_port.scene_center()
        elif self._end_pt is not None:
            p1 = self.start_port.scene_center()
            p2 = self._end_pt
        else:
            return

        dx = p2.x() - p1.x()
        c1 = QPointF(p1.x() + abs(dx) * 0.45, p1.y())
        c2 = QPointF(p2.x() - abs(dx) * 0.45, p2.y())

        path = QPainterPath(p1)
        path.cubicTo(c1, c2, p2)
        self.setPath(path)

        if self._flow_active:
            self._place_particles()

    def set_end_point(self, pt: QPointF):
        self._end_pt = pt
        self.update_path()

    # ── flow animation ────────────────────────────────────────────────────
    def start_flow(self, color: QColor, load_fraction: float = 1.0):
        """Start animated electricity flow. color = wire + particle colour."""
        if self.end_port is None:
            return
        self._flow_active = True

        wire_pen = QPen(color, 3.0)
        wire_pen.setCapStyle(Qt.RoundCap)
        self.setPen(wire_pen)

        # Speed proportional to load (min 40 %, max 100 %)
        self._speed = 0.008 + 0.014 * max(0.4, min(1.0, load_fraction))

        self._destroy_particles()
        scene = self.scene()
        r = _PARTICLE_R
        for _ in range(_PARTICLE_COUNT):
            dot = QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            dot.setBrush(QBrush(Qt.white))
            dot.setPen(QPen(color.darker(140), 1))
            dot.setZValue(5)
            if scene:
                scene.addItem(dot)
            self._particles.append(dot)

        self._place_particles()
        self._flow_timer.start(_FLOW_TICK_MS)

    def stop_flow(self):
        """Stop animation and restore the default wire style."""
        self._flow_active = False
        self._flow_timer.stop()
        self._destroy_particles()

        pen = QPen(QColor("#37474F"), 2.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)

    def _tick_flow(self):
        self._offsets = [(o + self._speed) % 1.0 for o in self._offsets]
        self._place_particles()

    def _place_particles(self):
        path   = self.path()
        length = path.length()
        if length < 1:
            return
        for dot, off in zip(self._particles, self._offsets):
            pt = path.pointAtPercent(off)
            dot.setPos(pt)

    def _destroy_particles(self):
        scene = self.scene()
        for dot in self._particles:
            if scene and dot.scene():
                scene.removeItem(dot)
        self._particles.clear()

    def contextMenuEvent(self, event):
        menu = QMenu()
        del_act = menu.addAction("🗑  Delete Wire")
        action = menu.exec_(event.screenPos())
        if action == del_act:
            s = self.scene()
            if s:
                s.remove_wire(self)


# ════════════════════════════════════════════════════════════════════════════
# Scene
# ════════════════════════════════════════════════════════════════════════════
class CanvasScene(QGraphicsScene):
    """Main editing scene — manages devices, wires, connection mode."""

    device_selected = pyqtSignal(object)   # DeviceItem | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-300, -200, 2600, 2000)

        self.devices: dict[str, DeviceItem] = {}
        self.wires: list[WireItem] = []
        self._counter: int = 0

        self.connection_mode: bool = False
        self._pending_wire: WireItem = None
        self._start_port: DevicePort = None

    # ── Public API ──────────────────────────────────────────────────────────
    def add_device(self, spec: DeviceSpec, pos: QPointF) -> DeviceItem:
        self._counter += 1
        did = f"{spec.name.replace(' ', '_')}_{self._counter}"
        item = DeviceItem(spec, did)
        item.setPos(pos)
        self.addItem(item)
        self.devices[did] = item
        return item

    def remove_device(self, item: DeviceItem):
        to_rm = (list(item.input_port.connected_wires)
                 + list(item.output_port.connected_wires))
        for w in to_rm:
            self.remove_wire(w)
        self.devices.pop(item.device_id, None)
        self.removeItem(item)

    def remove_wire(self, wire: WireItem):
        for port in (wire.start_port, wire.end_port):
            if port and wire in port.connected_wires:
                port.connected_wires.remove(wire)
        if wire in self.wires:
            self.wires.remove(wire)
        if wire.scene():
            self.removeItem(wire)

    def set_connection_mode(self, enabled: bool):
        self.connection_mode = enabled
        if not enabled:
            self._cancel_pending()

    # ── Flow animation public API ────────────────────────────────────────────
    def start_flow_animation(self, device_power: dict):
        """
        Animate every connected wire.

        device_power: {device_id: avg_kw}  — used to colour-code load level.
        Colour scale (inspired by ABB brand):
          low load   → blue   (#1565C0)
          medium     → amber  (#F57F17)
          high load  → red    (#CC0000)  (ABB red)
        """
        # Work out max power across all devices for normalisation
        max_kw = max(device_power.values(), default=1.0) or 1.0

        # Map each device id to a normalised load fraction
        def _load_frac(did: str) -> float:
            return min(1.0, device_power.get(did, 0.0) / max_kw)

        def _wire_color(frac: float) -> QColor:
            # Interpolate blue → amber → ABB red
            if frac < 0.5:
                t = frac / 0.5
                r = int(21  + t * (245 - 21))
                g = int(101 + t * (127 - 101))
                b = int(192 + t * (23  - 192))
            else:
                t = (frac - 0.5) / 0.5
                r = int(245 + t * (204 - 245))
                g = int(127 + t * (0   - 127))
                b = int(23  + t * (0   - 23))
            return QColor(r, g, b)

        for wire in self.wires:
            if wire.end_port is None:
                continue
            src_id = wire.start_port.parent_device.device_id
            dst_id = wire.end_port.parent_device.device_id
            # Use the higher of the two connected device loads
            frac   = max(_load_frac(src_id), _load_frac(dst_id))
            color  = _wire_color(frac)
            wire.start_flow(color, frac)

    def stop_flow_animation(self):
        """Stop all wire animations and reset wire appearance."""
        for wire in self.wires:
            wire.stop_flow()

    def clear_all(self):
        self.stop_flow_animation()
        for did in list(self.devices.keys()):
            if did in self.devices:
                self.remove_device(self.devices[did])

    def get_connections(self) -> list:
        return [
            (w.start_port.parent_device.device_id,
             w.end_port.parent_device.device_id)
            for w in self.wires if w.end_port
        ]

    def get_device_list(self) -> list:
        return [(did, item.device_spec, item)
                for did, item in self.devices.items()]

    # ── Connection mode helpers ─────────────────────────────────────────────
    def _port_for_item(self, item) -> DevicePort:
        """Return the appropriate port to use for the given item."""
        if isinstance(item, DevicePort):
            return item
        if isinstance(item, DeviceItem):
            return item.output_port if self._start_port is None else item.input_port
        return None

    def _cancel_pending(self):
        if self._pending_wire:
            self.removeItem(self._pending_wire)
            self._pending_wire = None
        self._start_port = None

    # ── Mouse events ────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if self.connection_mode and event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            port = self._port_for_item(item)

            if port is not None:
                if self._start_port is None:
                    # Start wire
                    self._start_port = port
                    self._pending_wire = WireItem(port)
                    self.addItem(self._pending_wire)
                elif port.parent_device is not self._start_port.parent_device:
                    # Complete wire
                    wire = WireItem(self._start_port, port)
                    self.addItem(wire)
                    self.wires.append(wire)
                    self._cancel_pending()
                else:
                    # Clicked same device — cancel
                    self._cancel_pending()
            else:
                # Clicked empty space — cancel
                self._cancel_pending()
            return   # don't propagate in connection mode

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.connection_mode and self._pending_wire:
            self._pending_wire.set_end_point(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        sel = self.selectedItems()
        dev = next((i for i in sel if isinstance(i, DeviceItem)), None)
        self.device_selected.emit(dev)


# ════════════════════════════════════════════════════════════════════════════
# View
# ════════════════════════════════════════════════════════════════════════════
class CanvasView(QGraphicsView):
    """Zoomable / pannable view for the CanvasScene with dot-grid background."""

    def __init__(self, scene: CanvasScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._canvas_scene = scene

    def drawBackground(self, painter: QPainter, rect):
        # Background fill
        painter.fillRect(rect, QColor("#F4F6F9"))

        # Major grid lines (80 px)
        major_pen = QPen(QColor("#D0D8E4"), 1)
        painter.setPen(major_pen)
        grid = 80
        left = int(rect.left())  - int(rect.left())  % grid
        top  = int(rect.top())   - int(rect.top())   % grid
        for x in range(left, int(rect.right()) + grid, grid):
            painter.drawLine(x, int(rect.top()),  x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()) + grid, grid):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

        # Minor dot grid (40 px)
        dot_pen = QPen(QColor("#B0BEC5"), 1)
        painter.setPen(dot_pen)
        minor = 40
        left2 = int(rect.left())  - int(rect.left())  % minor
        top2  = int(rect.top())   - int(rect.top())   % minor
        for x in range(left2, int(rect.right()) + minor, minor):
            for y in range(top2, int(rect.bottom()) + minor, minor):
                painter.drawPoint(x, y)

    # ── Scroll-wheel zoom ────────────────────────────────────────────────────
    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.scale(factor, factor)

    # ── Drag-and-drop from device palette ────────────────────────────────────
    def dragEnterEvent(self, event):
        event.accept() if event.mimeData().hasText() else event.ignore()

    def dragMoveEvent(self, event):
        event.accept() if event.mimeData().hasText() else event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            name = event.mimeData().text()
            if name in DEVICE_CATALOG:
                pos = self.mapToScene(event.pos())
                # Snap to 40 px grid
                pos = QPointF(
                    round(pos.x() / 40) * 40,
                    round(pos.y() / 40) * 40,
                )
                self._canvas_scene.add_device(DEVICE_CATALOG[name], pos)
            event.accept()
