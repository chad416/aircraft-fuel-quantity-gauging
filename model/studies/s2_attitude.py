"""S2: the fuel surface follows the specific force, not the attitude.

The free surface is normal to the specific force (gravity reaction plus acceleration).  In a
coordinated turn the specific force stays on the aircraft's z axis, so the surface stays
parallel to the wing whatever the bank angle; on the take-off roll the forward acceleration tilts
it aft by far more than the pitch attitude.  Three ways to place the surface are compared on the
same probe readings: (1) assume level; (2) tilt it by the attitude (pitch, roll) from an AHRS;
(3) fit it to the probes (this design) or take it from the measured specific force (fallback).
"""

from __future__ import annotations

import math

import numpy as np

from common import COLORS, dump, plt, save
from fqsim import data, design, gauge, tank


def surface_heights(t, probes, z, sx, sy):
    return [z + sx * (p.x - t.xr) + sy * (p.y - t.yr) for p in probes]


def volume_from(t, probes, zs, sx, sy):
    """Volume with assumed slopes, height from the mean of the probes that see the surface."""
    off = []
    for p, z in zip(probes, zs):
        if p.z_bot < z < p.z_top:
            off.append(z - sx * (p.x - t.xr) - sy * (p.y - t.yr))
    if not off:
        return float("nan")
    return float(t.volume_below(np.mean(off), sx, sy))


def main():
    t = design.the_tank()
    probes = design.chosen_probes()
    fs_v = t.v_full - t.v_unusable
    fills = np.linspace(0.1, 0.9, 17)
    cases = {
        "climb, pitch 8 deg, assumed level": (8.0, 0.0, 0.0, 0.0),
        "coordinated turn 25 deg bank, AHRS roll used": (2.0, 0.0, 2.0, 25.0),
        "coordinated turn 25 deg bank, assumed level": (2.0, 0.0, 0.0, 0.0),
        "sideslip n_y = 0.08 g, assumed level": (2.0, math.degrees(math.atan(0.08)), 0.0, 0.0),
    }
    out = {}
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.2))
    for k, (name, (tx, ty, ax_tilt, ay_tilt)) in enumerate(cases.items()):
        sx, sy = tank.slopes(tx, ty)
        ax_s, ay_s = tank.slopes(ax_tilt, ay_tilt)
        err = []
        for f in fills:
            z = t.z_for_volume(f * t.v_full, sx, sy)
            zs = surface_heights(t, probes, z, sx, sy)
            v = volume_from(t, probes, zs, ax_s, ay_s)
            err.append(100.0 * (v - f * t.v_full) / fs_v)
        out[name] = {"fills": fills, "err_pct_fs": np.array(err), "max_abs": float(np.nanmax(np.abs(err)))}
        axs[0].plot(100 * fills, err, color=COLORS[k], label=name)
    # this design: plane fit on the same readings (noise free), worst over the envelope grid
    cfg = design.cfg_for()
    worst = 0.0
    for tx, ty, f, z, sx, sy in design.envelope_states():
        if f < 0.1:
            continue
        caps = []
        for p in probes:
            zs = z + sx * (p.x - t.xr) + sy * (p.y - t.yr)
            h = min(max(zs - p.z_bot, 0.0), p.length)
            caps.append(p.c_dry * 1e12 + p.k * 1e12 * (gauge.EPS_DEFAULT - 1.0) * h)
        cc = cfg.comp_cdry_pf + cfg.comp_kl_pf * (gauge.EPS_DEFAULT - 1.0)
        r = gauge.solve(cfg, caps, cc, sf=gauge.sf_from_tilts(tx, ty))
        worst = max(worst, abs(r.volume - t.volume_below(z, sx, sy)) / fs_v * 100.0)
    out["plane_fit_worst_pct_fs"] = worst
    axs[0].axhspan(-100 * data.REQ_ACC_FS, 100 * data.REQ_ACC_FS, color="0.85", zorder=0)
    axs[0].set_xlabel("fill, % of full volume")
    axs[0].set_ylabel("volume error, % of full scale")
    axs[0].set_title("placing the surface wrongly (grey: +/-2 % FS)", fontsize=8)
    axs[0].legend(fontsize=6)
    axs[0].set_ylim(-30, 30)

    # take-off roll and rotation: specific-force tilt vs pitch attitude
    tt = np.linspace(0, 40, 401)
    a = np.where(tt < 30, 0.25 - 0.12 * tt / 30, 0.11) * data.G0  # forward acceleration (A)
    pitch = np.where(tt < 28, 0.0, np.minimum((tt - 28) * 4.0, 10.0))  # rotation at 28 s, 4 deg/s (A)
    th = np.radians(pitch)
    tilt = np.degrees(np.arctan((a + data.G0 * np.sin(th)) / (data.G0 * np.cos(th))))
    lim = math.degrees(math.atan(gauge.SX_RANGE[1]))
    axs[1].plot(tt, tilt, color=COLORS[0], label="fuel-surface tilt")
    axs[1].plot(tt, pitch, color=COLORS[1], ls="--", label="pitch attitude")
    axs[1].axhline(lim, color="k", ls=":", lw=1)
    axs[1].text(1, lim + 0.6, "attitude table limit %.0f deg" % lim, fontsize=7)
    axs[1].set_xlabel("time from brake release, s")
    axs[1].set_ylabel("deg")
    axs[1].set_title("take-off: acceleration tilts the fuel more than the pitch does", fontsize=8)
    axs[1].legend(fontsize=7)
    out["takeoff"] = {
        "max_tilt_deg": float(tilt.max()),
        "time_beyond_table_s": float(np.sum(tilt > lim) * (tt[1] - tt[0])),
        "tilt_at_brake_release_deg": float(tilt[0]),
    }
    fig.suptitle("S2: the fuel surface follows the specific force", fontsize=9)
    save(fig, "s2_attitude.png")
    print(
        {k: v["max_abs"] for k, v in out.items() if isinstance(v, dict) and "max_abs" in v},
        worst,
        out["takeoff"],
    )
    dump("s2_attitude.json", out)


if __name__ == "__main__":
    main()
