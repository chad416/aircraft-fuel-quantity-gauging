"""S4: Monte Carlo error budget of the chosen design (all probes healthy).

Each sample draws a spec fuel (composition and density), a bottom fuel temperature, a thermal
stratification, surface tilts inside the gauging envelope, a fill per tank, and one set of
measurement errors per tank (front end, stored C_dry, installation height, compensator).  Both
wing tanks are gauged (the left one sees the mirrored lateral tilt); the error is the indicated
total usable mass minus the true usable mass, in % of the full-scale total.  A one-at-a-time run
gives each source's share.  The healthy residuals also set the residual test's sigma (SIGMA_Z).
"""

from __future__ import annotations

import numpy as np

from common import COLORS, dump, plt, save
from fqsim import data, design, fuel, gauge, probe, tank

SOURCES = ("electronics", "c_dry_cal", "install", "compensator", "stratification", "composition")


def one_sample(rng, t, cfgs, probes, active, rho_mode="eps", sigma_stats=None):
    f = (
        fuel.random_fuel(rng)
        if "composition" in active
        else fuel.Fuel(r=fuel.R_NOM, rho15=rng.uniform(775, 840))
    )
    tb = rng.uniform(data.FUEL_T_MIN, data.FUEL_T_MAX)
    dT = rng.uniform(0, data.ERR["strat_dT_max"]) if "stratification" in active else 0.0
    tx = rng.uniform(*data.TILT_X_DEG)
    ty = rng.uniform(*data.TILT_Y_DEG)
    ind = true = 0.0
    for side, cfg in enumerate(cfgs):
        mirror = side == 1
        sx, sy = tank.slopes(tx, -ty if mirror else ty)
        u = rng.uniform(0.02, 1.0)
        z = t.z_empty(sx, sy) + u * (t.z_full(sx, sy) - t.z_empty(sx, sy))
        st = probe.TankState(z, sx, sy, f, tb, dT)
        n = len(probes)
        e = probe.draw_errors(rng, n)
        if "electronics" not in active:
            e.off[:] = 0
            e.gain[:] = 0
        if "c_dry_cal" not in active:
            e.cal[:] = 0
        if "install" not in active:
            e.dz[:] = 0
        if "compensator" not in active:
            e.comp_off = 0.0
            e.comp_gain = 0.0
        caps, cc = probe.measure(t, probes, st, e)
        rho_meas = None
        if rho_mode == "densitometer":
            rho_meas = probe.true_mean_rho(t, st) * (1 + rng.normal(0, data.ERR["densitometer"]))
        sf = (-np.tan(np.radians(tx)), (np.tan(np.radians(ty))) * -1.0, 1.0)
        r = gauge.solve(cfg, caps * 1e12, cc * 1e12, sf=sf, rho_meas=rho_meas)
        if sigma_stats is not None:
            h, cl = gauge.classify(cfg, caps * 1e12, r.eps)
            live = [i for i in range(n) if cl[i] == gauge.CL_LIVE]
            if len(live) >= 4:
                p = gauge.fit_plane(cfg, np.array(live), cfg.zbot[live] + h[live], gauge.weights(h[live]))
                if p is not None:
                    sigma_stats.append(p[3] / gauge.CHI2[len(live) - 4])
        v_true = t.volume_below(z, sx, sy)
        m_true = probe.true_mass(t, st) * max(0.0, v_true - t.v_unusable) / v_true if v_true > 0 else 0.0
        ind += r.mass if r.status != gauge.ST_INVALID else np.nan
        true += m_true
    return ind - true, u


def main():
    rng = np.random.default_rng(4)
    t = design.the_tank()
    probes = design.chosen_probes()
    cfgs = [design.cfg_for(mirror=False), design.cfg_for(mirror=True)]
    fs = 2 * gauge.full_scale_mass(t)
    n = 6000
    res = {"full_scale_total_kg": fs, "n": n}
    sig = []
    errs = {}
    fills = None
    for mode in ("eps", "densitometer"):
        e = np.empty(n)
        fl = np.empty(n)
        for k in range(n):
            e[k], fl[k] = one_sample(rng, t, cfgs, probes, set(SOURCES), mode, sig if mode == "eps" else None)
        errs[mode] = 100.0 * e / fs
        fills = fl
        ok = np.isfinite(errs[mode])
        res[mode] = {
            "invalid_share": float(1 - ok.mean()),
            "p95_abs_pct_fs": float(np.percentile(np.abs(errs[mode][ok]), 95)),
            "max_abs_pct_fs": float(np.abs(errs[mode][ok]).max()),
            "mean_pct_fs": float(errs[mode][ok].mean()),
        }
        print(mode, res[mode])
    sig = np.array(sig)
    # sig holds chi2 / threshold of every healthy residual test: > 1 would be a false alarm
    res["residual_tests"] = int(len(sig))
    res["chi2_over_threshold_max"] = float(sig.max())
    res["chi2_over_threshold_p99"] = float(np.percentile(sig, 99))
    res["false_alarms"] = int(np.sum(sig > 1.0))
    res["sigma_z_mm"] = 1000 * gauge.SIGMA_Z
    res["kappa_pct"] = 100 * gauge.KAPPA
    print("residual tests %d, false alarms %d, max chi2/T %.3f" % (len(sig), res["false_alarms"], sig.max()))

    # one source at a time
    share = {}
    m = 1500
    for s in SOURCES + ("none",):
        e = np.array([one_sample(rng, t, cfgs, probes, {s})[0] for _ in range(m)])
        e = 100.0 * e[np.isfinite(e)] / fs
        share[s] = float(np.percentile(np.abs(e), 95))
    res["p95_one_source_pct_fs"] = share
    print(share)

    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.3))
    bins = np.linspace(0.02, 1.0, 8)
    mids = 0.5 * (bins[1:] + bins[:-1])
    for mode, c, lab in (("eps", COLORS[0], "density from eps"), ("densitometer", COLORS[2], "densitometer")):
        p95 = []
        for a, b in zip(bins[:-1], bins[1:]):
            sel = (fills >= a) & (fills < b) & np.isfinite(errs[mode])
            p95.append(np.percentile(np.abs(errs[mode][sel]), 95))
        axs[0].plot(100 * mids, p95, "o-", color=c, label=lab)
    axs[0].axhline(100 * data.REQ_ACC_FS, color="k", ls=":", lw=1)
    axs[0].set_xlabel("tank fill (u), %")
    axs[0].set_ylabel("95th percentile |error|, % FS total")
    axs[0].set_title("total usable mass error, all probes healthy", fontsize=8)
    axs[0].legend(fontsize=7)
    axs[0].set_ylim(0, 2.2)
    names = list(share)
    axs[1].barh(range(len(names)), [share[k] for k in names], color=COLORS[0])
    axs[1].set_yticks(range(len(names)), names, fontsize=7)
    axs[1].set_xlabel("95th percentile |error|, % FS (one source)")
    axs[1].set_title("which source costs what", fontsize=8)
    fig.suptitle("S4: Monte Carlo error budget (%d samples per option)" % n, fontsize=9)
    save(fig, "s4_budget.png")
    dump("s4_budget.json", res)


if __name__ == "__main__":
    main()
