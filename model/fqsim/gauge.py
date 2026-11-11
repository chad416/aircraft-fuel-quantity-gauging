"""Reference implementation of the gauging algorithm (the specification of fw/lib/fq).

One computation cycle for one tank (no memory except the inputs given):

1. permittivity from the compensator, with a plausibility window;
2. wetted height of each probe; range faults (open, short or water); classification
   DRY / LIVE / FULL;
3. fuel plane z = z_ref + sx (x - xr) + sy (y - yr) by least squares through the LIVE probes;
4. fault detection with the residual (chi-square, n - 3 degrees of freedom) and exclusion
   by leave-one-out when n >= 5: the probe-level analogue of GNSS RAIM;
5. consistency of the DRY / FULL probes with a verified plane;
6. with fewer than 3 LIVE probes: slopes from the specific force (fallback);
7. volume from the attitude table by trilinear interpolation; usable volume; mass.

The monitor lane (MON) is a diverse computation: slopes from the specific force, height from
the median of the LIVE probes, the same table.  Units: pF, m, kg, m^3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import chi2

from . import data, fuel

# ---- algorithm constants (exported to fw/lib/fq/include/fq/fq_config.h) ------------------
EPS_MIN, EPS_MAX = 1.85, 2.45  # plausible fuel permittivity window (A, covers -55..+70 C)
EPS_DEFAULT = 2.13  # used when no compensator is plausible (D: nominal fuel at 15 C)
C_OPEN_PF = 2.0  # below C_dry - this: open circuit (pF)
C_SHORT_PF = 2.0  # above the full-probe value at EPS_MAX + this: short or water (pF)
H_SAT = 0.002  # m; h <= H_SAT is DRY
SAT_REL = 0.025  # h >= L (1 - SAT_REL) - H_SAT is FULL: a full probe can read 2 % short (D, S4)
SIGMA_Z = 0.0012  # m, height-independent 1-sigma per probe in the residual test (D, S4)
KAPPA = 0.012  # relative 1-sigma per metre wetted (eps stratification, compensator) (D, S4)
PFA = 1e-5  # false-alarm probability per test (A)
DET_MIN = 3e-3  # m^4, minimum determinant of the weighted position covariance: a plane from a
# tight cluster of probes extrapolates badly across the tank (D, S3/S4)
SAT_TOL = 0.015  # m, tolerance of the DRY / FULL consistency check
SX_RANGE = (-0.18, 0.36)  # table slopes (about -10..+20 deg)
SY_RANGE = (-0.14, 0.14)  # (about -8..+8 deg)
N_SX, N_SY, N_U = 25, 17, 65

# chi-square thresholds T[d] for d = 1..8 degrees of freedom
CHI2 = [float(chi2.isf(PFA, d)) for d in range(1, 9)]

ST_OK, ST_DEGRADED, ST_INVALID = 0, 1, 2
CL_DRY, CL_LIVE, CL_FULL, CL_OPEN, CL_SHORT, CL_EXCL = 0, 1, 2, 3, 4, 5


@dataclass
class Table:
    xr: float
    yr: float
    sx: np.ndarray
    sy: np.ndarray
    z_empty: np.ndarray  # [n_sx, n_sy]
    z_full: np.ndarray
    vol: np.ndarray  # [n_sx, n_sy, n_u]
    v_unusable: float


def build_table(tank):
    sx = np.linspace(*SX_RANGE, N_SX)
    sy = np.linspace(*SY_RANGE, N_SY)
    ze = np.zeros((N_SX, N_SY))
    zf = np.zeros((N_SX, N_SY))
    vol = np.zeros((N_SX, N_SY, N_U))
    u = np.linspace(0.0, 1.0, N_U)
    for i, a in enumerate(sx):
        for j, b in enumerate(sy):
            ze[i, j] = tank.z_empty(a, b)
            zf[i, j] = tank.z_full(a, b)
            vol[i, j] = tank.volume_below(ze[i, j] + u * (zf[i, j] - ze[i, j]), a, b)
    return Table(tank.xr, tank.yr, sx, sy, ze, zf, vol, tank.v_unusable)


def _locate(v, lo, hi, n):
    t = (min(max(v, lo), hi) - lo) / (hi - lo) * (n - 1)
    i = min(int(t), n - 2)
    return i, t - i


def table_volume(tb, z_ref, sx, sy):
    """Trilinear interpolation of the attitude table (slopes must be inside the table)."""
    i, fx = _locate(sx, tb.sx[0], tb.sx[-1], len(tb.sx))
    j, fy = _locate(sy, tb.sy[0], tb.sy[-1], len(tb.sy))
    v = 0.0
    for di, wi in ((0, 1.0 - fx), (1, fx)):
        for dj, wj in ((0, 1.0 - fy), (1, fy)):
            ze = tb.z_empty[i + di, j + dj]
            zf = tb.z_full[i + di, j + dj]
            uu = min(max((z_ref - ze) / (zf - ze), 0.0), 1.0)
            k, fu = _locate(uu, 0.0, 1.0, tb.vol.shape[2])
            vv = tb.vol[i + di, j + dj, k] * (1.0 - fu) + tb.vol[i + di, j + dj, k + 1] * fu
            v += wi * wj * vv
    return v


def in_table(tb, sx, sy):
    return tb.sx[0] <= sx <= tb.sx[-1] and tb.sy[0] <= sy <= tb.sy[-1]


@dataclass
class TankCfg:
    px: np.ndarray
    py: np.ndarray
    zbot: np.ndarray
    plen: np.ndarray
    cdry_pf: np.ndarray
    k_pf: np.ndarray  # pF per metre per unit (eps - 1)
    comp_cdry_pf: float
    comp_kl_pf: float  # pF per unit (eps - 1)
    table: Table
    mirror: bool = False  # left tank: lateral specific force changes sign


def make_cfg(tank, probes, mirror=False, table=None):
    from .probe import compensator_capacitance  # noqa: F401  (documented dependency)

    kl = data.PROBE_K * data.COMP_LEN * 1e12
    return TankCfg(
        px=np.array([p.x for p in probes]),
        py=np.array([p.y for p in probes]),
        zbot=np.array([p.z_bot for p in probes]),
        plen=np.array([p.length for p in probes]),
        cdry_pf=np.array([p.c_dry * 1e12 for p in probes]),
        k_pf=np.array([p.k * 1e12 for p in probes]),
        comp_cdry_pf=(data.PROBE_C_END + data.PROBE_K * data.COMP_LEN) * 1e12,
        comp_kl_pf=kl,
        table=build_table(tank) if table is None else table,
        mirror=mirror,
    )


def comp_eps(cfg, c_comp_pf):
    """Permittivity from the compensator, or None if implausible."""
    e = 1.0 + (c_comp_pf - cfg.comp_cdry_pf) / cfg.comp_kl_pf
    return e if EPS_MIN <= e <= EPS_MAX else None


def classify(cfg, caps_pf, eps):
    n = len(caps_pf)
    h = np.zeros(n)
    cl = np.zeros(n, dtype=int)
    for i in range(n):
        c = caps_pf[i]
        full_max = cfg.cdry_pf[i] + cfg.k_pf[i] * (EPS_MAX - 1.0) * cfg.plen[i] + C_SHORT_PF
        if c < cfg.cdry_pf[i] - C_OPEN_PF:
            cl[i] = CL_OPEN
            continue
        if c > full_max:
            cl[i] = CL_SHORT
            continue
        h[i] = (c - cfg.cdry_pf[i]) / (cfg.k_pf[i] * (eps - 1.0))
        if h[i] <= H_SAT:
            cl[i] = CL_DRY
        elif h[i] >= cfg.plen[i] * (1.0 - SAT_REL) - H_SAT:
            cl[i] = CL_FULL
        else:
            cl[i] = CL_LIVE
    return h, cl


def weights(h):
    """Inverse variance of each probe's surface height: sigma^2 = SIGMA_Z^2 + (KAPPA h)^2."""
    h = np.asarray(h, dtype=float)
    return 1.0 / (SIGMA_Z**2 + (KAPPA * h) ** 2)


def fit_plane(cfg, idx, zs, w=None):
    """Weighted least squares plane through probes idx with surface heights zs and weights w
    (same order).  Returns (z_ref, sx, sy, chi2) - chi2 is the weighted residual sum, already
    normalised by the variances - or None when the geometry is degenerate."""
    if len(idx) < 3:
        return None
    w = np.ones(len(idx)) / SIGMA_Z**2 if w is None else np.asarray(w, dtype=float)
    x = cfg.px[idx] - cfg.table.xr
    y = cfg.py[idx] - cfg.table.yr
    sw = w.sum()
    mx, my, mz = (w * x).sum() / sw, (w * y).sum() / sw, (w * zs).sum() / sw
    dx, dy, dz = x - mx, y - my, zs - mz
    sxx, syy, sxy = (w * dx * dx).sum() / sw, (w * dy * dy).sum() / sw, (w * dx * dy).sum() / sw
    sxz, syz = (w * dx * dz).sum() / sw, (w * dy * dz).sum() / sw
    det = sxx * syy - sxy * sxy
    if det < DET_MIN:
        return None
    a = (sxz * syy - syz * sxy) / det
    b = (syz * sxx - sxz * sxy) / det
    z0 = mz - a * mx - b * my
    r = zs - (z0 + a * x + b * y)
    return z0, a, b, float((w * r * r).sum())


@dataclass
class Result:
    status: int = ST_OK
    z_ref: float = 0.0
    sx: float = 0.0
    sy: float = 0.0
    volume: float = 0.0  # total (m^3)
    usable: float = 0.0  # m^3
    mass: float = 0.0  # kg
    rho: float = 0.0
    eps: float = 0.0
    excluded: int = -1  # probe excluded by the residual test this cycle
    detected: bool = False  # residual test failed (before exclusion)
    verified: bool = False  # plane from >= 4 LIVE probes that passed the test
    n_live: int = 0
    cls: list = field(default_factory=list)
    sat_bad: list = field(default_factory=list)  # DRY/FULL probes inconsistent with the plane
    fallback: bool = False


def sf_slopes(cfg, sf):
    """Fuel-surface slopes in this tank's frame from the body specific force (fx, fy, fz)."""
    fx, fy, fz = sf
    sx = -fx / fz
    sy = -fy / fz
    return sx, (-sy if cfg.mirror else sy)


def solve(cfg, caps_pf, c_comp_pf, sf=None, rho_meas=None, eps_hint=None, failed=None, hold=None):
    """One computation cycle for one tank.  failed: probes latched failed (excluded).
    hold: (sx, sy) of the last verified plane, used when sf is None in the fallback."""
    res = Result()
    eps = comp_eps(cfg, c_comp_pf)
    if eps is None:
        eps = EPS_DEFAULT if eps_hint is None else eps_hint
        res.status = ST_DEGRADED
    res.eps = eps
    h, cl = classify(cfg, np.asarray(caps_pf, dtype=float), eps)
    n = len(h)
    failed = np.zeros(n, dtype=bool) if failed is None else np.asarray(failed, dtype=bool)
    cl = np.where(failed, CL_EXCL, cl)
    zs_all = cfg.zbot + h
    live = [i for i in range(n) if cl[i] == CL_LIVE]
    res.n_live = len(live)
    wt = weights(h)
    plane = fit_plane(cfg, np.array(live, dtype=int), zs_all[live], wt[live]) if len(live) >= 3 else None
    if plane is not None and len(live) >= 4:
        dof = len(live) - 3
        if plane[3] > CHI2[dof - 1]:
            res.detected = True
            best = None
            if len(live) >= 5:
                for j in live:
                    sub = [i for i in live if i != j]
                    p = fit_plane(cfg, np.array(sub, dtype=int), zs_all[sub], wt[sub])
                    if p is not None and (best is None or p[3] < best[1][3]):
                        best = (j, p)
            if best is not None and best[1][3] <= CHI2[dof - 2]:
                res.excluded = best[0]
                cl[best[0]] = CL_EXCL
                plane = best[1]
                live = [i for i in live if i != best[0]]
                res.n_live = len(live)
                res.verified = len(live) >= 4
            else:
                res.cls = cl.tolist()
                res.status = ST_INVALID
                return res
        else:
            res.verified = True
    if plane is not None:
        z_ref, sx, sy = plane[0], plane[1], plane[2]
        # DRY / FULL probes must agree with the plane
        for i in range(n):
            if cl[i] in (CL_DRY, CL_FULL):
                zp = z_ref + sx * (cfg.px[i] - cfg.table.xr) + sy * (cfg.py[i] - cfg.table.yr)
                if cl[i] == CL_DRY and zp > cfg.zbot[i] + SAT_TOL:
                    res.sat_bad.append(i)
                if cl[i] == CL_FULL and zp < cfg.zbot[i] + cfg.plen[i] - SAT_TOL:
                    res.sat_bad.append(i)
        if res.sat_bad and not res.verified:
            plane = None  # an unverified plane that a DRY/FULL probe contradicts: use the fallback
            res.sat_bad = []
    if plane is None:
        # fallback: slopes from the specific force, or held from the last verified plane
        if sf is not None:
            sx, sy = sf_slopes(cfg, sf)
        elif hold is not None:
            sx, sy = hold
        else:
            res.cls = cl.tolist()
            res.status = ST_INVALID
            return res
        res.fallback = True
        usable_idx = [i for i in range(n) if cl[i] in (CL_DRY, CL_LIVE, CL_FULL)]
        if not usable_idx:
            res.cls = cl.tolist()
            res.status = ST_INVALID
            return res
        if live:
            off = [
                zs_all[i] - sx * (cfg.px[i] - cfg.table.xr) - sy * (cfg.py[i] - cfg.table.yr) for i in live
            ]
            z_ref = float(np.mean(off))
        else:
            fulls = [i for i in usable_idx if cl[i] == CL_FULL]
            if fulls:  # conservative: the lowest plane that still covers every FULL probe
                z_ref = max(
                    cfg.zbot[i]
                    + cfg.plen[i]
                    - sx * (cfg.px[i] - cfg.table.xr)
                    - sy * (cfg.py[i] - cfg.table.yr)
                    for i in fulls
                )
            else:  # all DRY: report empty (indicated <= true)
                z_ref = -1e3
        res.status = ST_DEGRADED
    if not in_table(cfg.table, sx, sy):
        res.cls = cl.tolist()
        res.status = ST_INVALID
        return res
    v = table_volume(cfg.table, z_ref, sx, sy)
    res.z_ref, res.sx, res.sy, res.volume = z_ref, sx, sy, v
    res.usable = max(0.0, v - cfg.table.v_unusable)
    res.rho = rho_meas if rho_meas is not None else float(fuel.rho_from_eps(eps))
    res.mass = res.usable * res.rho
    res.cls = cl.tolist()
    return res


def monitor(cfg, caps_pf, eps, sf, failed=None):
    """MON lane: slopes from the specific force, height from the median of LIVE probes.
    Returns the usable volume (m^3) or None if it cannot compute."""
    if sf is None:
        return None
    h, cl = classify(cfg, np.asarray(caps_pf, dtype=float), eps)
    failed = np.zeros(len(h), dtype=bool) if failed is None else np.asarray(failed, dtype=bool)
    sx, sy = sf_slopes(cfg, sf)
    if not in_table(cfg.table, sx, sy):
        return None
    live = [i for i in range(len(h)) if cl[i] == CL_LIVE and not failed[i]]
    if not live:
        return None
    off = sorted(
        cfg.zbot[i] + h[i] - sx * (cfg.px[i] - cfg.table.xr) - sy * (cfg.py[i] - cfg.table.yr) for i in live
    )
    m = len(off)
    z = off[m // 2] if m % 2 == 1 else 0.5 * (off[m // 2 - 1] + off[m // 2])
    return max(0.0, table_volume(cfg.table, z, sx, sy) - cfg.table.v_unusable)


def full_scale_mass(tank):
    """Full-scale usable mass of one tank at the design density 800 kg/m^3 (A)."""
    return (tank.v_full - tank.v_unusable) * 800.0


def sf_from_tilts(tilt_x_deg, tilt_y_deg):
    """A unit specific-force vector that produces the given surface tilts (right tank frame)."""
    tx, ty = math.tan(math.radians(tilt_x_deg)), math.tan(math.radians(tilt_y_deg))
    return (-tx, -ty, 1.0)
