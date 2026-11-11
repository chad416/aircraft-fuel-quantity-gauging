"""S1: what does the gauge know about the fuel's density?

A capacitance gauge measures volume (heights) once it knows eps from the compensator.  Mass needs
density.  Three ways: (a) a fixed design density; (b) density inferred from the measured eps via
Clausius-Mossotti with a stored specific polarisation r_nom; (c) a densitometer.  The error of (b)
is r / r_nom - 1: it depends only on how the fuel's composition differs from the nominal one.
"""

from __future__ import annotations

import numpy as np

from common import COLORS, dump, plt, save
from fqsim import data, fuel


def main():
    rng = np.random.default_rng(1)
    n = 20000
    r_c = fuel.compound_r()
    r_cls = fuel.R_CLASS
    fuels = [fuel.random_fuel(rng) for _ in range(n)]
    r = np.array([f.r for f in fuels])
    err_eps = r / fuel.R_NOM - 1.0  # density error of option (b)
    t = rng.uniform(data.FUEL_T_MIN, data.FUEL_T_MAX, n)
    rho_true = np.array([f.rho(tt) for f, tt in zip(fuels, t)])
    err_fixed = 800.0 / rho_true - 1.0
    err_dens = rng.normal(0, data.ERR["densitometer"], n)

    def pct(e, q):
        return float(np.percentile(np.abs(e), q))

    res = {
        "r_compound_m3_per_kg": r_c,
        "r_class": r_cls,
        "r_nom": fuel.R_NOM,
        "alpha_per_K": fuel.ALPHA,
        "alpha_by_compound": fuel.expansion_from_cm(),
        "eps_nominal_15C": float(fuel.NOMINAL.eps(15.0)),
        "eps_range": [
            float(min(f.eps(data.FUEL_T_MAX) for f in fuels)),
            float(max(f.eps(data.FUEL_T_MIN) for f in fuels)),
        ],
        "r_spread_pct": [100 * float(err_eps.min()), 100 * float(err_eps.max())],
        "density_error_pct": {
            "fixed_800": {"p95": 100 * pct(err_fixed, 95), "max": 100 * float(np.abs(err_fixed).max())},
            "eps_inferred": {"p95": 100 * pct(err_eps, 95), "max": 100 * float(np.abs(err_eps).max())},
            "densitometer": {"p95": 100 * pct(err_dens, 95), "max": 100 * float(np.abs(err_dens).max())},
        },
        "deps_dT_nominal": float((fuel.NOMINAL.eps(25.0) - fuel.NOMINAL.eps(5.0)) / 20.0),
    }
    print(res["density_error_pct"], "r spread %", res["r_spread_pct"], "alpha", fuel.ALPHA)

    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.2))
    names = list(r_c)
    cls_col = {"P": COLORS[0], "N1": COLORS[2], "N2": COLORS[3], "A": COLORS[1]}
    axs[0].barh(
        range(len(names)),
        [1e6 * r_c[k] for k in names],
        color=[cls_col[data.COMPOUNDS[k]["cls"]] for k in names],
    )
    axs[0].set_yticks(range(len(names)), names, fontsize=7)
    axs[0].axvline(1e6 * fuel.R_NOM, color="k", ls="--", lw=1, label="r_nom (mid kerosene)")
    axs[0].set_xlim(300, 375)
    axs[0].set_xlabel("specific polarisation r, 1e-6 m^3/kg")
    axs[0].set_title("pure compounds [R5],[R6]", fontsize=8)
    axs[0].legend(fontsize=7)
    axs[1].hist(100 * err_eps, bins=60, color=COLORS[0], alpha=0.85)
    axs[1].set_xlabel("density error of eps-inferred density, %")
    axs[1].set_ylabel("spec fuels (of %d)" % n)
    axs[1].set_title("blends within the composition ranges", fontsize=8)
    fig.suptitle("S1: Clausius-Mossotti specific polarisation and what composition does to it", fontsize=9)
    save(fig, "s1_polarisation.png")

    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    for e, lab, c in (
        (err_fixed, "fixed 800 kg/m^3", COLORS[1]),
        (err_eps, "inferred from eps (Clausius-Mossotti)", COLORS[0]),
        (err_dens, "densitometer (A: 0.15 %)", COLORS[2]),
    ):
        s = np.sort(np.abs(100 * e))
        ax.plot(s, np.linspace(0, 100, len(s)), label=lab, color=c)
    ax.axvline(100 * data.REQ_ACC_FS, color="k", ls=":", lw=1)
    ax.text(100 * data.REQ_ACC_FS + 0.05, 30, "whole +/-2 % FS budget", fontsize=7)
    ax.set_xlabel("|density error|, %")
    ax.set_ylabel("cumulative share of fuels and temperatures, %")
    ax.set_xlim(0, 6)
    ax.set_title("S1: density error of three options (-40..+50 C, spec fuels)", fontsize=8)
    ax.legend(fontsize=7, loc="lower right")
    save(fig, "s1_density_options.png")
    dump("s1_fuel.json", res)


if __name__ == "__main__":
    main()
