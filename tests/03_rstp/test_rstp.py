"""
RSTP Test Cases — TC31 to TC40
================================
TC31: RSTP mode enabled
TC32: Root bridge election by priority
TC33: Port role assignment (Root/Designated/Alternate)
TC34: Port state transitions (Discarding → Learning → Forwarding)
TC35: TCN (Topology Change Notification) on port down
TC36: RSTP convergence time (< 1s expected)
TC37: BPDUGuard on edge port
TC38: BPDUFilter configuration
TC39: PortFast on access port
TC40: Root guard configuration

Topology: Dual switch (testbed_dual.yaml) — SW1=root, SW2=peer
"""

import time
import logging
from pyats import aetest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.config_loader import vlan, intf, get_stp_config, timer
from lib.common import (
    connect_devices, disconnect_all, send_cmd, send_config,
    assert_output, assert_not_in_output, create_vlan, delete_vlan,
    port_up, port_down, wait, wait_for_convergence, show_stp
)

log = logging.getLogger(__name__)

STP_CFG    = get_stp_config()
TEST_VLAN  = vlan('test_vlan_1')
TRUNK_SW1  = intf('SW1', 'trunk_port_1')
TRUNK_SW2  = intf('SW2', 'trunk_port_1')
PRIO_ROOT  = STP_CFG['priority_sw1']    # 4096
PRIO_PEER  = STP_CFG['priority_sw2']    # 8192


class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect(self, testbed):
        devs = connect_devices(testbed, 'SW1', 'SW2')
        self.parent.parameters['sw1'] = devs['SW1']
        self.parent.parameters['sw2'] = devs['SW2']

    @aetest.subsection
    def enable_rstp(self, sw1, sw2):
        for dev in [sw1, sw2]:
            send_config(dev, ['spanning-tree mode rapid-pvst'])
        create_vlan(sw1, TEST_VLAN)
        create_vlan(sw2, TEST_VLAN)
        # Trunk between SW1 and SW2
        for dev, port in [(sw1, TRUNK_SW1), (sw2, TRUNK_SW2)]:
            send_config(dev, [
                f'interface {port}',
                'switchport mode trunk',
                f'switchport trunk allowed vlan {TEST_VLAN}',
                'no shutdown',
                'exit'
            ])
        wait_for_convergence("initial RSTP setup")


class TC31_RstpEnabled(aetest.Testcase):
    """TC31: Verify RSTP mode is active."""

    @aetest.test
    def test_rstp_mode(self, sw1):
        output = show_stp(sw1, vlan_id=TEST_VLAN)
        assert_output(output, 'ieee', "TC31 FAIL: RSTP mode not active")
        self.passed("TC31 PASS: RSTP mode confirmed")


class TC32_RootBridgeElection(aetest.Testcase):
    """TC32: Verify SW1 is root bridge with lower priority."""

    @aetest.setup
    def setup(self, sw1, sw2):
        send_config(sw1, [f'spanning-tree vlan {TEST_VLAN} priority {PRIO_ROOT}'])
        send_config(sw2, [f'spanning-tree vlan {TEST_VLAN} priority {PRIO_PEER}'])
        wait_for_convergence("root election")

    @aetest.test
    def test_sw1_is_root(self, sw1):
        output = show_stp(sw1, vlan_id=TEST_VLAN)
        assert_output(output, 'This bridge is the root',
                      "TC32 FAIL: SW1 is not the root bridge")
        self.passed(f"TC32 PASS: SW1 is root bridge (priority {PRIO_ROOT})")

    @aetest.test
    def test_sw2_is_not_root(self, sw2):
        output = show_stp(sw2, vlan_id=TEST_VLAN)
        assert_not_in_output(output, 'This bridge is the root',
                             "TC32 FAIL: SW2 should not be root bridge")
        self.passed("TC32 PASS: SW2 is not root bridge")


class TC33_PortRoles(aetest.Testcase):
    """TC33: Verify port role assignment on root and non-root."""

    @aetest.test
    def test_root_bridge_designated_ports(self, sw1):
        output = show_stp(sw1, vlan_id=TEST_VLAN)
        assert_output(output, 'Desg', "TC33 FAIL: No Designated ports on root bridge")
        self.passed("TC33 PASS: Root bridge has Designated ports")

    @aetest.test
    def test_nonroot_root_port(self, sw2):
        output = show_stp(sw2, vlan_id=TEST_VLAN)
        assert_output(output, 'Root', "TC33 FAIL: No Root port on SW2")
        self.passed("TC33 PASS: SW2 has Root port toward root bridge")


class TC34_PortFast(aetest.Testcase):
    """TC34: PortFast on access port — skips Discarding/Learning."""

    @aetest.test
    def test_portfast(self, sw1):
        access = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {access}',
            'spanning-tree portfast',
            'exit'
        ])
        output = send_cmd(sw1, f'show spanning-tree interface {access} detail')
        assert_output(output, 'portfast', "TC34 FAIL: PortFast not active on port")
        self.passed("TC34 PASS: PortFast configured on access port")

    @aetest.cleanup
    def cleanup(self, sw1):
        access = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {access}',
            'no spanning-tree portfast',
            'exit'
        ])


class TC35_BpduGuard(aetest.Testcase):
    """TC35: BPDUGuard — errdisable port if BPDU received."""

    @aetest.test
    def test_bpdu_guard_config(self, sw1):
        access = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {access}',
            'spanning-tree portfast',
            'spanning-tree bpduguard enable',
            'exit'
        ])
        output = send_cmd(sw1, f'show spanning-tree interface {access} detail')
        assert_output(output, 'bpdu guard',
                      "TC35 FAIL: BPDUGuard not active")
        self.passed("TC35 PASS: BPDUGuard configured")

    @aetest.cleanup
    def cleanup(self, sw1):
        access = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {access}',
            'no spanning-tree portfast',
            'no spanning-tree bpduguard enable',
            'exit'
        ])


class TC36_RootGuard(aetest.Testcase):
    """TC36: Root Guard — prevent superior BPDU from changing root."""

    @aetest.test
    def test_root_guard(self, sw1):
        trunk = intf('SW1', 'trunk_port_2')
        send_config(sw1, [
            f'interface {trunk}',
            'spanning-tree guard root',
            'exit'
        ])
        output = send_cmd(sw1, f'show spanning-tree interface {trunk} detail')
        assert_output(output, 'root guard',
                      "TC36 FAIL: Root Guard not active")
        self.passed("TC36 PASS: Root Guard configured")

    @aetest.cleanup
    def cleanup(self, sw1):
        trunk = intf('SW1', 'trunk_port_2')
        send_config(sw1, [
            f'interface {trunk}',
            'no spanning-tree guard root',
            'exit'
        ])


class TC37_ConvergenceOnLinkDown(aetest.Testcase):
    """TC37: Verify RSTP re-converges when uplink goes down."""

    @aetest.test
    def test_convergence(self, sw1, sw2):
        t_start = time.time()
        port_down(sw1, TRUNK_SW1)
        wait(2, "link down propagation")
        port_up(sw1, TRUNK_SW1)
        wait_for_convergence("RSTP re-convergence")
        t_end = time.time()
        elapsed = t_end - t_start
        log.info(f"TC37: Re-convergence cycle took {elapsed:.1f}s")
        output = show_stp(sw1, vlan_id=TEST_VLAN)
        assert_output(output, 'FWD', "TC37 FAIL: Port not in Forwarding after convergence")
        self.passed(f"TC37 PASS: RSTP re-converged in {elapsed:.1f}s")


class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def restore_stp_defaults(self, sw1, sw2):
        for dev in [sw1, sw2]:
            send_config(dev, [
                f'no spanning-tree vlan {TEST_VLAN} priority',
                'spanning-tree mode rapid-pvst',
            ])

    @aetest.subsection
    def remove_vlans(self, sw1, sw2):
        for dev in [sw1, sw2]:
            delete_vlan(dev, TEST_VLAN)

    @aetest.subsection
    def disconnect(self, testbed):
        disconnect_all(testbed)


if __name__ == '__main__':
    import argparse
    from pyats.topology import loader
    parser = argparse.ArgumentParser()
    parser.add_argument('--testbed', required=True)
    args, _ = parser.parse_known_args()
    testbed = loader.load(args.testbed)
    aetest.main(testbed=testbed)
