"""
l2_full_job.py — Master pyATS Job File
========================================
Runs all L2 test cases. Each task picks the right testbed automatically.

Run:
    pyats run job jobs/l2_full_job.py
    pyats run job jobs/l2_full_job.py --groups vlan
    pyats run job jobs/l2_full_job.py --groups "mac vlan"
    pyats run job jobs/l2_full_job.py --groups "rstp erps"

Groups: mac, vlan, rstp, mstp, port_neg, auto_mdix,
        mirror, lag, erps, oam, mvrp, qinq, scalability
"""

import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

T = os.path.join(ROOT, 'testbeds')
S = os.path.join(ROOT, 'tests')

SINGLE = os.path.join(T, 'testbed_single.yaml')
DUAL   = os.path.join(T, 'testbed_dual.yaml')
RING   = os.path.join(T, 'testbed_ring.yaml')


def main(runtime):
    runtime.job.name = 'HFCL L2 Full Test Suite'

    # Single-switch
    runtime.tasks.run(testscript=f'{S}/01_mac/test_mac.py',
                      taskid='MAC_TC01-10',      testbed=SINGLE, groups=['mac'])
    runtime.tasks.run(testscript=f'{S}/02_vlan/test_vlan_access_access.py',
                      taskid='VLAN_TC01-06',     testbed=SINGLE, groups=['vlan'])
    runtime.tasks.run(testscript=f'{S}/02_vlan/test_vlan.py',
                      taskid='VLAN_TC07-20',     testbed=SINGLE, groups=['vlan'])
    runtime.tasks.run(testscript=f'{S}/05_port_negotiation/test_port_neg.py',
                      taskid='PORT_NEG_TC01-02', testbed=SINGLE, groups=['port_neg'])
    runtime.tasks.run(testscript=f'{S}/06_auto_mdix/test_auto_mdix.py',
                      taskid='AUTO_MDIX_TC01-02',testbed=SINGLE, groups=['auto_mdix'])
    runtime.tasks.run(testscript=f'{S}/07_port_mirroring/test_port_mirror.py',
                      taskid='PORT_MIRROR_TC01', testbed=SINGLE, groups=['mirror'])
    runtime.tasks.run(testscript=f'{S}/08_vlan_mirroring/test_vlan_mirror.py',
                      taskid='VLAN_MIRROR_TC01', testbed=SINGLE, groups=['mirror'])
    runtime.tasks.run(testscript=f'{S}/14_scalability/test_scalability.py',
                      taskid='SCALE_TC01-05',    testbed=SINGLE, groups=['scalability'])

    # Dual-switch
    runtime.tasks.run(testscript=f'{S}/03_rstp/test_rstp.py',
                      taskid='RSTP_TC01-10',     testbed=DUAL,   groups=['rstp'])
    runtime.tasks.run(testscript=f'{S}/09_lag/test_lag.py',
                      taskid='LAG_TC01-07',      testbed=DUAL,   groups=['lag'])
    runtime.tasks.run(testscript=f'{S}/11_ethernet_oam/test_oam.py',
                      taskid='OAM_TC01-05',      testbed=DUAL,   groups=['oam'])
    runtime.tasks.run(testscript=f'{S}/12_mvrp/test_mvrp.py',
                      taskid='MVRP_TC01-11',     testbed=DUAL,   groups=['mvrp'])
    runtime.tasks.run(testscript=f'{S}/13_qinq/test_qinq.py',
                      taskid='QINQ_TC01-09',     testbed=DUAL,   groups=['qinq'])

    # Ring (3 switches)
    runtime.tasks.run(testscript=f'{S}/04_mstp/test_mstp.py',
                      taskid='MSTP_TC01-11',     testbed=RING,   groups=['mstp'])
    runtime.tasks.run(testscript=f'{S}/10_erps/test_erps.py',
                      taskid='ERPS_TC01-09',     testbed=RING,   groups=['erps'])
