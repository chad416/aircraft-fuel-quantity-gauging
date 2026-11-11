#!/usr/bin/env python3
"""Regenerate every study figure (docs/img) and result file (results/).

    python model/run_all.py [s1 s2 ...]

S1 fuel, S2 attitude, S3 probe placement, S4 error budget (about 2 min), S5 fault
detection, S6 AoA, S7 safety, S8 export to the firmware (needs S5).
"""

import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "studies"))
sys.path.insert(0, HERE)

STUDIES = [
    "s1_fuel",
    "s2_attitude",
    "s3_placement",
    "s4_budget",
    "s5_fde",
    "s6_aoa",
    "s7_safety",
    "s8_export",
]

if __name__ == "__main__":
    pick = sys.argv[1:]
    for name in STUDIES:
        if pick and name.split("_")[0] not in pick:
            continue
        t0 = time.time()
        print("== %s" % name, flush=True)
        importlib.import_module(name).main()
        print("   %.0f s" % (time.time() - t0), flush=True)
