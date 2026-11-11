"""Fuel dielectric and density model.

Clausius-Mossotti (Lorentz-Lorenz) for a non-polar liquid [R8]:

    (eps - 1) / (eps + 2) = r * rho

r is the specific polarisation (m^3/kg).  It is a property of the molecules, so for an ideal
mixture it is additive by mass fraction: r_mix = sum(w_i * r_i) [R8].  A capacitance gauge that
measures eps in the tank (compensator) can infer the density as rho = CM(eps) / r_nom; the
density error is then r / r_nom - 1, set by how far the fuel's composition is from the one r_nom
was taken for.  This module derives r for the hydrocarbon classes of kerosene from pure-compound
permittivities [R5] and densities [R6].
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import data


def cm(eps):
    """Clausius-Mossotti function (eps-1)/(eps+2)."""
    return (eps - 1.0) / (eps + 2.0)


def eps_from_cm(c):
    return (1.0 + 2.0 * c) / (1.0 - c)


def compound_r():
    """Specific polarisation of each compound at its density temperature, m^3/kg (D)."""
    out = {}
    for name, c in data.COMPOUNDS.items():
        eps = c["eps"] - c["a"] * 1e-2 * (c["t_rho"] - c["t_eps"])
        out[name] = cm(eps) / (c["rho"] * 1000.0)
    return out


def class_r():
    """Mean specific polarisation per hydrocarbon class (D)."""
    r = compound_r()
    cls = {}
    for name, c in data.COMPOUNDS.items():
        cls.setdefault(c["cls"], []).append(r[name])
    return {k: float(np.mean(v)) for k, v in cls.items()}


def expansion_from_cm():
    """Volumetric thermal expansion alpha (1/K) of the n-paraffins, derived from the
    temperature dependence of eps [R5] through Clausius-Mossotti at constant r (D)."""
    out = {}
    for name, (eps2, t2) in data.EPS_T2.items():
        c = data.COMPOUNDS[name]
        c1, c2 = cm(c["eps"]), cm(eps2)
        # rho ~ CM at constant r; alpha = -dln(rho)/dT
        out[name] = -np.log(c2 / c1) / (t2 - c["t_eps"])
    return out


ALPHA = float(np.mean(list(expansion_from_cm().values())))  # 1/K (D)
R_CLASS = class_r()


def blend_r(w_p, w_n1, w_n2, w_a):
    return w_p * R_CLASS["P"] + w_n1 * R_CLASS["N1"] + w_n2 * R_CLASS["N2"] + w_a * R_CLASS["A"]


def nominal_r():
    """r of the mid-range composition: the value the gauge stores (D)."""
    a = np.mean(data.COMP_AROM)
    n = np.mean(data.COMP_NAPH)
    s2 = np.mean(data.COMP_N2_SHARE)
    return float(blend_r(1.0 - a - n, n * (1.0 - s2), n * s2, a))


R_NOM = nominal_r()


@dataclass
class Fuel:
    r: float  # m^3/kg
    rho15: float  # kg/m^3 at 15 C
    alpha: float = ALPHA

    def rho(self, t_c):
        return self.rho15 * (1.0 - self.alpha * (np.asarray(t_c, dtype=float) - 15.0))

    def eps(self, t_c):
        return eps_from_cm(self.r * self.rho(t_c))


def random_fuel(rng):
    """A spec-compliant kerosene: composition within the ranges of data.COMP_*, density at
    15 C uniform over the specification (A)."""
    a = rng.uniform(*data.COMP_AROM)
    n = rng.uniform(*data.COMP_NAPH)
    s2 = rng.uniform(*data.COMP_N2_SHARE)
    r = blend_r(1.0 - a - n, n * (1.0 - s2), n * s2, a)
    return Fuel(r=float(r), rho15=float(rng.uniform(data.RHO15_MIN, data.RHO15_MAX)))


NOMINAL = Fuel(r=R_NOM, rho15=0.5 * (data.RHO15_MIN + data.RHO15_MAX))


def rho_from_eps(eps, r=None):
    """Density the gauge infers from a measured permittivity (kg/m^3)."""
    return cm(eps) / (R_NOM if r is None else r)
