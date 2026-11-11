"""S6: analysis of alternatives with weight sensitivity.

A1  classic summed-probe gauge: one capacitance bridge per tank sums the probes (inferred
    density, no plane, calibrated in level attitude) - its accuracy is computed here;
A2  digital gauge computer, probes on dedicated measurement channels, plane fit + residual test
    + monitor lane, density from eps (this design) - accuracy and integrity from S4/S5;
A3  as A2 plus a densitometer in each tank;
A4  "smart" digital probes with their own electronics on a bus inside the tank, same algorithm
    as A3.
Scores 1-10 per criterion; accuracy and integrity are mapped from computed numbers, the rest are
judged (A) with the reason stated in DOSSIER §8.
"""

from __future__ import annotations

import json
import os

import numpy as np

from common import COLORS, RES, dump, plt, save
from fqsim import data, design, fuel, gauge, probe, tank

CRIT = ["accuracy", "integrity", "intrinsic safety", "mass + wiring", "dev + cert cost", "maintainability"]
W0 = np.array([0.25, 0.25, 0.15, 0.10, 0.15, 0.10])  # baseline weights (A)


def a1_accuracy(rng, n=3000):
    """Summed-probe gauge: usable mass ~ a0 + a1 * sum(C_i - C_dry_i), level calibration."""
    t = design.the_tank()
    probes = design.chosen_probes()
    fs = gauge.full_scale_mass(t)
    # calibrate at level with the nominal fuel at 15 C
    xs, ys = [], []
    for u in np.linspace(0.02, 1.0, 40):
        z = t.z_empty(0, 0) + u * (t.z_full(0, 0) - t.z_empty(0, 0))
        st = probe.TankState(z, 0.0, 0.0, fuel.NOMINAL, 15.0, 0.0)
        caps, _ = probe.measure(t, probes, st)
        xs.append(sum(c - p.c_dry for c, p in zip(caps, probes)) * 1e12)
        ys.append(probe.true_mass(t, st))
    a1, a0 = np.polyfit(xs, ys, 1)
    err = []
    for _ in range(n):
        f = fuel.random_fuel(rng)
        tx, ty = rng.uniform(*data.TILT_X_DEG), rng.uniform(*data.TILT_Y_DEG)
        sx, sy = tank.slopes(tx, ty)
        u = rng.uniform(0.02, 1.0)
        z = t.z_empty(sx, sy) + u * (t.z_full(sx, sy) - t.z_empty(sx, sy))
        st = probe.TankState(z, sx, sy, f, rng.uniform(data.FUEL_T_MIN, data.FUEL_T_MAX), rng.uniform(0, 10))
        caps, _ = probe.measure(t, probes, st, probe.draw_errors(rng, len(probes)))
        m = a0 + a1 * sum(c - p.c_dry for c, p in zip(caps, probes)) * 1e12
        err.append(100.0 * (m - probe.true_mass(t, st)) / fs)
    return float(np.percentile(np.abs(err), 95))


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    rng = np.random.default_rng(6)
    s4 = load("s4_budget.json")
    s5 = load("s5_fde.json")
    acc = {
        "A1": a1_accuracy(rng),
        "A2": s4["eps"]["p95_abs_pct_fs"],
        "A3": s4["densitometer"]["p95_abs_pct_fs"],
        "A4": s4["densitometer"]["p95_abs_pct_fs"],
    }
    # integrity: share of in-range probe bias events that end misleading, COM + MON (S5)
    mis = s5["summary"]["bias"]["misleading_after_mon"]
    integ_frac = {"A1": 1.0, "A2": mis, "A3": mis, "A4": mis}

    def acc_score(p95):
        return float(np.clip(10.0 - 3.0 * p95, 1.0, 10.0))

    def integ_score(frac):
        # A1 has no redundancy among its probes: any in-range fault is in the reading (score 2)
        return 2.0 if frac >= 1.0 else float(np.clip(10.0 - 400.0 * frac, 1.0, 10.0))

    S = {
        "A1": [acc_score(acc["A1"]), integ_score(integ_frac["A1"]), 9, 9, 8, 6],
        "A2": [acc_score(acc["A2"]), integ_score(integ_frac["A2"]), 9, 7, 6, 8],
        "A3": [acc_score(acc["A3"]), integ_score(integ_frac["A3"]), 8, 6, 5, 7],
        "A4": [acc_score(acc["A4"]), integ_score(integ_frac["A4"]), 4, 8, 3, 6],
    }
    names = list(S)
    M = np.array([S[k] for k in names], dtype=float)
    base = M @ W0
    # Monte Carlo over weights (Dirichlet around the baseline)
    Wmc = rng.dirichlet(W0 * 40.0, 20000)
    win = np.bincount(np.argmax(Wmc @ M.T, axis=1), minlength=len(names)) / len(Wmc)
    # one weight +/-10 % (renormalised): does the winner change?
    flips = []
    for i in range(len(W0)):
        for f in (0.9, 1.1):
            w = W0.copy()
            w[i] *= f
            w /= w.sum()
            if np.argmax(M @ w) != np.argmax(base):
                flips.append((CRIT[i], f))
    res = {
        "accuracy_p95_pct_fs": acc,
        "integrity_misleading_share": integ_frac,
        "scores": S,
        "weights": W0,
        "weighted": dict(zip(names, base)),
        "win_share": dict(zip(names, win)),
        "flips_10pct": flips,
    }
    print(res["weighted"], res["win_share"], flips, acc)

    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.2))
    axs[0].bar(names, base, color=[COLORS[i] for i in range(len(names))])
    for i, v in enumerate(base):
        axs[0].text(i, v + 0.05, "%.2f" % v, ha="center", fontsize=8)
    axs[0].set_ylabel("weighted score (baseline weights)")
    axs[0].set_ylim(0, 10)
    axs[0].set_title("baseline", fontsize=8)
    axs[1].bar(names, 100 * win, color=[COLORS[i] for i in range(len(names))])
    axs[1].set_ylabel("wins, % of 20 000 random weightings")
    axs[1].set_title("weight sensitivity", fontsize=8)
    fig.suptitle(
        "S6: A1 summed bridge / A2 digital, eps density / A3 + densitometer / A4 smart probes", fontsize=9
    )
    save(fig, "s6_aoa.png")
    dump("s6_aoa.json", res)


if __name__ == "__main__":
    main()
