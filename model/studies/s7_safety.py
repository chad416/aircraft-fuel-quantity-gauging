"""S7: safety and RMA - misleading quantity, the low-fuel warning, and energy into the tank.

1. Fault tree for "indicated total usable fuel more than 5 % FS high, undetected" per flight hour,
   built from failure rates (A) and the detection coverages the design achieves (S5 and the
   firmware's checks); then the catastrophic combination with a lost low-fuel warning.
   Targets: AC 23.1309-1E Fig. 2, Class IV (commuter): Hazardous < 1e-7, Catastrophic < 1e-9
   per flight hour [R3].
2. Intrinsic safety: energy stored in the in-tank circuit and current into the tank against the
   AC 25.981-1D limits (20 uJ design target, 50 uJ normal, 200 uJ failure; 25 mA rms steady,
   50 mA rms failure, 125 mA peak transient) [R2].
3. MTBF of the gauge and dispatch with one probe excluded.
"""

from __future__ import annotations

import json
import math
import os

from common import COLORS, RES, dump, plt, save

FLIGHT_H = 3.0  # mean flight time, h (A)

# failure rates per hour (A: order-of-magnitude values for this class of part; DOSSIER §10)
LAM = {
    "probe in-range drift (each)": 2.0e-6,
    "probe open/short (each)": 3.0e-6,
    "measurement channel, common-mode gain": 5.0e-6,
    "compensator in-range drift (each tank)": 1.0e-6,
    "processor / memory (COM+MON common)": 2.0e-6,
    "low-level sensor or its channel": 5.0e-6,
    "specific-force input (AHRS) wrong, undetected by AHRS": 1.0e-6,
}
N_PROBES = 16  # two tanks x 8


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    s5 = load("s5_fde.json")
    mis_bias = s5["summary"]["bias"]["misleading_after_mon"]
    mis_gain = s5["summary"]["gain"]["misleading_after_mon"]
    mis_com = s5["summary"]["bias"]["misleading_com_only"]
    # coverage assumptions of the other mechanisms (A, each implemented in fw, DOSSIER §6)
    cov_ref = 0.99  # reference-capacitor check every cycle on the measurement channel
    cov_comp = 0.95  # left/right compensator cross-check
    cov_cpu = 0.999  # watchdog + RAM/flash CRC + COM/MON comparison
    branches = {
        "probe drift, COM+MON miss (S5)": N_PROBES
        * LAM["probe in-range drift (each)"]
        * 0.5
        * (mis_bias + mis_gain),
        "probe drift, COM only (no MON)": N_PROBES * LAM["probe in-range drift (each)"] * mis_com,
        "channel gain, reference check miss": LAM["measurement channel, common-mode gain"] * (1 - cov_ref),
        "compensator drift, cross-check miss": 2
        * LAM["compensator in-range drift (each tank)"]
        * (1 - cov_comp),
        "processor/memory, undetected": LAM["processor / memory (COM+MON common)"] * (1 - cov_cpu),
    }
    # only a fraction of undetected drift events end above 5 % FS: already inside the S5 shares for
    # probes; for the common-mode branches the error grows with the drift - half of them assumed
    # to exceed 5 % FS before the next maintenance check (A)
    for k in (
        "channel gain, reference check miss",
        "compensator drift, cross-check miss",
        "processor/memory, undetected",
    ):
        branches[k] *= 0.5
    p_mis = sum(v for k, v in branches.items() if "COM only" not in k)
    # low-fuel warning unavailable: latent failure found by the pre-flight test of the sensor
    q_low = LAM["low-level sensor or its channel"] * FLIGHT_H / 2.0
    p_cat = p_mis * q_low
    # without the independent sensor the misleading branch is the catastrophic one
    res = {
        "branches_per_fh": branches,
        "p_misleading_per_fh": p_mis,
        "target_hazardous": 1e-7,
        "q_low_warning_unavailable": q_low,
        "p_catastrophic_per_fh": p_cat,
        "target_catastrophic": 1e-9,
        "p_catastrophic_without_low_sensor": p_mis,
    }

    # intrinsic safety of the probe excitation (design values, DOSSIER §7.3)
    c_probe_max = 250e-12  # F, longest probe full at eps 2.45 (95 pF dry + 231 pF/m x 0.40 m x 1.45, D)
    c_harness = 60e-12 * 8.0  # F, 60 pF/m x 8 m in-tank and wing harness (A)
    v_exc = 5.0 * math.sqrt(2.0)  # V peak, 5 V rms excitation (A)
    f_exc = 10e3  # Hz (A)
    e_norm = 0.5 * (c_probe_max + c_harness) * v_exc**2
    i_norm = 2 * math.pi * f_exc * (c_probe_max + c_harness) * 5.0
    v_hot = 32.2  # V, highest normal 28 V bus voltage of the equipment class (A)
    r_series = 1000.0  # ohm, series resistor in each in-tank line (design)
    i_fault = v_hot / r_series
    e_fault = 0.5 * (c_probe_max + c_harness) * v_hot**2
    tau = r_series * (c_probe_max + c_harness)
    res["intrinsic_safety"] = {
        "energy_normal_uJ": 1e6 * e_norm,
        "current_normal_mA_rms": 1e3 * i_norm,
        "hot_short_current_mA": 1e3 * i_fault,
        "hot_short_stored_energy_uJ": 1e6 * e_fault,
        "series_R_ohm": r_series,
        "rc_time_constant_us": 1e6 * tau,
        "phase_at_excitation_deg": math.degrees(2 * math.pi * f_exc * tau),
        "limits": {"design_uJ": 20, "normal_uJ": 50, "failure_uJ": 200, "steady_mA": 25, "failure_mA": 50},
    }
    # reliability of the gauge function (sum of rates, both tanks)
    lam_total = (
        N_PROBES * (LAM["probe in-range drift (each)"] + LAM["probe open/short (each)"])
        + 2 * LAM["measurement channel, common-mode gain"]
        + 2 * LAM["compensator in-range drift (each tank)"]
        + LAM["processor / memory (COM+MON common)"]
        + 2 * LAM["low-level sensor or its channel"]
    )
    res["mtbf_h"] = 1.0 / lam_total
    # dispatch: one probe failed and excluded is tolerable (S5 post-exclusion accuracy within 3 % FS)
    lam_probe = N_PROBES * (LAM["probe in-range drift (each)"] + LAM["probe open/short (each)"])
    res["share_of_failures_dispatchable_with_one_probe_out"] = lam_probe / lam_total
    print(res["p_misleading_per_fh"], res["p_catastrophic_per_fh"], res["intrinsic_safety"], res["mtbf_h"])

    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.3))
    names = [k for k in branches]
    vals = [branches[k] for k in names]
    axs[0].barh(range(len(names)), vals, color=[COLORS[1] if "COM only" in k else COLORS[0] for k in names])
    axs[0].set_xscale("log")
    axs[0].axvline(1e-7, color="k", ls=":", lw=1)
    axs[0].text(1.1e-7, len(names) - 0.6, "Hazardous < 1e-7", fontsize=7)
    axs[0].set_yticks(range(len(names)), names, fontsize=6.5)
    axs[0].set_xlabel("undetected misleading > 5 % FS, per flight hour")
    axs[0].set_title("fault-tree branches (red: without MON)", fontsize=8)
    lim = [p_mis, p_cat]
    axs[1].bar(
        ["misleading\n(hazardous)", "misleading + no\nlow-fuel warning"], lim, color=[COLORS[0], COLORS[2]]
    )
    axs[1].set_yscale("log")
    axs[1].plot([-0.4, 0.4], [1e-7, 1e-7], "k:", lw=1)
    axs[1].plot([0.6, 1.4], [1e-9, 1e-9], "k:", lw=1)
    axs[1].set_ylabel("per flight hour")
    axs[1].set_title("top events against AC 23.1309-1E Class IV", fontsize=8)
    fig.suptitle("S7: the independent low-level sensor carries the catastrophic case", fontsize=9)
    save(fig, "s7_safety.png")
    dump("s7_safety.json", res)


if __name__ == "__main__":
    main()
