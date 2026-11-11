"""Coaxial capacitance probes and the tank state they see.

A probe of active length L between z_bot and z_bot + L, wetted to height h, has [R11]

    C = C_dry + k * integral_0^h (eps(z) - 1) dz,     k = 2 pi eps0 / ln(r_o / r_i)

C_dry includes the end and stray capacitance.  Free water at the probe foot (eps 78.5 [R5])
or a short gives a capacitance far above the fuel range; an open connection gives about 0 F.
The fuel can be thermally stratified: eps and density then vary linearly with height (warm,
lighter fuel on top is the stable case, A).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import data
from .fuel import Fuel


@dataclass
class Probe:
    x: float
    y: float
    z_bot: float  # bottom of the active length (m, tank frame)
    length: float  # active length (m)
    k: float = data.PROBE_K  # F/m
    c_dry: float = 0.0  # F; set by make_probe

    @property
    def z_top(self):
        return self.z_bot + self.length


def make_probe(tank, x, y):
    zl = float(tank.lower(x, y)[0]) + data.DEAD_ZONE
    zu = float(tank.upper(x, y)[0]) - data.DEAD_ZONE
    length = zu - zl
    return Probe(
        x=float(x), y=float(y), z_bot=zl, length=length, c_dry=data.PROBE_C_END + data.PROBE_K * length
    )


@dataclass
class TankState:
    """Truth: fuel plane, fuel, bottom temperature and the top-to-bottom difference."""

    z_ref: float
    sx: float
    sy: float
    fuel: Fuel
    t_bottom: float = 15.0
    dT: float = 0.0  # K warmer at the top of the tank (over depth_ref)
    depth_ref: float = 0.42  # m, maximum tank depth: the gradient is dT / depth_ref


def eps_profile(tank, st):
    """eps at the tank bottom and its vertical gradient (1/m)."""
    z0 = float(np.min(tank.z_lo))
    e_b = float(st.fuel.eps(st.t_bottom))
    e_t = float(st.fuel.eps(st.t_bottom + st.dT))
    return z0, e_b, (e_t - e_b) / st.depth_ref


def probe_capacitance(tank, probe, st, water_mm=0.0):
    """True capacitance (F) of a probe in tank state st; water_mm of free water at its foot."""
    z_s = float(tank.plane(st.z_ref, st.sx, st.sy, probe.x, probe.y))
    h = min(max(z_s - probe.z_bot, 0.0), probe.length)
    z0, e_b, g = eps_profile(tank, st)
    # mean eps over [z_bot, z_bot + h] with a linear profile
    e_mean = e_b + g * (probe.z_bot + 0.5 * h - z0)
    c = probe.c_dry + probe.k * (e_mean - 1.0) * h
    if water_mm > 0.0:
        hw = min(water_mm * 1e-3, probe.length)
        c += probe.k * (data.WATER_EPS - e_mean) * hw
    return c


def compensator_capacitance(tank, st, length=data.COMP_LEN, k=data.PROBE_K):
    """Compensator at the tank bottom, always submerged: returns (C, C_dry, k*L)."""
    z0, e_b, g = eps_profile(tank, st)
    e_mean = e_b + g * 0.5 * length
    c_dry = data.PROBE_C_END + k * length
    return c_dry + k * length * (e_mean - 1.0), c_dry, k * length


def true_mass(tank, st):
    """Mass (kg) of the fuel below the plane with the stratified density."""
    z0 = float(np.min(tank.z_lo))
    rho_b = float(st.fuel.rho(st.t_bottom))
    drho = (float(st.fuel.rho(st.t_bottom + st.dT)) - rho_b) / st.depth_ref
    zs = tank.plane(st.z_ref, st.sx, st.sy)
    top = np.clip(zs, tank.z_lo, tank.z_up)
    h = top - tank.z_lo
    zmid = 0.5 * (top + tank.z_lo)
    m = np.sum((rho_b + drho * (zmid - z0)) * h * tank.dA) * tank.fill_frac
    return float(m)


def true_mean_rho(tank, st):
    v = float(tank.volume_below(st.z_ref, st.sx, st.sy))
    return true_mass(tank, st) / v if v > 0 else float(st.fuel.rho(st.t_bottom))


@dataclass
class Errors:
    """One draw of the measurement errors of a probe set (all in SI)."""

    off: np.ndarray
    gain: np.ndarray
    cal: np.ndarray
    dz: np.ndarray
    comp_off: float
    comp_gain: float


def draw_errors(rng, n, scale=1.0):
    e = data.ERR
    return Errors(
        off=rng.normal(0, e["c_offset"] * scale, n),
        gain=rng.normal(0, e["c_gain"] * scale, n),
        cal=rng.normal(0, e["c_dry_cal"] * scale, n),
        dz=rng.normal(0, e["z_install"] * scale, n),
        comp_off=float(rng.normal(0, e["c_offset"] * scale)),
        comp_gain=float(rng.normal(0, e["c_gain"] * scale)),
    )


def measure(tank, probes, st, err=None, water=None):
    """Measured probe capacitances (F) and compensator reading (F) for a state.
    err shifts each probe vertically by dz (installation) and adds front-end errors;
    the gauge uses the nominal position and the stored C_dry."""
    caps = np.empty(len(probes))
    for i, p in enumerate(probes):
        q = p
        if err is not None:
            q = Probe(p.x, p.y, p.z_bot + err.dz[i], p.length, p.k, p.c_dry + err.cal[i])
        c = probe_capacitance(tank, q, st, 0.0 if water is None else water[i])
        if err is not None:
            c = c * (1.0 + err.gain[i]) + err.off[i]
        caps[i] = c
    cc, _, _ = compensator_capacitance(tank, st)
    if err is not None:
        cc = cc * (1.0 + err.comp_gain) + err.comp_off
    return caps, cc
