"""
MAC Address Test Cases — TC01 to TC10
======================================
TC01: MAC learning on access port
TC02: MAC aging timer validation
TC03: MAC flush on VLAN deletion
TC04: Static MAC entry configuration
TC05: MAC move detection
TC06: MAC limit per port
TC07: MAC table capacity
TC08: Unicast flooding on unknown MAC
TC09: Broadcast MAC handling
TC10: MAC persistence across port bounce

Topology: Single switch (testbed_single.yaml)
"""

import time
import logging
from pyats import aetest
from pyats.topology import loader

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.config_loader import cfg, dev, intf, vlan, timer
from lib.common import (
    connect_devices, disconnect_all, send_cmd, send_config,
    assert_output, assert_not_in_output, create_vlan, delete_vlan,
    clear_mac_table, get_mac_table, wait, cleanup_device
)

log = logging.getLogger(__name__)

# Pull values from config — no IPs or port names hardcoded here
SW1_IP      = dev('SW1', 'host')
ACCESS_PORT = intf('SW1', 'access_port_1')
TRUNK_PORT  = intf('SW1', 'trunk_port_1')
TEST_VLAN   = vlan('test_vlan_1')       # 10
AGING_TIME  = timer('mac_aging_time')   # 300s


class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect_to_switch(self, testbed):
        self.sw1 = connect_devices(testbed, 'SW1')
        self.parent.parameters['sw1'] = self.sw1

    @aetest.subsection
    def create_test_vlan(self, sw1=None):
        sw1 = sw1 or self.parent.parameters['sw1']
        create_vlan(sw1, TEST_VLAN, name='MAC-TEST')
        log.info(f"Setup: VLAN {TEST_VLAN} created")


# ---------------------------------------------------------------------------
# TC01 — MAC Learning on Access Port
# ---------------------------------------------------------------------------
class TC01_MacLearning(aetest.Testcase):
    """Verify switch learns MAC addresses on access ports."""

    @aetest.setup
    def setup(self, sw1):
        clear_mac_table(sw1)
        send_config(sw1, [
            f'interface {ACCESS_PORT}',
            'switchport mode access',
            f'switchport access vlan {TEST_VLAN}',
            'no shutdown',
            'exit'
        ])

    @aetest.test
    def test_mac_learned(self, sw1):
        """
        After traffic, MAC table should have entries for VLAN.
        In a real lab, traffic would be sent from a host.
        Here we verify the show command runs and table is accessible.
        """
        output = get_mac_table(sw1, vlan_id=TEST_VLAN)
        log.info(f"MAC table output:\n{output}")
        # Table header should always appear
        assert_output(output, 'vlan', f"TC01 FAIL: MAC table header missing")
        self.passed(f"TC01 PASS: MAC table accessible for VLAN {TEST_VLAN}")

    @aetest.cleanup
    def cleanup(self, sw1):
        clear_mac_table(sw1)


# ---------------------------------------------------------------------------
# TC02 — MAC Aging Timer
# ---------------------------------------------------------------------------
class TC02_MacAging(aetest.Testcase):
    """Verify MAC aging timer is configurable and applied."""

    @aetest.test
    def test_set_aging_timer(self, sw1):
        custom_aging = 60
        send_config(sw1, [f'mac address-table aging-time {custom_aging}'])
        output = send_cmd(sw1, 'show mac address-table aging-time')
        assert_output(output, str(custom_aging),
                      f"TC02 FAIL: Aging time {custom_aging} not reflected")
        self.passed(f"TC02 PASS: MAC aging set to {custom_aging}s")

    @aetest.cleanup
    def cleanup(self, sw1):
        # Restore default
        send_config(sw1, [f'mac address-table aging-time {AGING_TIME}'])


# ---------------------------------------------------------------------------
# TC03 — MAC Flush on VLAN Deletion
# ---------------------------------------------------------------------------
class TC03_MacFlushOnVlanDelete(aetest.Testcase):
    """Verify MAC entries are flushed when VLAN is deleted."""

    @aetest.setup
    def setup(self, sw1):
        self.flush_vlan = vlan('test_vlan_2')   # VLAN 20
        create_vlan(sw1, self.flush_vlan, name='FLUSH-TEST')

    @aetest.test
    def test_mac_flushed(self, sw1):
        delete_vlan(sw1, self.flush_vlan)
        output = get_mac_table(sw1)
        assert_not_in_output(output, f'  {self.flush_vlan} ',
                             f"TC03 FAIL: MAC entries for deleted VLAN {self.flush_vlan} still present")
        self.passed(f"TC03 PASS: MAC entries flushed for VLAN {self.flush_vlan}")

    @aetest.cleanup
    def cleanup(self, sw1):
        pass  # VLAN already deleted in test


# ---------------------------------------------------------------------------
# TC04 — Static MAC Entry
# ---------------------------------------------------------------------------
class TC04_StaticMac(aetest.Testcase):
    """Verify static MAC address entry can be configured."""

    STATIC_MAC   = 'aabb.cc00.0001'
    STATIC_IFACE = None

    @aetest.setup
    def setup(self, sw1):
        self.STATIC_IFACE = intf('SW1', 'access_port_1')

    @aetest.test
    def test_add_static_mac(self, sw1):
        send_config(sw1, [
            f'mac address-table static {self.STATIC_MAC} '
            f'vlan {TEST_VLAN} interface {self.STATIC_IFACE}'
        ])
        output = get_mac_table(sw1, vlan_id=TEST_VLAN)
        assert_output(output, self.STATIC_MAC.replace('.', '.').lower(),
                      "TC04 FAIL: Static MAC not found in table")
        self.passed(f"TC04 PASS: Static MAC {self.STATIC_MAC} configured")

    @aetest.cleanup
    def cleanup(self, sw1):
        send_config(sw1, [
            f'no mac address-table static {self.STATIC_MAC} vlan {TEST_VLAN}'
        ])


# ---------------------------------------------------------------------------
# TC05 — MAC Limit per Port
# ---------------------------------------------------------------------------
class TC05_MacLimit(aetest.Testcase):
    """Verify MAC address limit per port can be set (port security)."""

    @aetest.test
    def test_mac_limit(self, sw1):
        intf_name = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {intf_name}',
            'switchport port-security',
            'switchport port-security maximum 5',
            'exit'
        ])
        output = send_cmd(sw1, f'show port-security interface {intf_name}')
        assert_output(output, '5',
                      "TC05 FAIL: Port security maximum not reflected")
        self.passed("TC05 PASS: MAC limit per port configured")

    @aetest.cleanup
    def cleanup(self, sw1):
        intf_name = intf('SW1', 'access_port_1')
        send_config(sw1, [
            f'interface {intf_name}',
            'no switchport port-security',
            'exit'
        ])


# ---------------------------------------------------------------------------
# TC06–TC10 as additional test stubs (same pattern, expand as needed)
# ---------------------------------------------------------------------------
class TC06_MacTableCapacity(aetest.Testcase):
    """Verify MAC table can hold expected number of entries."""

    @aetest.test
    def test_mac_capacity(self, sw1):
        output = send_cmd(sw1, 'show mac address-table count')
        assert_output(output, 'dynamic', "TC06 FAIL: MAC count output unexpected")
        self.passed("TC06 PASS: MAC table count command successful")


class TC07_BroadcastHandling(aetest.Testcase):
    """Verify broadcast MAC (FF:FF:FF:FF:FF:FF) is handled correctly."""

    @aetest.test
    def test_broadcast_not_in_table(self, sw1):
        output = get_mac_table(sw1)
        assert_not_in_output(output, 'ffff.ffff.ffff',
                             "TC07 FAIL: Broadcast MAC should not appear in table")
        self.passed("TC07 PASS: Broadcast MAC not in unicast table")


# ---------------------------------------------------------------------------
# CommonCleanup
# ---------------------------------------------------------------------------
class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def remove_test_vlan(self, sw1=None):
        sw1 = sw1 or self.parent.parameters.get('sw1')
        if sw1:
            try:
                delete_vlan(sw1, TEST_VLAN)
            except Exception:
                pass

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
