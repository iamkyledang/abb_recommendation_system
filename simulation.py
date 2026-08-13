"""
Simulation Engine — 24-hour energy consumption simulation.

For each device in the scene the engine:
  1. Picks a realistic 24-hour load profile based on category and
     user-configured operating hours.
  2. Applies physical models (motor affinity law for drives, transformer
     losses, etc.) to compute input power at every hourly time-step.
  3. Integrates power over time to give energy (kWh), cost, and CO₂.

All calculations are in kW (real power at the device input terminals).
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

from devices import DeviceSpec, DeviceCategory


# ════════════════════════════════════════════════════════════════════════════
# Result container
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class SimulationResult:
    time_hours: List[float] = field(default_factory=list)
    total_power_kw: List[float] = field(default_factory=list)
    device_power: Dict[str, List[float]] = field(default_factory=dict)

    total_energy_kwh: float = 0.0
    peak_power_kw: float = 0.0
    energy_cost_usd: float = 0.0
    co2_kg: float = 0.0

    # per-device aggregates (filled after run)
    device_energy_kwh: Dict[str, float] = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════════════
# Engine
# ════════════════════════════════════════════════════════════════════════════
class SimulationEngine:
    """
    Simulates 24 hours of operation (or `duration_h` hours) at 1-hour steps.
    """

    # Electricity tariff and carbon intensity (adjust per region)
    RATE_USD_PER_KWH: float = 0.12
    CO2_KG_PER_KWH: float  = 0.40   # EU grid average ~2024

    # ── Public entry-point ──────────────────────────────────────────────────
    def run(
        self,
        device_list: List[Tuple],   # [(id, DeviceSpec, DeviceItem), ...]
        connections: List[Tuple],   # [(src_id, dst_id), ...]
        duration_h: int = 24,
    ) -> SimulationResult:

        result = SimulationResult()
        result.time_hours = list(range(duration_h + 1))

        # ── per-device hourly power ─────────────────────────────────────────
        for did, spec, item in device_list:
            result.device_power[did] = [
                self._power_at(spec, item, t) for t in result.time_hours
            ]

        # ── totals ─────────────────────────────────────────────────────────
        n = len(result.time_hours)
        result.total_power_kw = [
            sum(result.device_power[did][ti]
                for did, _, _ in device_list)
            for ti in range(n)
        ]

        result.total_energy_kwh = _trapz(result.total_power_kw, result.time_hours)
        result.peak_power_kw    = max(result.total_power_kw, default=0.0)
        result.energy_cost_usd  = result.total_energy_kwh * self.RATE_USD_PER_KWH
        result.co2_kg           = result.total_energy_kwh * self.CO2_KG_PER_KWH

        # per-device energy integrals
        for did in result.device_power:
            result.device_energy_kwh[did] = _trapz(
                result.device_power[did], result.time_hours
            )

        return result

    # ── Power model per device ──────────────────────────────────────────────
    def _power_at(self, spec: DeviceSpec, item, t: int) -> float:
        """Return input kW at hour *t* for this device."""
        if spec.category == DeviceCategory.SOURCE:
            return 0.0
        if spec.rated_power_kw == 0.0:
            return 0.0

        lf   = max(0.1, min(1.0, getattr(item, "load_factor",     1.0)))
        op_h = max(1,   min(24,  getattr(item, "operating_hours",  8)))
        pf   = _load_profile(spec.category, t, op_h)   # 0..1 temporal factor

        # ── Meter: constant small draw ─────────────────────────────────────
        if spec.category == DeviceCategory.METER:
            return spec.rated_power_kw

        # ── Transformer: no-load + load-dependent losses ───────────────────
        if spec.category == DeviceCategory.TRANSFORMER:
            p_fe   = spec.parameters.get("no_load_loss_kw",  spec.rated_power_kw * 0.0015)
            p_cu_fl = spec.parameters.get("full_load_loss_kw", spec.rated_power_kw * 0.010)
            # Load losses scale as I² ∝ load²
            p_cu  = p_cu_fl * (lf ** 2)
            return (p_fe + p_cu) * pf

        # ── Variable-frequency drive (motor follows affinity law) ───────────
        if spec.category == DeviceCategory.DRIVE:
            # Average speed setpoint reduced from full speed
            # Affinity law: P ∝ n³  → big savings at reduced speed
            speed_ratio = max(0.35, lf * 0.85)   # typically 35–100%
            shaft_power = spec.rated_power_kw * (speed_ratio ** 3)
            input_power = shaft_power / spec.efficiency
            return input_power * pf

        # ── Motor (direct-on-line) ─────────────────────────────────────────
        if spec.category == DeviceCategory.MOTOR:
            return (spec.rated_power_kw * lf / spec.efficiency) * pf

        # ── Contactor / protection: minimal coil power ─────────────────────
        if spec.category == DeviceCategory.PROTECTION:
            return spec.rated_power_kw * pf

        # ── Generic load (HVAC, lighting, compressor, conveyor…) ──────────
        eff = spec.efficiency
        if eff > 3:
            # COP-based device (HVAC) — efficiency is COP, rate power is electrical input
            return spec.rated_power_kw * lf * pf
        return (spec.rated_power_kw * lf / max(eff, 0.01)) * pf


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════
def _load_profile(cat: DeviceCategory, t: int, op_h: int) -> float:
    """
    Normalised temporal load factor (0..1) at hour *t* of a 24-hour day.

    Operating hours are centred around 12:00 (noon).
    During operation a smooth sinusoidal variation of ±20 % is applied to
    model realistic load variation (shift changes, demand peaks, etc.).
    """
    # Window centred at noon
    half = op_h / 2.0
    start = max(0.0, 12.0 - half)
    end   = min(24.0, start + op_h)

    if start <= t <= end:
        # Sinusoidal shape: peak at 70% through operating window
        phase = math.pi * (t - start) / max(end - start, 1.0)
        return 0.80 + 0.20 * math.sin(phase)

    # Short ramp-down after shift
    if end < t <= end + 1.5:
        return 0.30

    # Night-time standby (lights, meters keep small draw)
    if cat in (DeviceCategory.METER, DeviceCategory.LOAD):
        return 0.04
    if cat == DeviceCategory.TRANSFORMER:
        return 0.10   # no-load losses always present
    return 0.02


def _trapz(y: List[float], x: List[float]) -> float:
    """Trapezoidal integration — avoids numpy dependency for core math."""
    if len(y) < 2:
        return 0.0
    total = 0.0
    for i in range(len(y) - 1):
        total += (y[i] + y[i + 1]) * (x[i + 1] - x[i]) / 2.0
    return total
