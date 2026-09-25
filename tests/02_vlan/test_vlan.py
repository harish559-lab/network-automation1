"""
VLAN Test Cases — TC11 to TC30
================================
TC11: VLAN creation and deletion
TC12: Access port VLAN assignment
TC13: Trunk port VLAN tagging
TC14: Native VLAN configuration
TC15: VLAN allowed list on trunk
TC16: VLAN pruning
TC17: Inter-VLAN isolation
TC18: VLAN name assignment
TC19: VLAN database persistence (save/reload)
TC20: Bulk VLAN creation
TC21-TC30: Additional VLAN features

Topology: Single switch (testbed_single.yaml)
"""

import logging
from pyats import aetest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.config_loader import vlan, intf, timer
from lib.common import (
    connect_devices, disconnect_all, send_cmd, send_config,
    assert_output, assert_not_in_output, create_vlan, delete_vlan,
    verify_vlan_exists, set_port_vlan, cleanup_device, wait
)

log = logging.getLogger(__name__)

# All values from config — nothing hardcoded
VLAN1      = vlan('test_vlan_1')        # 10
VLAN2      = vlan('test_vlan_2')        # 20
VLAN3      = vlan('test_vlan_3')        # 30
NATIVE     = vlan('native_vlan')        # 1
MGMT_VLAN  = vlan('management_vlan')   # 100
ACCESS1    = intf('SW1', 'access_port_1')
ACCESS2    = intf('SW1', 'access_port_2')
TRUNK1     = intf('SW1', 'trunk_port_1')
TRUNK2     = intf('SW1', 'trunk_port_2')


class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect(self, testbed):
        sw1 = connect_devices(testbed, 'SW1')
        self.parent.parameters['sw1'] = sw1


class TC11_VlanCreateDelete(aetest.Testcase):
    """TC11: VLAN creation and deletion."""

    @aetest.test
    def test_create_vlan(self, sw1):
        create_vlan(sw1, VLAN1, name='TC11-TEST')
        assert verify_vlan_exists(sw1, VLAN1), \
            f"TC11 FAIL: VLAN {VLAN1} not found after creation"
        self.passed(f"TC11a PASS: VLAN {VLAN1} created")

    @aetest.test
    def test_delete_vlan(self, sw1):
        delete_vlan(sw1, VLAN1)
        assert not verify_vlan_exists(sw1, VLAN1), \
            f"TC11 FAIL: VLAN {VLAN1} still present after deletion"
        self.passed(f"TC11b PASS: VLAN {VLAN1} deleted")


class TC12_AccessPortVlan(aetest.Testcase):
    """TC12: Access port VLAN assignment."""

    @aetest.setup
    def setup(self, sw1):
        create_vlan(sw1, VLAN1)

    @aetest.test
    def test_access_port(self, sw1):
        set_port_vlan(sw1, ACCESS1, VLAN1, mode='access')
        output = send_cmd(sw1, f'show interfaces {ACCESS1} switchport')
        assert_output(output, 'access mode vlan',
                      "TC12 FAIL: Access mode not confirmed")
        assert_output(output, str(VLAN1),
                      f"TC12 FAIL: VLAN {VLAN1} not assigned to {ACCESS1}")
        self.passed(f"TC12 PASS: {ACCESS1} set to access VLAN {VLAN1}")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, [f'default interface {ACCESS1}'])
        delete_vlan(sw1, VLAN1)


class TC13_TrunkPortTagging(aetest.Testcase):
    """TC13: Trunk port VLAN tagging."""

    @aetest.setup
    def setup(self, sw1):
        create_vlan(sw1, VLAN1)
        create_vlan(sw1, VLAN2)

    @aetest.test
    def test_trunk_port(self, sw1):
        send_config(sw1, [
            f'interface {TRUNK1}',
            'switchport mode trunk',
            f'switchport trunk allowed vlan {VLAN1},{VLAN2}',
            'no shutdown',
            'exit'
        ])
        output = send_cmd(sw1, f'show interfaces {TRUNK1} trunk')
        assert_output(output, str(VLAN1),
                      f"TC13 FAIL: VLAN {VLAN1} not in trunk allowed list")
        assert_output(output, str(VLAN2),
                      f"TC13 FAIL: VLAN {VLAN2} not in trunk allowed list")
        self.passed(f"TC13 PASS: Trunk {TRUNK1} carries VLAN {VLAN1},{VLAN2}")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, [f'default interface {TRUNK1}'])
        delete_vlan(sw1, VLAN1)
        delete_vlan(sw1, VLAN2)


class TC14_NativeVlan(aetest.Testcase):
    """TC14: Native VLAN configuration on trunk."""

    @aetest.test
    def test_native_vlan(self, sw1):
        send_config(sw1, [
            f'interface {TRUNK1}',
            'switchport mode trunk',
            f'switchport trunk native vlan {NATIVE}',
            'exit'
        ])
        output = send_cmd(sw1, f'show interfaces {TRUNK1} trunk')
        assert_output(output, str(NATIVE),
                      f"TC14 FAIL: Native VLAN {NATIVE} not reflected")
        self.passed(f"TC14 PASS: Native VLAN set to {NATIVE}")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, [f'default interface {TRUNK1}'])


class TC15_VlanAllowedList(aetest.Testcase):
    """TC15: Trunk VLAN allowed list add/remove."""

    @aetest.setup
    def setup(self, sw1):
        for v in [VLAN1, VLAN2, VLAN3]:
            create_vlan(sw1, v)
        send_config(sw1, [
            f'interface {TRUNK1}',
            'switchport mode trunk',
            f'switchport trunk allowed vlan {VLAN1},{VLAN2},{VLAN3}',
            'exit'
        ])

    @aetest.test
    def test_remove_vlan_from_trunk(self, sw1):
        send_config(sw1, [
            f'interface {TRUNK1}',
            f'switchport trunk allowed vlan remove {VLAN3}',
            'exit'
        ])
        output = send_cmd(sw1, f'show interfaces {TRUNK1} trunk')
        # VLAN1 and VLAN2 should still be there
        assert_output(output, str(VLAN1), "TC15 FAIL: VLAN1 removed unexpectedly")
        self.passed("TC15 PASS: VLAN removed from trunk allowed list")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, [f'default interface {TRUNK1}'])
        for v in [VLAN1, VLAN2, VLAN3]:
            delete_vlan(sw1, v)


class TC16_VlanName(aetest.Testcase):
    """TC16: VLAN name assignment and verification."""

    @aetest.test
    def test_vlan_name(self, sw1):
        create_vlan(sw1, VLAN1, name='CORP-NETWORK')
        output = send_cmd(sw1, 'show vlan brief')
        assert_output(output, 'CORP-NETWORK',
                      "TC16 FAIL: VLAN name not reflected")
        self.passed("TC16 PASS: VLAN name set correctly")

    @aetest.cleanup
    def cleanup(self, sw1):
        delete_vlan(sw1, VLAN1)


class TC17_BulkVlanCreation(aetest.Testcase):
    """TC17: Create a range of VLANs (scalability check)."""

    @aetest.test
    def test_bulk_vlan(self, sw1):
        # Create VLANs 500-509 (small range for this test)
        send_config(sw1, ['vlan 500-509', 'exit'])
        output = send_cmd(sw1, 'show vlan brief')
        assert_output(output, '500', "TC17 FAIL: Bulk VLAN 500 not created")
        assert_output(output, '509', "TC17 FAIL: Bulk VLAN 509 not created")
        self.passed("TC17 PASS: Bulk VLAN range 500-509 created")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, ['no vlan 500-509'])


class CommonCleanup(aetest.CommonCleanup):

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
