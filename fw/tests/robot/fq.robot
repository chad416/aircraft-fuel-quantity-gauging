*** Settings ***
Documentation       Gauge-computer integration tests: the test image on the MIMXRT1064-EVK
...                 model in Renode, with sim/rig.py replaying 10 Hz acquisition data made
...                 by model/studies/s8_export.py. Requirement IDs (FQ-xx) refer to fw/SRS.md.
Suite Setup         Setup
Suite Teardown      Teardown
Test Setup          Reset Emulation
Test Teardown       Test Teardown
Resource            common.resource

*** Test Cases ***
IT01 Boot And First Indication
    [Documentation]    FQ-46, FQ-60, FQ-70: normal sign/status from the first frames; total within 2 % FS.
    [Tags]    FQ-46    FQ-60    FQ-70
    Boot With    sc1_flight.csv
    Advance    3.0
    ${n}=    Rig    rig.outs
    Should Be True    int($n) >= 28
    ${ok}=    Rig    rig.all_ssm_normal(0.2)
    Should Be Equal    ${ok}    True
    ${e}=    Rig    rig.max_err(0.5)
    ${tot}=    Rig    rig.a429_total()
    ${pb}=    Rig    rig.parity_bad
    Log To Console    \noutputs ${n}; max tank error ${e} kg; A429 total ${tot} kg; parity errors ${pb}
    Should Be True    float($e) <= 0.02 * ${FS_TANK}
    Should Be Equal As Integers    ${pb}    0
    Should Be True    float($tot) > 700

IT02 Flight Profile Within 2 Percent
    [Documentation]    FQ-01, FQ-13, FQ-17, FQ-44: take-off roll (surface tilt up to 16 deg), climb,
    ...                cruise with a sideslip, descent; both tanks within 2 % FS, no fault latched.
    [Tags]    FQ-01    FQ-13    FQ-17    FQ-44
    Boot With    sc1_flight.csv
    Advance    120.05
    ${e}=    Rig    rig.max_err(1.0)
    ${eto}=    Rig    rig.max_err(5.0, 30.0)
    ${ok}=    Rig    rig.all_ssm_normal(0.5)
    ${ab}=    Rig    rig.abnormal(0.5)
    Log To Console    \nnot normal: ${ab}
    ${fl}=    Rig    rig.last(9)
    ${fr}=    Rig    rig.last(10)
    Log To Console    \nmax error ${e} kg (take-off ${eto} kg) of ${FS_TANK} kg FS
    Should Be True    float($e) <= 0.02 * ${FS_TANK}
    Should Be Equal    ${ok}    True
    Should Be Equal As Integers    ${fl}    0
    Should Be Equal As Integers    ${fr}    0

IT03 Probe Faults Excluded And Latched
    [Documentation]    FQ-11, FQ-14, FQ-15, FQ-42: right P3 opens at 10 s, right P5 drifts +30 mm at
    ...                20 s, 3 mm of water reaches left P2 at 30 s; each latched, indication stays within 3 % FS.
    [Tags]    FQ-11    FQ-14    FQ-15    FQ-42
    Boot With    sc2_faults.csv
    Advance    40.05
    ${t3}=    Rig    rig.first_failed_time(1, 4)
    ${t5}=    Rig    rig.first_failed_time(1, 16)
    ${t2}=    Rig    rig.first_failed_time(0, 2)
    ${e}=    Rig    rig.max_err(1.0)
    ${ok}=    Rig    rig.all_ssm_normal(0.5)
    ${ab}=    Rig    rig.abnormal(0.5)
    Log To Console    \nnot normal: ${ab}
    Log To Console    \nlatched: R3 at ${t3} ms, R5 at ${t5} ms, L2 at ${t2} ms; max error ${e} kg
    Should Be True    10000 < float($t3) <= 10600
    Should Be True    20000 < float($t5) <= 20600
    Should Be True    30000 < float($t2) <= 30600
    Should Be True    float($e) <= 0.03 * ${FS_TANK}
    Should Be Equal    ${ok}    True

IT04 Low Fuel Warning
    [Documentation]    FQ-50, FQ-52: the left low-level sensor goes dry at 60 kg: LOW FUEL L after
    ...                20 s of persistence and the lamp discrete on; the right tank is still above.
    [Tags]    FQ-50    FQ-52
    Boot With    sc3_low.csv
    Advance    70.5
    ${tc}=    Rig    rig.first_row_time_below(0, 60.0)
    ${tw}=    Rig    rig.first_status_time(${ST_LOW_L})
    ${twr}=    Rig    rig.first_status_time(${ST_LOW_R})
    ${lamp}=    Rig    rig.read_u32('fq_diag_lamp')
    ${dt}=    Evaluate    (float($tw) - float($tc)) / 1000.0
    Log To Console    \nleft below 60 kg at ${tc} ms; LOW FUEL L ${dt} s later; lamp ${lamp}
    Should Be True    19.8 <= $dt <= 21.0
    Should Be Equal As Integers    ${lamp}    1
    Should Be True    float($twr) < 0

IT05 Compensator Drift And Data Gap
    [Documentation]    FQ-41, FQ-48: the right compensator drifts +0.06 at 5 s: XCOMP, both tanks
    ...                use the larger eps and read low, not high; no data 15-17 s: NCD after 0.5 s, then normal.
    [Tags]    FQ-41    FQ-48
    Boot With    sc4_comp_gap.csv
    Advance    30.5
    ${tx}=    Rig    rig.first_status_time(${ST_XCOMP})
    ${over}=    Rig    rig.max_over(6.0, 14.9)
    ${tn}=    Rig    rig.first_status_time(${ST_NODATA})
    ${tncd}=    Rig    rig.first_ssm_time(1, ${SSM_NCD}, 15000)
    ${tback}=    Rig    rig.first_ssm_time(1, ${SSM_NO}, ${tncd})
    Log To Console    \nXCOMP at ${tx} ms; reads high by at most ${over} kg; NO DATA at ${tn} ms; normal again at ${tback} ms
    Should Be True    5000 < float($tx) <= 5300
    Should Be True    float($over) <= 0.005 * ${FS_TANK}
    ${late}=    Rig    rig.max_over(14.0, 14.9)
    Should Be True    float($late) < 0.0
    Should Be True    15400 <= float($tn) <= 15800
    Should Be True    float($tback) > 17000

IT06 Stuck Dry Low-Level Sensor
    [Documentation]    FQ-50, FQ-51: the right sensor reads dry from 5 s while the tank holds 350 kg:
    ...                LOW FUEL R after 20 s (the sensor alone may warn), FQ DISAGREE after 60 s.
    [Tags]    FQ-50    FQ-51
    Boot With    sc5_stuck_dry.csv
    Advance    75.5
    ${tl}=    Rig    rig.first_status_time(${ST_LOW_R})
    ${td}=    Rig    rig.first_status_time(${ST_DIS_R})
    Log To Console    \nLOW FUEL R at ${tl} ms; FQ DISAGREE R at ${td} ms
    Should Be True    24800 <= float($tl) <= 25600
    Should Be True    64800 <= float($td) <= 65600

IT07 Cycle Time
    [Documentation]    FQ-05: worst computation time of one cycle below 10 % of the 100 ms cycle.
    [Tags]    FQ-05
    Boot With    sc2_faults.csv
    Advance    25.0
    ${c}=    Rig    rig.read_u32('fq_diag_max_cyc')
    ${us}=    Evaluate    int($c) / 600.0
    Log To Console    \nworst fq_step ${us} us (Renode virtual time, 600 MHz)
    Should Be True    0 < $us < 10000
