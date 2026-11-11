*** Settings ***
Documentation       Shared keywords for the gauge-computer integration tests in Renode.
Resource            ${RENODEKEYWORDS}

*** Variables ***
# Overridden by scripts/test-sim.sh
${ELF}              /root/recorder-ws/build/fqis/zephyr/zephyr.elf
${OUT}              /tmp/fqis-robot
${SIM}              ${CURDIR}/../../sim
${SSM_FW}           0
${SSM_NCD}          1
${SSM_NO}           3
${ST_LOW_L}         1
${ST_LOW_R}         2
${ST_DIS_R}         8
${ST_DEG_R}         32
${ST_XCOMP}         256
${ST_NODATA}        512
# full-scale usable mass of one tank (S8 export): 743.9 kg
${FS_TANK}          743.9

*** Keywords ***
Boot With
    [Arguments]    ${scenario}
    Execute Command             $elf=@${ELF}
    Execute Command             include @${SIM}/fq.resc
    Execute Command             include @${SIM}/rig.py
    Execute Command             python "rig = Rig(self.Machine, '${SIM}/scenarios/${scenario}')"
    Create Terminal Tester      sysbus.lpuart1    defaultPauseEmulation=True
    Start Emulation
    Wait For Line On Uart       fq READY    timeout=5

Advance
    [Documentation]    Run the emulation for a fixed virtual time (seconds).
    [Arguments]    ${seconds}
    Execute Command             pause
    Execute Command             emulation RunFor "${seconds}"

Rig
    [Documentation]    Evaluate an expression on the rig (IronPython inside Renode).
    [Arguments]    ${code}
    ${out}=    Execute Command    python "print(${code})"
    ${out}=    Evaluate    $out.strip()
    RETURN    ${out}
