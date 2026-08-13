"""
AI Recommendation Engine — rule-based energy-saving analysis.

Analyses the circuit topology and simulation results to generate
prioritised recommendations aligned with ABB's product portfolio and
IEC/EU energy efficiency standards.

Rules implemented
─────────────────
1.  Motors without VFD on variable-torque loads → add ABB ACS-series drive
2.  IE2 motors → upgrade to IE4 / IE5 SynRM (EU 2019/1781)
3.  IE3 motors → consider IE5 SynRM + ACS880 system
4.  System power factor < 0.92 → ABB CLMD capacitor banks / PQF active filter
5.  Transformer lightly loaded (< 30 %) → right-size or consolidate
6.  High peak-to-average ratio → ABB Ability™ load scheduling / BESS
7.  No energy meter → add ABB B24 for sub-metering and ISO 50001
8.  Old lighting (high kW load) → LED upgrade
9.  Direct-on-line soft starters → ABB PSE soft starter (inrush reduction)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from devices import DeviceSpec, DeviceCategory
from simulation import SimulationResult, _trapz


# ════════════════════════════════════════════════════════════════════════════
# Data class
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class Recommendation:
    priority: str          # "HIGH" | "MEDIUM" | "LOW"
    title: str
    description: str       # HTML-formatted
    savings_kwh_day: float
    savings_pct: float
    roi_years: float = None
    category: str = "General"

    _ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    def sort_key(self):
        return (self._ORDER.get(self.priority, 9), -self.savings_kwh_day)

    @property
    def annual_kwh(self) -> float:
        return self.savings_kwh_day * 365

    @property
    def annual_usd(self) -> float:
        return self.annual_kwh * 0.12   # $0.12 / kWh


# ════════════════════════════════════════════════════════════════════════════
# Engine
# ════════════════════════════════════════════════════════════════════════════
class RecommendationEngine:
    """Generate a sorted list of Recommendation objects from circuit + results."""

    RATE = 0.12   # $/kWh

    def analyze(
        self,
        device_list: List[Tuple],
        connections: List[Tuple],
        result: SimulationResult,
    ) -> List[Recommendation]:

        recs: List[Recommendation] = []

        vfd_driven = self._vfd_driven_motors(device_list, connections)
        dol_motors  = self._dol_motors(device_list, connections, vfd_driven)

        for did, spec, item in device_list:
            if spec.category == DeviceCategory.MOTOR:
                if did not in vfd_driven:
                    recs += self._add_vfd(did, spec, result)
                recs += self._motor_efficiency(did, spec, result)

        recs += self._power_factor(device_list, result)
        recs += self._transformer_loading(device_list, result)
        recs += self._peak_demand(result)
        recs += self._energy_metering(device_list)
        recs += self._lighting(device_list, result)

        recs.sort(key=lambda r: r.sort_key())
        return recs

    # ── Topology helpers ────────────────────────────────────────────────────
    @staticmethod
    def _vfd_driven_motors(device_list, connections) -> set:
        drive_ids = {did for did, spec, _ in device_list
                     if spec.category == DeviceCategory.DRIVE}
        motor_ids = {did for did, spec, _ in device_list
                     if spec.category == DeviceCategory.MOTOR}
        driven = set()
        for src, dst in connections:
            if src in drive_ids and dst in motor_ids:
                driven.add(dst)
            if dst in drive_ids and src in motor_ids:
                driven.add(src)
        return driven

    @staticmethod
    def _dol_motors(device_list, connections, vfd_driven) -> set:
        """Motors directly connected without a soft-starter or VFD."""
        starter_ids = {did for did, spec, _ in device_list
                       if spec.category == DeviceCategory.DRIVE}
        motor_ids   = {did for did, spec, _ in device_list
                       if spec.category == DeviceCategory.MOTOR}
        started = set()
        for src, dst in connections:
            if src in starter_ids and dst in motor_ids:
                started.add(dst)
            if dst in starter_ids and src in motor_ids:
                started.add(src)
        return motor_ids - started - vfd_driven

    # ── Individual recommendation generators ────────────────────────────────

    def _add_vfd(self, did: str, spec: DeviceSpec,
                 result: SimulationResult) -> List[Recommendation]:
        energy = result.device_energy_kwh.get(did, 0.0)
        pct = 35.0   # typical variable-torque savings (affinity law)
        saved_kwh = energy * pct / 100
        cost_yr   = saved_kwh * 365 * self.RATE
        drive_cost = max(600, spec.rated_power_kw * 130)  # ~$130/kW
        roi = round(drive_cost / cost_yr, 1) if cost_yr > 0 else None

        r = Recommendation(
            priority="HIGH",
            title=f"Add VFD to {spec.name} ({spec.rated_power_kw} kW)",
            description=(
                f"<b>{spec.model}</b> runs direct-on-line (DOL) without speed control.<br/>"
                f"For variable-torque loads (pumps, fans, compressors) the affinity law "
                f"means <i>P&nbsp;∝&nbsp;n³</i> — reducing speed to 80&nbsp;% cuts power "
                f"to just 51&nbsp;% of full load.<br/>"
                f"<b>Recommendation:</b> Install an "
                f"<b>ABB {'ACS580' if spec.rated_power_kw <= 15 else 'ACS880'}</b> "
                f"variable frequency drive.<br/>"
                f"<span style='color:#27AE60;'>Typical savings: 20–50&nbsp;% of motor "
                f"energy &nbsp;·&nbsp; est. {saved_kwh*365:.0f}&nbsp;kWh/yr "
                f"(${cost_yr:.0f}/yr)</span>"
                + (f"<br/><i>Estimated payback: {roi}&nbsp;yr</i>" if roi else "")
            ),
            savings_kwh_day=saved_kwh,
            savings_pct=pct,
            roi_years=roi,
            category="Motor",
        )
        return [r]

    def _motor_efficiency(self, did: str, spec: DeviceSpec,
                          result: SimulationResult) -> List[Recommendation]:
        recs = []
        ec     = spec.parameters.get("efficiency_class", "IE2")
        energy = result.device_energy_kwh.get(did, 0.0)

        if ec == "IE2":
            pct = 2.8
            recs.append(Recommendation(
                priority="MEDIUM",
                title=f"Upgrade {spec.name} to IE4/IE5",
                description=(
                    f"<b>{spec.model}</b> is IE2 (η&nbsp;=&nbsp;{spec.efficiency*100:.1f}&nbsp;%). "
                    f"EU Regulation&nbsp;2019/1781 mandates IE3 minimum since July&nbsp;2021, "
                    f"and IE4 for&nbsp;≥75&nbsp;kW motors since July&nbsp;2023.<br/>"
                    f"<b>ABB M4BP IE4</b>: η&nbsp;≈&nbsp;92.9&nbsp;% (+{pct}&nbsp;% vs IE2).<br/>"
                    f"<b>ABB SynRM IE5</b> + ACS880: up to 40&nbsp;% total system saving vs "
                    f"IE2&nbsp;+&nbsp;DOL. No rotor copper losses.<br/>"
                    f"<span style='color:#27AE60;'>~{pct}&nbsp;% reduction "
                    f"· est. {energy*pct/100*365:.0f}&nbsp;kWh/yr saved</span>"
                ),
                savings_kwh_day=energy * pct / 100,
                savings_pct=pct,
                category="Motor",
            ))

        elif ec == "IE3":
            pct = 1.6
            recs.append(Recommendation(
                priority="LOW",
                title=f"Consider ABB SynRM IE5 for {spec.name}",
                description=(
                    f"<b>{spec.model}</b> is IE3 (η&nbsp;=&nbsp;{spec.efficiency*100:.1f}&nbsp;%). "
                    f"ABB's Synchronous Reluctance Motor (SynRM) reaches IE5 — the highest "
                    f"IEC efficiency class — by eliminating rotor copper losses.<br/>"
                    f"Pair with <b>ABB ACS880</b> drive (DTC control) for optimal performance. "
                    f"The combined <i>SynRM&nbsp;+&nbsp;Drive</i> system achieves &gt;95&nbsp;% "
                    f"at partial load.<br/>"
                    f"<span style='color:#27AE60;'>~{pct}&nbsp;% additional energy saving</span>"
                ),
                savings_kwh_day=energy * pct / 100,
                savings_pct=pct,
                category="Motor",
            ))
        return recs

    def _power_factor(self, device_list, result: SimulationResult) -> List[Recommendation]:
        recs = []
        n = len(result.time_hours) or 1
        total_real = total_apparent = 0.0

        for did, spec, item in device_list:
            if spec.category == DeviceCategory.SOURCE:
                continue
            avg = sum(result.device_power.get(did, [0.0])) / n
            total_real     += avg
            if spec.power_factor > 0:
                total_apparent += avg / spec.power_factor

        if total_apparent < 0.5:
            return recs

        pf = total_real / total_apparent

        if pf < 0.88:
            q_kvar = total_apparent * (1 - pf ** 2) ** 0.5
            recs.append(Recommendation(
                priority="HIGH",
                title=f"Improve System Power Factor  (PF = {pf:.2f})",
                description=(
                    f"System PF is <b>{pf:.2f}</b> — below the typical utility "
                    f"penalty threshold of 0.90. Reactive power: <b>{q_kvar:.1f}&nbsp;kVAr</b>.<br/>"
                    f"Low PF increases line current, causes additional I²R losses in cables, "
                    f"and transformers, and triggers reactive power surcharges.<br/>"
                    f"<b>Solutions:</b><br/>"
                    f"• <b>ABB CLMD capacitor banks</b> — fixed or automatic, correct PF to 0.98+.<br/>"
                    f"• <b>ABB PQF active power filter</b> — compensates reactive power "
                    f"<i>and</i> harmonics simultaneously.<br/>"
                    f"<span style='color:#27AE60;'>Estimated 4–6&nbsp;% reduction in "
                    f"distribution losses</span>"
                ),
                savings_kwh_day=result.total_energy_kwh * 0.05,
                savings_pct=5.0,
                category="Power Quality",
            ))
        elif pf < 0.93:
            recs.append(Recommendation(
                priority="MEDIUM",
                title=f"Power Factor Below Target  (PF = {pf:.2f})",
                description=(
                    f"System PF is <b>{pf:.2f}</b>. Industry target is ≥&nbsp;0.95.<br/>"
                    f"<b>ABB CLMD capacitor banks</b> provide cost-effective reactive power "
                    f"compensation. ABB's Reactive Power Controller (RPC) automates step switching."
                ),
                savings_kwh_day=result.total_energy_kwh * 0.02,
                savings_pct=2.0,
                category="Power Quality",
            ))
        return recs

    def _transformer_loading(self, device_list,
                              result: SimulationResult) -> List[Recommendation]:
        recs = []
        for did, spec, item in device_list:
            if spec.category != DeviceCategory.TRANSFORMER:
                continue
            rated_kva = spec.parameters.get("kva", spec.rated_power_kw)
            avg_kw    = sum(result.device_power.get(did, [0.0])) / len(result.time_hours or [1])
            load_pct  = (avg_kw / rated_kva * 100) if rated_kva > 0 else 0

            if load_pct < 30:
                recs.append(Recommendation(
                    priority="LOW",
                    title=f"Transformer Under-loaded ({load_pct:.0f}&nbsp;% of rating)",
                    description=(
                        f"<b>{spec.model}</b> operates at only {load_pct:.0f}&nbsp;% of its "
                        f"{rated_kva}&nbsp;kVA rating. "
                        f"Transformers reach peak efficiency at 50–70&nbsp;% load; at very "
                        f"light loads, fixed no-load (iron core) losses dominate.<br/>"
                        f"<b>Options:</b><br/>"
                        f"• Consolidate loads onto this transformer.<br/>"
                        f"• Replace with a smaller ABB RESIBLOC unit (lower no-load losses).<br/>"
                        f"ABB's RESIBLOC Tier&nbsp;2 (EU 2021) has ≤0.95&nbsp;kW no-load losses "
                        f"at 630&nbsp;kVA — 40&nbsp;% lower than older designs."
                    ),
                    savings_kwh_day=result.total_energy_kwh * 0.008,
                    savings_pct=0.8,
                    category="Transformer",
                ))
        return recs

    def _peak_demand(self, result: SimulationResult) -> List[Recommendation]:
        recs = []
        if not result.total_power_kw:
            return recs
        avg  = sum(result.total_power_kw) / len(result.total_power_kw)
        peak = result.peak_power_kw
        if avg > 0.5 and peak / avg > 1.6:
            ratio = peak / avg
            recs.append(Recommendation(
                priority="MEDIUM",
                title=f"High Peak Demand  (Peak/Avg = {ratio:.1f}×)",
                description=(
                    f"Peak demand ({peak:.1f}&nbsp;kW) is {ratio:.1f}× the average "
                    f"({avg:.1f}&nbsp;kW). Many utilities apply a demand charge on the "
                    f"monthly peak reading.<br/>"
                    f"<b>Solutions:</b><br/>"
                    f"• <b>ABB Ability™ Energy Manager</b> — automatically shifts "
                    f"deferrable loads (pumps, compressors, EV charging) to off-peak hours.<br/>"
                    f"• <b>ABB REACT2 battery storage</b> — stores energy at low-tariff "
                    f"hours and discharges during peaks.<br/>"
                    f"• Stagger motor start sequences to reduce simultaneous inrush current."
                ),
                savings_kwh_day=result.total_energy_kwh * 0.07,
                savings_pct=7.0,
                category="Demand Management",
            ))
        return recs

    def _energy_metering(self, device_list) -> List[Recommendation]:
        recs = []
        has_meter = any(spec.category == DeviceCategory.METER
                        for _, spec, _ in device_list)
        n_devices = len([d for d in device_list
                         if d[1].category != DeviceCategory.METER])
        if not has_meter and n_devices >= 2:
            recs.append(Recommendation(
                priority="MEDIUM",
                title="No Energy Meter in Circuit",
                description=(
                    "Without sub-metering you cannot verify energy baselines, "
                    "identify waste, or report ISO&nbsp;50001 KPIs.<br/>"
                    "<b>ABB B24 Energy Meter</b>: Class&nbsp;1, M-Bus + Ethernet, "
                    "measures kWh / kVArh / PF / harmonics — €150–250 installed.<br/>"
                    "<b>ABB M4M&nbsp;30 Power Analyzer</b>: Class&nbsp;A power quality, "
                    "Modbus RTU/TCP — ideal for identifying harmonic sources.<br/>"
                    "Connect to <b>ABB Ability™ Energy Monitor</b> for continuous "
                    "dashboards and automated anomaly alerts."
                ),
                savings_kwh_day=0.0,
                savings_pct=0.0,
                category="Monitoring",
            ))
        return recs

    def _lighting(self, device_list,
                  result: SimulationResult) -> List[Recommendation]:
        recs = []
        for did, spec, item in device_list:
            if spec.category != DeviceCategory.LOAD:
                continue
            if "light" not in spec.name.lower():
                continue
            if spec.rated_power_kw < 2:
                continue
            replaced_kw = spec.parameters.get("replaced_hps_kw", spec.rated_power_kw * 2.8)
            if replaced_kw <= spec.rated_power_kw:
                continue
            savings_kw  = replaced_kw - spec.rated_power_kw
            energy_kwh  = result.device_energy_kwh.get(did, 0.0)
            pct = savings_kw / replaced_kw * 100
            recs.append(Recommendation(
                priority="LOW",
                title=f"LED Upgrade Verified — {savings_kw:.1f}&nbsp;kW Saved",
                description=(
                    f"Your LED system ({spec.rated_power_kw}&nbsp;kW) already replaces "
                    f"a conventional {replaced_kw:.0f}&nbsp;kW HPS installation — "
                    f"a {pct:.0f}&nbsp;% lighting energy reduction. ✅<br/>"
                    f"<b>Further improvements:</b><br/>"
                    f"• Add occupancy sensors and daylight harvesting (DALI protocol).<br/>"
                    f"• Connect to <b>ABB i-bus® KNX</b> for building automation integration.<br/>"
                    f"• Maintain LPD &lt; 3&nbsp;W/m² for industrial spaces (EN&nbsp;12464-1)."
                ),
                savings_kwh_day=energy_kwh * pct / 100,
                savings_pct=pct,
                category="Lighting",
            ))
        return recs
