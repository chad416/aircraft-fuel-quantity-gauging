"""Probe candidate sites, the envelope grid and the chosen layout (set by study S3)."""

from __future__ import annotations

import functools

import numpy as np

from . import data, gauge, probe, tank

# candidate sites: chord fractions inside the box (spar clearance) x spanwise stations
XI_SITES = (0.19, 0.30, 0.41, 0.53)
Y_SITES = (1.30, 1.75, 2.25, 2.75, 3.25, 3.75, 4.10)

# envelope grid for coverage (tilts in degrees, fill as a fraction of the full volume)
TX = (-5.0, -2.0, 1.0, 4.0, 8.0, 12.0)
TY = (-5.0, -2.5, 0.0, 2.5, 5.0)
FILLS = (0.03, 0.06, 0.10, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.92, 0.97)

# chosen layout: indices into candidates() (S3 result; see DOSSIER §8 and §9.3)
CHOSEN = (0, 1, 3, 6, 9, 16, 18, 25)


@functools.lru_cache(maxsize=1)
def the_tank():
    return tank.Tank()


@functools.lru_cache(maxsize=1)
def the_table():
    return gauge.build_table(the_tank())


def site_xy(xi, y):
    w = data.WING
    f = (y - w["y_root"]) / (w["y_tip"] - w["y_root"])
    chord = w["chord_root"] + f * (w["chord_tip"] - w["chord_root"])
    x_le = (y - w["y_root"]) * np.tan(np.radians(w["sweep_le_deg"]))
    return float(x_le + xi * chord), float(y)


@functools.lru_cache(maxsize=1)
def candidates():
    t = the_tank()
    out = []
    for y in Y_SITES:
        for xi in XI_SITES:
            x, yy = site_xy(xi, y)
            out.append(probe.make_probe(t, x, yy))
    return tuple(out)


def chosen_probes(layout=CHOSEN):
    c = candidates()
    return [c[i] for i in layout]


def cfg_for(layout=CHOSEN, mirror=False):
    return gauge.make_cfg(the_tank(), chosen_probes(layout), mirror=mirror, table=the_table())


@functools.lru_cache(maxsize=1)
def envelope_states():
    """(tx, ty, fill, z_ref, sx, sy) for the coverage grid."""
    t = the_tank()
    out = []
    for tx in TX:
        for ty in TY:
            sx, sy = tank.slopes(tx, ty)
            for f in FILLS:
                out.append((tx, ty, f, t.z_for_volume(f * t.v_full, sx, sy), sx, sy))
    return tuple(out)
