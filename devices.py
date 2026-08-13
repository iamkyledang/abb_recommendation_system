"""
ABB Device Catalog — AI-Powered Electrical Energy Simulator
Devices are based on ABB's real product portfolio (Motors, Drives, Protection, etc.)
"""

from dataclasses import dataclass, field
from typing import Dict, Any
from enum import Enum


class DeviceCategory(Enum):
    SOURCE = "Power Source"
    TRANSFORMER = "Transformer"
    PROTECTION = "Protection"
    MOTOR = "Motor"
    DRIVE = "Drive & Starter"
    METER = "Meter"
    LOAD = "Load"


@dataclass
class DeviceSpec:
    name: str
    category: DeviceCategory
    model: str
    description: str
    icon_color: str          # hex color for visual representation
    rated_power_kw: float    # nameplate kW
    efficiency: float        # 0–1  (or COP for HVAC)
    power_factor: float      # 0–1
    voltage_v: float
    parameters: Dict[str, Any] = field(default_factory=dict)

    def get_consumption_kw(self, load_factor: float = 1.0) -> float:
        """Input power drawn at a given load factor."""
        if self.category == DeviceCategory.SOURCE:
            return 0.0
        if self.rated_power_kw == 0:
            return 0.0
        return self.rated_power_kw * load_factor / max(self.efficiency, 0.01)


# ---------------------------------------------------------------------------
# ABB Product Portfolio — curated for industrial energy simulation
# ---------------------------------------------------------------------------
ABB_DEVICES = [

    # ── Power Sources ───────────────────────────────────────────────────────
    DeviceSpec(
        name="Grid Supply",
        category=DeviceCategory.SOURCE,
        model="Utility Grid 400 V / 50 Hz",
        description="Low-voltage grid connection point (400 V, 50 Hz, TN-S system).",
        icon_color="#2C3E50",
        rated_power_kw=0, efficiency=1.0, power_factor=1.0, voltage_v=400,
        parameters={"voltage_kv": 0.4, "frequency_hz": 50, "short_circuit_mva": 10},
    ),
    DeviceSpec(
        name="Diesel Generator",
        category=DeviceCategory.SOURCE,
        model="ABB Backup Genset 200 kVA",
        description="Emergency / backup diesel generator with AVR voltage regulation.",
        icon_color="#6D4C41",
        rated_power_kw=160, efficiency=0.92, power_factor=0.80, voltage_v=400,
        parameters={"kva": 200, "fuel_l_h": 38, "start_time_s": 10},
    ),

    # ── Transformers ────────────────────────────────────────────────────────
    DeviceSpec(
        name="Dry Transformer",
        category=DeviceCategory.TRANSFORMER,
        model="ABB RESIBLOC 630 kVA",
        description=(
            "ABB RESIBLOC cast-resin dry-type transformer. "
            "Dyn11, 11 kV / 400 V, Tier 2 Ecodesign compliant. "
            "No-load loss 0.95 kW, load loss 6.3 kW at full load."
        ),
        icon_color="#8D6E63",
        rated_power_kw=630, efficiency=0.9875, power_factor=1.0, voltage_v=400,
        parameters={
            "primary_kv": 11, "secondary_v": 400, "kva": 630,
            "no_load_loss_kw": 0.95, "full_load_loss_kw": 6.3,
            "vector_group": "Dyn11",
        },
    ),
    DeviceSpec(
        name="Oil Transformer",
        category=DeviceCategory.TRANSFORMER,
        model="ABB ONAN 1000 kVA",
        description=(
            "ABB oil-immersed distribution transformer. "
            "ONAN cooling, 20 kV / 400 V, AMDT-S energy-efficient design."
        ),
        icon_color="#5D4037",
        rated_power_kw=1000, efficiency=0.9920, power_factor=1.0, voltage_v=400,
        parameters={
            "primary_kv": 20, "secondary_v": 400, "kva": 1000,
            "no_load_loss_kw": 1.1, "full_load_loss_kw": 9.0,
            "cooling": "ONAN",
        },
    ),

    # ── Protection ──────────────────────────────────────────────────────────
    DeviceSpec(
        name="Circuit Breaker",
        category=DeviceCategory.PROTECTION,
        model="ABB Tmax XT2 160 A",
        description=(
            "ABB Tmax XT2 molded-case circuit breaker. "
            "160 A, 36 kA breaking capacity, thermal-magnetic trip unit."
        ),
        icon_color="#1565C0",
        rated_power_kw=0.0, efficiency=1.0, power_factor=1.0, voltage_v=400,
        parameters={"rated_current_a": 160, "breaking_kA": 36, "poles": 3},
    ),
    DeviceSpec(
        name="Air Circuit Breaker",
        category=DeviceCategory.PROTECTION,
        model="ABB SACE Emax2 E1.2 1250 A",
        description=(
            "ABB SACE Emax2 intelligent air circuit breaker. "
            "1250 A, 150 kA, Ekip Touch trip unit with energy metering & Modbus."
        ),
        icon_color="#0D47A1",
        rated_power_kw=0.0, efficiency=1.0, power_factor=1.0, voltage_v=400,
        parameters={
            "rated_current_a": 1250, "breaking_kA": 150, "poles": 4,
            "ekip_metering": True, "communication": "Modbus RTU",
        },
    ),
    DeviceSpec(
        name="Contactor",
        category=DeviceCategory.PROTECTION,
        model="ABB AF40-30-00-13",
        description=(
            "ABB AF-series electronically controlled contactor. "
            "40 A / AC3, 18.5 kW@400 V, coil 24–500 V AC/DC. Low coil power: 1.8 W."
        ),
        icon_color="#00838F",
        rated_power_kw=0.002, efficiency=1.0, power_factor=0.85, voltage_v=400,
        parameters={"rated_current_a": 40, "motor_kw_ac3": 18.5, "coil_w": 1.8},
    ),

    # ── Motors ───────────────────────────────────────────────────────────────
    DeviceSpec(
        name="Motor IE2",
        category=DeviceCategory.MOTOR,
        model="ABB M2BAX 7.5 kW IE2",
        description=(
            "ABB M2BAX cast-iron frame motor. IE2 Standard Efficiency. "
            "7.5 kW, 4-pole, 1450 rpm, 400/690 V. η = 88.7 %."
        ),
        icon_color="#E65100",
        rated_power_kw=7.5, efficiency=0.887, power_factor=0.84, voltage_v=400,
        parameters={
            "speed_rpm": 1450, "poles": 4, "efficiency_class": "IE2",
            "rated_torque_nm": 49.3, "starting_current_ia": 7.0,
        },
    ),
    DeviceSpec(
        name="Motor IE3",
        category=DeviceCategory.MOTOR,
        model="ABB M3BP 7.5 kW IE3",
        description=(
            "ABB M3BP cast-iron frame motor. IE3 Premium Efficiency. "
            "7.5 kW, 4-pole, 1450 rpm. η = 91.0 %. Meets EU 2021 regulation."
        ),
        icon_color="#2E7D32",
        rated_power_kw=7.5, efficiency=0.910, power_factor=0.86, voltage_v=400,
        parameters={
            "speed_rpm": 1450, "poles": 4, "efficiency_class": "IE3",
            "rated_torque_nm": 49.3, "starting_current_ia": 6.8,
        },
    ),
    DeviceSpec(
        name="Motor IE4",
        category=DeviceCategory.MOTOR,
        model="ABB M4BP 7.5 kW IE4",
        description=(
            "ABB M4BP motor. IE4 Super Premium Efficiency. "
            "7.5 kW, 4-pole. η = 92.9 %. Required for ≥75 kW from 2023 (EU 2019/1781)."
        ),
        icon_color="#00695C",
        rated_power_kw=7.5, efficiency=0.929, power_factor=0.88, voltage_v=400,
        parameters={
            "speed_rpm": 1450, "poles": 4, "efficiency_class": "IE4",
            "rated_torque_nm": 49.3, "starting_current_ia": 6.5,
        },
    ),
    DeviceSpec(
        name="SynRM IE5",
        category=DeviceCategory.MOTOR,
        model="ABB SynRM 11 kW IE5",
        description=(
            "ABB Synchronous Reluctance Motor (SynRM) — IE5 Ultra-Premium Efficiency. "
            "11 kW, 4-pole. η = 94.8 %. No rotor copper losses. Must be used with ACS880."
        ),
        icon_color="#1B5E20",
        rated_power_kw=11, efficiency=0.948, power_factor=0.90, voltage_v=400,
        parameters={
            "speed_rpm": 1500, "poles": 4, "efficiency_class": "IE5",
            "type": "SynRM", "drive_required": "ACS880",
        },
    ),
    DeviceSpec(
        name="Motor 22 kW IE3",
        category=DeviceCategory.MOTOR,
        model="ABB M3BP 22 kW IE3",
        description=(
            "ABB M3BP large frame motor. IE3 Premium Efficiency. "
            "22 kW, 4-pole, 1480 rpm. η = 93.6 %."
        ),
        icon_color="#388E3C",
        rated_power_kw=22, efficiency=0.936, power_factor=0.87, voltage_v=400,
        parameters={
            "speed_rpm": 1480, "poles": 4, "efficiency_class": "IE3",
            "rated_torque_nm": 142, "starting_current_ia": 6.5,
        },
    ),

    # ── Drives & Starters ───────────────────────────────────────────────────
    DeviceSpec(
        name="VFD ACS180",
        category=DeviceCategory.DRIVE,
        model="ABB ACS180 3 kW",
        description=(
            "ABB ACS180 machinery/HVAC drive. Entry-level, compact design. "
            "3 kW, 400 V, 7.2 A. Built-in EMC Class C2 filter. Coated PCBs."
        ),
        icon_color="#7B1FA2",
        rated_power_kw=3, efficiency=0.97, power_factor=0.96, voltage_v=400,
        parameters={
            "max_output_hz": 500, "overload_pct": 150,
            "control_modes": "Scalar/Vector", "speed_range_rpm": "0–3000",
        },
    ),
    DeviceSpec(
        name="VFD ACS580",
        category=DeviceCategory.DRIVE,
        model="ABB ACS580 11 kW",
        description=(
            "ABB ACS580 general purpose drive. 11 kW, 400 V, 25 A. "
            "Built-in EMC filter + line choke. Assistant control panel. "
            "ABB Ability™ compatible. η ≈ 98 %."
        ),
        icon_color="#4A148C",
        rated_power_kw=11, efficiency=0.980, power_factor=0.97, voltage_v=400,
        parameters={
            "max_output_hz": 500, "overload_pct": 110,
            "control_modes": "Scalar/DTC", "built_in_filter": True,
            "speed_range_rpm": "0–3000",
        },
    ),
    DeviceSpec(
        name="VFD ACS880",
        category=DeviceCategory.DRIVE,
        model="ABB ACS880 18.5 kW",
        description=(
            "ABB ACS880 industrial drive. 18.5 kW, 400 V, 38 A. "
            "Direct Torque Control (DTC). Cabinet or wall mounting. "
            "Safe Torque Off (STO) SIL 3. η ≈ 98.5 %. Required for SynRM IE5."
        ),
        icon_color="#311B92",
        rated_power_kw=18.5, efficiency=0.985, power_factor=0.98, voltage_v=400,
        parameters={
            "max_output_hz": 300, "overload_pct": 150,
            "control_modes": "DTC", "safety": "STO SIL3",
            "speed_range_rpm": "0–6000",
        },
    ),
    DeviceSpec(
        name="Soft Starter PSE",
        category=DeviceCategory.DRIVE,
        model="ABB PSE25 11 kW",
        description=(
            "ABB PSE electronic soft starter. 11 kW, 25 A, 208–600 V. "
            "Integrated bypass contactor. Reduces inrush current to 3–4× FLA. "
            "Motor protection relay included."
        ),
        icon_color="#006064",
        rated_power_kw=11, efficiency=0.990, power_factor=0.98, voltage_v=400,
        parameters={
            "start_ramp_s": 10, "stop_ramp_s": 10, "bypass_contactor": True,
            "starting_current_max": "4× FLA",
        },
    ),

    # ── Meters ──────────────────────────────────────────────────────────────
    DeviceSpec(
        name="Energy Meter",
        category=DeviceCategory.METER,
        model="ABB B24 112-100",
        description=(
            "ABB B24 multi-function energy meter. Class 1 (IEC 62053-21). "
            "Measures kWh, kVArh, kVA, PF, harmonics. M-Bus + Ethernet. "
            "65 A direct connection. DIN rail mount."
        ),
        icon_color="#0277BD",
        rated_power_kw=0.003, efficiency=1.0, power_factor=1.0, voltage_v=400,
        parameters={
            "accuracy_class": 1, "communication": "M-Bus + Ethernet",
            "measurements": "kWh / kVArh / PF / THD", "max_current_a": 65,
        },
    ),
    DeviceSpec(
        name="Power Quality Meter",
        category=DeviceCategory.METER,
        model="ABB M4M 30 Network Analyzer",
        description=(
            "ABB M4M 30 power quality and energy analyzer. "
            "Class A power quality (IEC 61000-4-30). Modbus RTU/TCP. "
            "Records harmonics up to 63rd order."
        ),
        icon_color="#01579B",
        rated_power_kw=0.005, efficiency=1.0, power_factor=1.0, voltage_v=400,
        parameters={
            "accuracy_class": "A (IEC 61000-4-30)",
            "communication": "Modbus RTU + TCP",
            "harmonic_order": 63,
        },
    ),

    # ── Loads ────────────────────────────────────────────────────────────────
    DeviceSpec(
        name="Pump",
        category=DeviceCategory.LOAD,
        model="Centrifugal Pump 11 kW",
        description=(
            "Industrial centrifugal water pump. 11 kW shaft power. "
            "50 m³/h @ 40 m head. Follows affinity laws — ideal VFD candidate."
        ),
        icon_color="#00796B",
        rated_power_kw=11, efficiency=0.80, power_factor=0.83, voltage_v=400,
        parameters={"flow_m3_h": 50, "head_m": 40, "type": "Centrifugal"},
    ),
    DeviceSpec(
        name="Compressor",
        category=DeviceCategory.LOAD,
        model="Rotary Screw Compressor 15 kW",
        description=(
            "Industrial rotary screw air compressor. 15 kW, 7 bar, 2.5 m³/min FAD. "
            "VFD-controlled compressors can save 35–50% vs fixed-speed."
        ),
        icon_color="#BF360C",
        rated_power_kw=15, efficiency=0.85, power_factor=0.82, voltage_v=400,
        parameters={"pressure_bar": 7, "flow_m3_min": 2.5, "type": "Rotary Screw"},
    ),
    DeviceSpec(
        name="HVAC Unit",
        category=DeviceCategory.LOAD,
        model="Industrial HVAC 20 kW",
        description=(
            "Industrial HVAC unit. Inverter compressor, COP 3.5 (cooling) / 4.2 (heating). "
            "20 kW electrical input = 70 kW thermal output."
        ),
        icon_color="#1565C0",
        rated_power_kw=20, efficiency=3.5, power_factor=0.85, voltage_v=400,
        parameters={"cop_cooling": 3.5, "cop_heating": 4.2, "type": "Air-Cooled Split"},
    ),
    DeviceSpec(
        name="LED Lighting",
        category=DeviceCategory.LOAD,
        model="Industrial LED Panel 5 kW",
        description=(
            "Industrial LED lighting system. 5 kW total, 150 lm/W efficacy, IP65. "
            "Replaces 14 kW HPS system. DALI dimmable."
        ),
        icon_color="#F57F17",
        rated_power_kw=5, efficiency=0.95, power_factor=0.92, voltage_v=230,
        parameters={
            "luminous_efficacy_lm_w": 150, "operating_h_day": 10,
            "replaced_hps_kw": 14, "control": "DALI",
        },
    ),
    DeviceSpec(
        name="Conveyor",
        category=DeviceCategory.LOAD,
        model="Industrial Conveyor Belt 5.5 kW",
        description=(
            "Belt conveyor driven by gearmotor. 5.5 kW, variable load profile. "
            "Speed control via VFD reduces energy 20–40%."
        ),
        icon_color="#4E342E",
        rated_power_kw=5.5, efficiency=0.82, power_factor=0.80, voltage_v=400,
        parameters={"belt_speed_m_s": 1.5, "load_variation": "high"},
    ),
]

DEVICE_CATALOG: Dict[str, DeviceSpec] = {d.name: d for d in ABB_DEVICES}
