"""S5: one wrong probe - is it caught, and what does the pilot see if it is not?

Faults injected into one probe of the chosen layout, in random healthy states of the envelope
(measurement errors as in S4):
- open circuit, short, free water at the probe foot: range checks;
- in-range height bias (contamination film, partial short, connector leakage) and gain drift:
  only the residual test (COM) and the monitor lane (MON) can see them.
The outcome of each event is: excluded (the right probe), detected but not isolated (tank
invalid), or undetected; an undetected event is misleading when its error exceeds 5 % of the
tank's full scale.  MON's alarm limit is set from the healthy COM-MON spread.
"""

from __future__ import annotations

import numpy as np

from common import COLORS, dump, plt, save
from fqsim import data, design, fuel, gauge, probe


def healthy_state(rng, t):
    f = fuel.random_fuel(rng)
    tx = rng.uniform(*data.TILT_X_DEG)
    ty = rng.uniform(*data.TILT_Y_DEG)
    sx, sy = np.tan(np.radians(tx)), np.tan(np.radians(ty))
    u = rng.uniform(0.08, 0.97)
    z = t.z_empty(sx, sy) + u * (t.z_full(sx, sy) - t.z_empty(sx, sy))
    st = probe.TankState(z, sx, sy, f, rng.uniform(data.FUEL_T_MIN, data.FUEL_T_MAX), rng.uniform(0, 10))
    return st, (-sx, -sy, 1.0)


def run(rng, t, cfg, probes, kind, size):
    st, sf = healthy_state(rng, t)
    e = probe.draw_errors(rng, len(probes))
    caps, cc = probe.measure(t, probes, st, e)
    caps = caps * 1e12
    cc *= 1e12
    h, cl = gauge.classify(cfg, caps, gauge.comp_eps(cfg, cc) or gauge.EPS_DEFAULT)
    live = [i for i in range(len(probes)) if cl[i] == gauge.CL_LIVE]
    if not live:
        return None
    j = int(rng.choice(live))
    eps = gauge.comp_eps(cfg, cc) or gauge.EPS_DEFAULT
    kk = cfg.k_pf[j] * (eps - 1.0)
    if kind == "open":
        caps[j] = 0.3
    elif kind == "short":
        caps[j] = 5000.0
    elif kind == "water":
        caps[j] += cfg.k_pf[j] * (data.WATER_EPS - eps) * size
    elif kind == "bias":
        caps[j] += kk * size
    elif kind == "gain":
        caps[j] = cfg.cdry_pf[j] + (caps[j] - cfg.cdry_pf[j]) * (1.0 + size)
    r = gauge.solve(cfg, caps, cc, sf=sf)
    fs = gauge.full_scale_mass(t)
    v_true = t.volume_below(st.z_ref, st.sx, st.sy)
    m_true = probe.true_mass(t, st) * max(0.0, v_true - t.v_unusable) / v_true
    mon_v = gauge.monitor(cfg, caps, r.eps, sf)
    out = {"n_live": len(live), "probe": j, "status": r.status, "excluded": r.excluded}
    if r.status == gauge.ST_INVALID:
        out["outcome"] = "detected"
        out["err"] = 0.0
        out["mon_gap"] = 0.0
        return out
    out["err"] = 100.0 * (r.mass - m_true) / fs
    out["mon_gap"] = 100.0 * abs(r.mass - (mon_v * r.rho if mon_v is not None else r.mass)) / fs
    rng_fault = r.cls[j] in (gauge.CL_OPEN, gauge.CL_SHORT)
    if rng_fault:
        out["outcome"] = "range"
    elif r.excluded == j:
        out["outcome"] = "excluded"
    elif r.excluded >= 0:
        out["outcome"] = "wrong_exclusion"
    else:
        out["outcome"] = "undetected"
    return out


def main():
    rng = np.random.default_rng(5)
    t = design.the_tank()
    probes = design.chosen_probes()
    cfg = design.cfg_for()

    # healthy COM-MON spread -> MON alarm limit
    gaps = []
    for _ in range(3000):
        st, sf = healthy_state(rng, t)
        caps, cc = probe.measure(t, probes, st, probe.draw_errors(rng, len(probes)))
        r = gauge.solve(cfg, caps * 1e12, cc * 1e12, sf=sf)
        mv = gauge.monitor(cfg, caps * 1e12, r.eps, sf)
        if r.status != gauge.ST_INVALID and mv is not None:
            gaps.append(100.0 * abs(r.usable - mv) / (t.v_full - t.v_unusable))
    gaps = np.array(gaps)
    mon_tol = float(np.ceil(1.5 * np.percentile(gaps, 99.9) * 2) / 2)  # rounded up to 0.5 % FS
    print(
        "healthy COM-MON gap p99.9 %.2f %% FS -> MON limit %.1f %% FS" % (np.percentile(gaps, 99.9), mon_tol)
    )

    res = {"mon_gap_p999_pct_fs": float(np.percentile(gaps, 99.9)), "mon_tol_pct_fs": mon_tol}
    kinds = {
        "open": [None] * 300,
        "short": [None] * 300,
        "water": list(rng.uniform(0.0005, 0.04, 600)),
        "bias": list(rng.choice([-1, 1], 3000) * rng.uniform(0.002, 0.08, 3000)),
        "gain": list(rng.choice([-1, 1], 1500) * rng.uniform(0.02, 0.4, 1500)),
    }
    events = []
    for kind, sizes in kinds.items():
        for s in sizes:
            o = run(rng, t, cfg, probes, kind, s)
            if o is not None:
                o["kind"] = kind
                o["size"] = 0.0 if s is None else float(s)
                events.append(o)
    summary = {}
    for kind in kinds:
        ev = [e for e in events if e["kind"] == kind]
        n = len(ev)
        cnt = {
            k: sum(1 for e in ev if e["outcome"] == k) / n
            for k in ("range", "excluded", "detected", "undetected", "wrong_exclusion")
        }
        mis = [
            e
            for e in ev
            if e["outcome"] in ("undetected", "wrong_exclusion") and abs(e["err"]) > 100 * data.REQ_MISLEAD_FS
        ]
        mis_mon = [e for e in mis if e["mon_gap"] <= mon_tol]
        post = [abs(e["err"]) for e in ev if e["outcome"] == "excluded"]
        summary[kind] = {
            "n": n,
            **cnt,
            "misleading_com_only": len(mis) / n,
            "misleading_after_mon": len(mis_mon) / n,
            "post_exclusion_p95_pct_fs": float(np.percentile(post, 95)) if post else None,
        }
        print(kind, summary[kind])
    res["summary"] = summary
    # where do the misleading events come from? by the number of LIVE probes at the event
    by = {}
    for lab, lo, hi in (("<=3 LIVE", 0, 3), ("4 LIVE", 4, 4), (">=5 LIVE", 5, 99)):
        ev = [e for e in events if e["kind"] in ("bias", "gain") and lo <= e["n_live"] <= hi]
        mis = [
            e
            for e in ev
            if e["outcome"] in ("undetected", "wrong_exclusion")
            and abs(e["err"]) > 100 * data.REQ_MISLEAD_FS
            and e["mon_gap"] <= mon_tol
        ]
        by[lab] = {"n": len(ev), "misleading_after_mon": len(mis) / max(1, len(ev))}
    res["misleading_by_live"] = by
    print(by)

    # detection probability vs bias size, by LIVE count
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.3))
    ev = [e for e in events if e["kind"] == "bias"]
    edges = np.array([0, 4, 8, 12, 16, 20, 30, 40, 60, 80]) * 1e-3
    for k, nl in enumerate((4, 5, 6, 7)):
        sel = [e for e in ev if e["n_live"] == nl]
        if len(sel) < 20:
            continue
        pd = []
        for a, b in zip(edges[:-1], edges[1:]):
            s = [e for e in sel if a <= abs(e["size"]) < b]
            pd.append(np.mean([e["outcome"] in ("excluded", "detected") for e in s]) if s else np.nan)
        axs[0].plot(
            1000 * 0.5 * (edges[1:] + edges[:-1]),
            100 * np.array(pd),
            "o-",
            color=COLORS[k],
            label="%d LIVE" % nl,
        )
    axs[0].set_xlabel("in-range height bias on one probe, mm")
    axs[0].set_ylabel("detected or excluded, %")
    axs[0].set_title("residual test (P_fa 1e-5, sigma %.1f mm)" % (1000 * gauge.SIGMA_Z), fontsize=8)
    axs[0].legend(fontsize=7)
    und = [e for e in ev if e["outcome"] in ("undetected", "wrong_exclusion")]
    axs[1].scatter(
        [1000 * abs(e["size"]) for e in und],
        [abs(e["err"]) for e in und],
        s=6,
        color=COLORS[0],
        label="undetected by COM",
    )
    caught = [e for e in und if e["mon_gap"] > mon_tol]
    axs[1].scatter(
        [1000 * abs(e["size"]) for e in caught],
        [abs(e["err"]) for e in caught],
        s=10,
        facecolors="none",
        edgecolors=COLORS[1],
        label="... caught by MON",
    )
    axs[1].axhline(100 * data.REQ_MISLEAD_FS, color="k", ls=":", lw=1)
    axs[1].text(2, 100 * data.REQ_MISLEAD_FS + 0.2, "misleading (5 % FS)", fontsize=7)
    axs[1].set_xlabel("bias, mm")
    axs[1].set_ylabel("|tank mass error|, % FS")
    axs[1].set_title("what is left when COM does not see it", fontsize=8)
    axs[1].legend(fontsize=7)
    fig.suptitle("S5: fault detection and exclusion on one wrong probe", fontsize=9)
    save(fig, "s5_fde.png")
    dump("s5_fde.json", res)


if __name__ == "__main__":
    main()
