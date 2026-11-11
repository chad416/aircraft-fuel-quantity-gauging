"""Integral wing-tank geometry and the volume below an arbitrary fuel plane.

The tank is the wing box between the front and rear spar and two ribs.  Its skins follow the
NACA four-digit thickness distribution [R9] scaled to the local thickness, on a straight
dihedral line (A).  Columns on a fine planform grid have a bottom z_lo(x, y) and a top z_up(x, y);
the fuel in a column is the part of [z_lo, z_up] below the fuel plane, so the volume below any
plane is a sum over columns.  That is exact for a tank with vertical walls and single-valued
skins, which a wing box is (to the grid resolution, checked in the tests against a box).

Frame (local to the tank): x aft of the root leading edge, y outboard, z up; the left tank
uses the same frame mirrored, so a lateral fuel-surface slope changes sign for it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import data

SKIN = 0.003  # m, skin + sealant thickness taken off both skins (A)


def naca_half_thickness(xi, tc):
    """Half thickness / chord of a NACA 4-digit section at chord fraction xi [R9] (V)."""
    return 5.0 * tc * (0.2969 * np.sqrt(xi) - 0.1260 * xi - 0.3516 * xi**2 + 0.2843 * xi**3 - 0.1015 * xi**4)


@dataclass
class Tank:
    ny: int = 96
    nxi: int = 48
    w: dict = field(default_factory=lambda: dict(data.WING))

    def __post_init__(self):
        w = self.w
        ys = np.linspace(w["y_root"], w["y_tip"], self.ny + 1)
        yc = 0.5 * (ys[1:] + ys[:-1])
        dy = ys[1] - ys[0]
        xis = np.linspace(w["box_front"], w["box_rear"], self.nxi + 1)
        xic = 0.5 * (xis[1:] + xis[:-1])
        dxi = xis[1] - xis[0]
        f = (yc - w["y_root"]) / (w["y_tip"] - w["y_root"])
        chord = w["chord_root"] + f * (w["chord_tip"] - w["chord_root"])
        tc = w["tc_root"] + f * (w["tc_tip"] - w["tc_root"])
        x_le = (yc - w["y_root"]) * math.tan(math.radians(w["sweep_le_deg"]))
        z_c = yc * math.tan(math.radians(w["dihedral_deg"]))
        Y, XI = np.meshgrid(yc, xic, indexing="ij")
        C = chord[:, None] * np.ones_like(XI)
        self.x = x_le[:, None] + XI * C
        self.y = Y
        half = naca_half_thickness(XI, tc[:, None]) * C
        self.z_lo = z_c[:, None] - half + SKIN
        self.z_up = z_c[:, None] + half - SKIN
        self.dA = (C * dxi) * dy
        self.depth = self.z_up - self.z_lo
        a = self.dA
        self.xr = float(np.sum(self.x * a) / np.sum(a))
        self.yr = float(np.sum(self.y * a) / np.sum(a))
        self.fill_frac = 1.0 - w["structure_frac"]
        self.v_full = self.volume_below(np.inf, 0.0, 0.0)
        z_e = self.z_empty(0.0, 0.0)
        self.v_unusable = float(self.volume_below(z_e + 0.020, 0.0, 0.0))  # outlet sump 20 mm deep (A)

    # --- geometry queries ------------------------------------------------------------------
    def lower(self, x, y):
        """Inner lower-skin height at planform point(s) (nearest column)."""
        return self._at(self.z_lo, x, y)

    def upper(self, x, y):
        return self._at(self.z_up, x, y)

    def _at(self, arr, x, y):
        x = np.atleast_1d(np.asarray(x, dtype=float))
        y = np.atleast_1d(np.asarray(y, dtype=float))
        iy = np.clip(np.searchsorted(self.y[:, 0], y) - 1, 0, self.ny - 1)
        out = np.empty_like(x)
        for k in range(x.size):
            row = self.x[iy[k]]
            j = int(np.clip(np.searchsorted(row, x[k]) - 1, 0, self.nxi - 2))
            t = float(np.clip((x[k] - row[j]) / (row[j + 1] - row[j]), 0.0, 1.0))
            yrow = self.y[:, 0]
            i0 = iy[k]
            i1 = min(i0 + 1, self.ny - 1)
            u = 0.0 if i1 == i0 else float(np.clip((y[k] - yrow[i0]) / (yrow[i1] - yrow[i0]), 0.0, 1.0))
            a0 = arr[i0, j] * (1 - t) + arr[i0, j + 1] * t
            a1 = arr[i1, j] * (1 - t) + arr[i1, j + 1] * t
            out[k] = a0 * (1 - u) + a1 * u
        return out

    def plane(self, z_ref, sx, sy, x=None, y=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        return z_ref + sx * (x - self.xr) + sy * (y - self.yr)

    def volume_below(self, z_ref, sx, sy):
        """Fuel volume (m^3) below the plane z = z_ref + sx (x - xr) + sy (y - yr).
        z_ref may be an array (vectorised over planes with the same slopes)."""
        z_ref = np.asarray(z_ref, dtype=float)
        base = sx * (self.x - self.xr) + sy * (self.y - self.yr)
        zs = z_ref[..., None, None] + base
        h = np.clip(zs - self.z_lo, 0.0, self.depth)
        return np.sum(h * self.dA, axis=(-2, -1)) * self.fill_frac

    def z_empty(self, sx, sy):
        return float(np.min(self.z_lo - sx * (self.x - self.xr) - sy * (self.y - self.yr)))

    def z_full(self, sx, sy):
        return float(np.max(self.z_up - sx * (self.x - self.xr) - sy * (self.y - self.yr)))

    def z_for_volume(self, v, sx, sy):
        """Plane height at the reference point that holds volume v (bisection)."""
        lo, hi = self.z_empty(sx, sy), self.z_full(sx, sy)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.volume_below(mid, sx, sy) < v:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)


def slopes(tilt_x_deg, tilt_y_deg):
    """Fuel-surface slopes in the tank frame for longitudinal / lateral tilts (deg).
    A nose-up tilt moves fuel aft: the surface rises towards +x relative to the skins."""
    return math.tan(math.radians(tilt_x_deg)), math.tan(math.radians(tilt_y_deg))


def tilts_from_specific_force(fx, fy, fz):
    """Surface tilts (deg) from the body specific force (any unit; x aft, y right, z up).
    The fuel surface is normal to the specific force: z = c - (fx/fz) x - (fy/fz) y."""
    return math.degrees(math.atan2(-fx, fz)), math.degrees(math.atan2(-fy, fz))
