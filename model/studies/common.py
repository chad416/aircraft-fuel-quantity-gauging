"""Shared helpers for the study scripts: paths, figure style, JSON results."""

from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(ROOT, "model")
if MODEL not in sys.path:
    sys.path.insert(0, MODEL)
IMG = os.path.join(ROOT, "docs", "img")
RES = os.path.join(ROOT, "results")
os.makedirs(IMG, exist_ok=True)
os.makedirs(RES, exist_ok=True)

COLORS = ["#2a6f97", "#d1495b", "#66a182", "#edae49", "#7b4b94", "#4f5d75", "#00798c"]

plt.rcParams.update(
    {
        "figure.dpi": 110,
        "savefig.dpi": 130,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": matplotlib.cycler(color=COLORS),
    }
)


def save(fig, name):
    path = os.path.join(IMG, name)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def dump(name, obj):
    def conv(o):
        try:
            import numpy as np

            if isinstance(o, np.ndarray):
                return np.round(o.astype(float), 4).tolist()
            if isinstance(o, (np.floating,)):
                return round(float(o), 4)
            if isinstance(o, (np.integer,)):
                return int(o)
            if isinstance(o, (np.bool_,)):
                return bool(o)
        except ImportError:
            pass
        raise TypeError(type(o))

    path = os.path.join(RES, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, default=conv)
    return path
