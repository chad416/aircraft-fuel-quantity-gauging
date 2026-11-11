"""S3: how many probes, and where?

For every candidate site and every state of the envelope grid (surface tilts x fill) the probe
is LIVE when the fuel surface crosses its active length.  A layout observes the fuel plane by
itself when >= 3 LIVE probes are not collinear; it can detect one wrong probe with >= 4 and
exclude it with >= 5 (every leave-one-out subset must still fix the plane).  A greedy search
with one-swap refinement picks the layout for each probe count.
"""

from __future__ import annotations

import itertools

import numpy as np

from common import COLORS, dump, plt, save
from fqsim import design, gauge

H = gauge.H_SAT


def live_matrix():
    cands = design.candidates()
    states = design.envelope_states()
    t = design.the_tank()
    L = np.zeros((len(cands), len(states)), dtype=bool)
    for j, (_, _, _, z, sx, sy) in enumerate(states):
        for i, p in enumerate(cands):
            zs = z + sx * (p.x - t.xr) + sy * (p.y - t.yr)
            L[i, j] = p.z_bot + H < zs < p.z_top - H
    return L


def _det(n, sx, sy, sxx, syy, sxy):
    """Determinant of the centred position covariance for sums over a probe set."""
    with np.errstate(invalid="ignore", divide="ignore"):
        mx, my = sx / n, sy / n
        d = (sxx / n - mx * mx) * (syy / n - my * my) - (sxy / n - mx * my) ** 2
    return np.where(n >= 3, d, 0.0)


def geom_ok(pts):
    if len(pts) < 3:
        return False
    a = np.array(pts)
    d = a - a.mean(axis=0)
    cxx, cyy, cxy = (d[:, 0] ** 2).mean(), (d[:, 1] ** 2).mean(), (d[:, 0] * d[:, 1]).mean()
    return cxx * cyy - cxy * cxy >= gauge.DET_MIN


def coverage(layout, L, mask=None):
    """Shares of states where the plane is observable / a fault detectable / excludable."""
    cands = design.candidates()
    x = np.array([cands[i].x for i in layout])[:, None]
    y = np.array([cands[i].y for i in layout])[:, None]
    M = L[list(layout)].astype(float)
    tot = [
        M.sum(0),
        (M * x).sum(0),
        (M * y).sum(0),
        (M * x * x).sum(0),
        (M * y * y).sum(0),
        (M * x * y).sum(0),
    ]
    n = tot[0]
    ok3 = _det(*tot) >= gauge.DET_MIN
    ok5 = ok3 & (n >= 5)
    for k in range(len(layout)):
        m = M[k]
        sub = [
            tot[0] - m,
            tot[1] - m * x[k],
            tot[2] - m * y[k],
            tot[3] - m * x[k] ** 2,
            tot[4] - m * y[k] ** 2,
            tot[5] - m * x[k] * y[k],
        ]
        ok5 &= (m == 0) | (_det(*sub) >= gauge.DET_MIN)
    sel = np.ones(L.shape[1], dtype=bool) if mask is None else mask
    c3 = float(ok3[sel].mean())
    c4 = float((ok3 & (n >= 4))[sel].mean())
    c5 = float(ok5[sel].mean())
    return c3, c4, c5, n.astype(int)


def score(layout, L, mask):
    c3, c4, c5, _ = coverage(layout, L, mask)
    return c3 + c4 + c5


def search(n_max, L, mask):
    best = {}
    layout = []
    ncand = L.shape[0]
    for n in range(1, n_max + 1):
        cand = [(score(layout + [i], L, mask), i) for i in range(ncand) if i not in layout]
        layout = layout + [max(cand)[1]]
        # one-swap refinement
        improved = True
        while improved:
            improved = False
            s0 = score(layout, L, mask)
            for k, i in itertools.product(range(len(layout)), range(ncand)):
                if i in layout:
                    continue
                trial = layout[:k] + [i] + layout[k + 1 :]
                s = score(trial, L, mask)
                if s > s0 + 1e-12:
                    layout, s0, improved = trial, s, True
        best[n] = list(layout)
    return best


def main():
    L = live_matrix()
    states = design.envelope_states()
    fills = np.array([s[2] for s in states])
    mask = fills >= 0.06
    best = search(9, L, mask)
    rows = []
    for n, lay in best.items():
        c3, c4, c5, _ = coverage(lay, L, mask)
        lo = coverage(lay, L, (fills >= 0.06) & (fills <= 0.15))
        rows.append({"n": n, "layout": lay, "observe": c3, "detect": c4, "exclude": c5, "low_detect": lo[1]})
        print(
            "N=%d  observe %.3f  detect %.3f  exclude %.3f  (6-15 %% fill: detect %.3f)  %s"
            % (n, c3, c4, c5, lo[1], lay)
        )
    chosen = list(design.CHOSEN)
    c3, c4, c5, nlive = coverage(chosen, L, mask)
    print("chosen", chosen, c3, c4, c5)

    # figure 1: coverage against probe count
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    ns = [r["n"] for r in rows]
    ax.plot(ns, [100 * r["observe"] for r in rows], "o-", label="plane observable (>= 3 LIVE, not collinear)")
    ax.plot(ns, [100 * r["detect"] for r in rows], "s-", label="one wrong probe detectable (>= 4)")
    ax.plot(ns, [100 * r["exclude"] for r in rows], "^-", label="one wrong probe excludable (>= 5)")
    ax.axvline(len(chosen), color="0.5", ls=":", lw=1)
    ax.set_xlabel("probes per tank (best layout for each count)")
    ax.set_ylabel("share of envelope states, %")
    ax.set_title("S3: what the probe count buys (fill 6-97 %, tilts -5..12 / -5..5 deg)")
    ax.legend(fontsize=7, loc="lower right")
    ax.set_ylim(0, 102)
    save(fig, "s3_coverage.png")

    # figure 2: planform with candidates and the chosen layout
    t = design.the_tank()
    cands = design.candidates()
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    cs = ax.contourf(t.y, t.x, t.depth * 1000, levels=12, cmap="Blues")
    fig.colorbar(cs, ax=ax, label="tank depth, mm")
    ax.plot([p.y for p in cands], [p.x for p in cands], "x", color="0.4", ms=5, label="candidate sites")
    for k, i in enumerate(chosen):
        ax.plot(cands[i].y, cands[i].x, "o", color=COLORS[1], ms=8)
        ax.annotate(
            "P%d" % (k + 1), (cands[i].y, cands[i].x), xytext=(5, 4), textcoords="offset points", fontsize=8
        )
    ax.plot([], [], "o", color=COLORS[1], label="chosen layout")
    ax.set_xlabel("y outboard, m")
    ax.set_ylabel("x aft, m")
    ax.invert_yaxis()
    ax.set_title("S3: wing-tank planform, candidate sites and the %d-probe layout" % len(chosen))
    ax.legend(fontsize=7, loc="lower left")
    save(fig, "s3_layout.png")

    # figure 3: LIVE count over fill and longitudinal tilt (lateral 0 and +5 deg)
    nlive_all = coverage(chosen, L, None)[3]
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, ty in zip(axs, (0.0, 5.0)):
        grid = np.zeros((len(design.FILLS), len(design.TX)))
        for j, s in enumerate(states):
            if s[1] == ty:
                grid[design.FILLS.index(s[2]), design.TX.index(s[0])] = nlive_all[j]
        im = ax.imshow(grid, origin="lower", aspect="auto", cmap="viridis", vmin=0, vmax=len(chosen))
        ax.set_xticks(range(len(design.TX)), [str(int(v)) for v in design.TX])
        ax.set_yticks(range(len(design.FILLS)), ["%d" % (100 * f) for f in design.FILLS], fontsize=6)
        ax.set_xlabel("longitudinal tilt, deg")
        ax.set_title("lateral tilt %+.0f deg" % ty, fontsize=8)
        for a in range(grid.shape[0]):
            for b in range(grid.shape[1]):
                ax.text(b, a, int(grid[a, b]), ha="center", va="center", fontsize=6, color="w")
    axs[0].set_ylabel("fill, % of full volume")
    fig.colorbar(im, ax=axs, label="LIVE probes")
    fig.suptitle("S3: LIVE probes of the chosen layout over the envelope", fontsize=9)
    save(fig, "s3_live_map.png")

    dump(
        "s3_placement.json",
        {
            "rows": rows,
            "chosen": chosen,
            "chosen_cov": {"observe": c3, "detect": c4, "exclude": c5},
            "sites_xy": [(cands[i].x, cands[i].y, cands[i].z_bot, cands[i].length) for i in chosen],
            "n_states": int(mask.sum()),
        },
    )


if __name__ == "__main__":
    main()
