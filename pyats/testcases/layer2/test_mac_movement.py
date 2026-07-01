#!/usr/bin/env python3
"""
test_mac_movement.py
--------------------
pyATS test script for: "Verify MAC movement between ports"

Device CLI reference (HFCL Switch):
  Show MAC table   : show mac address-table
  MAC table format : Type  VID  MAC Address        Ports
                     Dynamic 1  00:11:22:33:44:55  GigabitEthernet 1/1

Test Cases:
  TC01 : Verify MAC learned on Port 1 (Gi 1/1) after traffic from Laptop 1
  TC02 : Verify MAC moves to Port 2 (Gi 1/2) after traffic from Laptop 2
  TC03 : Verify old port entry is removed after MAC movement
  TC04 : Verify MAC entry type is Dynamic (not Static) after movement

Usage:
  python3 pyats/testcases/layer2/test_mac_movement.py --testbed pyats/testbed.yaml
"""

import re
import time
import logging
import subprocess

from pyats import aetest
from pyats.topology import loader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEVICE_NAME   = "Hfcl-Switch"

# Laptop 1 details (connected to Gi 1/1)
LAPTOP1_USER  = "harish"
LAPTOP1_IP    = "192.168.89.62"
LAPTOP1_IFACE = "enp2s0"

# Laptop 2 details (connected to Gi 1/2)
LAPTOP2_USER  = "lab-testing"
LAPTOP2_IP    = "192.168.89.63"
LAPTOP2_IFACE = "enp44s0"

# Traffic script path (same on both laptops)
TRAFFIC_SCRIPT = "/home/harish/Documents/network-automation/scripts/MAC_movement_traffic.py"
TRAFFIC_SCRIPT_L2 = "/home/lab-testing/Documents/network-automation/scripts/MAC_movement_traffic.py"

# MAC address used for movement test
TEST_MAC = "00:11:22:33:44:55"

# Expected ports
PORT1 = "GigabitEthernet 1/1"
PORT2 = "GigabitEthernet 1/2"

log = logging.getLogger(__name__)


def send_traffic(user, ip, script, iface, src_mac):
    """SSH to a laptop and run the traffic generator with sudo."""
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        f"{user}@{ip}",
        f"sudo /usr/bin/python3 {script} --interface {iface} --src-mac {src_mac}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    log.info(f"Traffic stdout:\n{result.stdout}")
    if result.returncode != 0:
        log.warning(f"Traffic stderr:\n{result.stderr}")
    return result.returncode == 0


def get_mac_port(output, mac):
    """Find which port a MAC address is learned on."""
    for line in output.splitlines():
        if mac.lower() in line.lower():
            parts = line.split()
            if len(parts) >= 4:
                # Port is everything after the MAC address
                mac_idx = next(i for i, p in enumerate(parts)
                               if mac.lower() in p.lower())
                port = " ".join(parts[mac_idx + 1:])
                return port.strip()
    return None


# ===========================================================================
# Common Setup — connect to device
# ===========================================================================
class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to Hfcl-Switch via SSH."""
        device = testbed.devices[DEVICE_NAME]
        device.connect(log_stdout=True)
        self.parent.parameters["device"] = device
        log.info(f"✅ Connected to {DEVICE_NAME}")

    @aetest.subsection
    def clear_test_mac(self, testbed):
        """Clear test MAC from table before starting if it exists."""
        device = self.parent.parameters["device"]
        output = device.execute("show mac address-table")
        if TEST_MAC.lower() in output.lower():
            log.info(f"Test MAC {TEST_MAC} found — clearing MAC table entries")
            device.execute("clear mac address-table dynamic")
            time.sleep(3)
        log.info("✅ MAC table ready for test")


# ===========================================================================
# TC01 : Verify MAC learned on Port 1 after traffic from Laptop 1
# ===========================================================================
class TC01_VerifyMacLearnedOnPort1(aetest.Testcase):

    @aetest.setup
    def send_traffic_from_laptop1(self):
        """Send traffic from Laptop 1 (connected to Gi 1/1)."""
        log.info(f"🚦 Sending traffic from Laptop 1 ({LAPTOP1_IP}) via {LAPTOP1_IFACE}...")
        success = send_traffic(
            LAPTOP1_USER, LAPTOP1_IP,
            TRAFFIC_SCRIPT, LAPTOP1_IFACE, TEST_MAC
        )
        if success:
            log.info("✅ Traffic sent successfully from Laptop 1")
        else:
            log.warning("⚠️  Traffic generation had issues — test may fail")
        log.info("⏳ Waiting 5 seconds for switch MAC table to update...")
        time.sleep(5)

    @aetest.test
    def verify_mac_on_port1(self, device):
        """Verify TEST_MAC is learned on Gi 1/1."""
        output = device.execute("show mac address-table")
        log.info(f"MAC table:\n{output}")

        if TEST_MAC.lower() not in output.lower():
            self.failed(f"❌ TC01 FAIL: MAC {TEST_MAC} NOT found in MAC table.")

        port = get_mac_port(output, TEST_MAC)
        log.info(f"MAC {TEST_MAC} found on port: {port}")

        if PORT1 in (port or ""):
            log.info(f"✅ TC01 PASS: MAC {TEST_MAC} correctly learned on {PORT1}")
            self.passed(f"MAC {TEST_MAC} learned on {PORT1}")
        else:
            self.failed(
                f"❌ TC01 FAIL: MAC {TEST_MAC} found on {port} "
                f"but expected {PORT1}"
            )

    @aetest.test
    def verify_entry_is_dynamic(self, device):
        """Verify the MAC entry is Dynamic."""
        output = device.execute("show mac address-table")
        for line in output.splitlines():
            if TEST_MAC.lower() in line.lower():
                if "dynamic" in line.lower():
                    log.info(f"✅ TC01b PASS: Entry is Dynamic: {line.strip()}")
                    self.passed("MAC entry is correctly marked as Dynamic")
                else:
                    self.failed(f"❌ TC01b FAIL: Entry not Dynamic: {line.strip()}")


# ===========================================================================
# TC02 : Verify MAC moves to Port 2 after traffic from Laptop 2
# ===========================================================================
class TC02_VerifyMacMovesToPort2(aetest.Testcase):

    @aetest.setup
    def send_traffic_from_laptop2(self):
        """Send same source MAC from Laptop 2 (connected to Gi 1/2)."""
        log.info(f"🚦 Sending traffic from Laptop 2 ({LAPTOP2_IP}) via {LAPTOP2_IFACE}...")
        success = send_traffic(
            LAPTOP2_USER, LAPTOP2_IP,
            TRAFFIC_SCRIPT_L2, LAPTOP2_IFACE, TEST_MAC
        )
        if success:
            log.info("✅ Traffic sent successfully from Laptop 2")
        else:
            log.warning("⚠️  Traffic generation had issues — test may fail")
        log.info("⏳ Waiting 5 seconds for switch MAC table to update...")
        time.sleep(5)

    @aetest.test
    def verify_mac_moved_to_port2(self, device):
        """Verify TEST_MAC has moved to Gi 1/2."""
        output = device.execute("show mac address-table")
        log.info(f"MAC table after movement:\n{output}")

        if TEST_MAC.lower() not in output.lower():
            self.failed(f"❌ TC02 FAIL: MAC {TEST_MAC} NOT found in MAC table.")

        port = get_mac_port(output, TEST_MAC)
        log.info(f"MAC {TEST_MAC} now on port: {port}")

        if PORT2 in (port or ""):
            log.info(f"✅ TC02 PASS: MAC {TEST_MAC} correctly moved to {PORT2}")
            self.passed(f"MAC movement confirmed: {TEST_MAC} now on {PORT2}")
        else:
            self.failed(
                f"❌ TC02 FAIL: MAC {TEST_MAC} found on {port} "
                f"but expected {PORT2} after movement"
            )


# ===========================================================================
# TC03 : Verify old port entry is removed after MAC movement
# ===========================================================================
class TC03_VerifyOldPortEntryRemoved(aetest.Testcase):

    @aetest.test
    def verify_mac_not_on_port1(self, device):
        """Verify TEST_MAC is no longer associated with Gi 1/1."""
        output = device.execute("show mac address-table")
        log.info(f"MAC table:\n{output}")

        port = get_mac_port(output, TEST_MAC)

        if port and PORT1 in port:
            self.failed(
                f"❌ TC03 FAIL: MAC {TEST_MAC} still on old port {PORT1} "
                f"after movement — switch did not update correctly."
            )
        else:
            log.info(
                f"✅ TC03 PASS: MAC {TEST_MAC} is no longer on {PORT1}. "
                f"Currently on: {port}"
            )
            self.passed(f"Old port entry correctly removed after MAC movement")


# ===========================================================================
# TC04 : Verify MAC entry is still Dynamic after movement
# ===========================================================================
class TC04_VerifyDynamicAfterMovement(aetest.Testcase):

    @aetest.test
    def verify_entry_dynamic_on_port2(self, device):
        """Verify MAC entry on new port is still Dynamic."""
        output = device.execute("show mac address-table")
        log.info(f"MAC table:\n{output}")

        for line in output.splitlines():
            if TEST_MAC.lower() in line.lower():
                if "dynamic" in line.lower():
                    log.info(f"✅ TC04 PASS: Entry still Dynamic after movement: {line.strip()}")
                    self.passed("MAC entry remains Dynamic after movement")
                else:
                    self.failed(
                        f"❌ TC04 FAIL: Entry not Dynamic after movement: {line.strip()}"
                    )
                return

        self.failed(f"❌ TC04 FAIL: MAC {TEST_MAC} not found in table at all.")


# ===========================================================================
# Common Cleanup — disconnect
# ===========================================================================
class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def disconnect(self):
        """Disconnect from device."""
        device = self.parent.parameters.get("device")
        if device is None:
            log.warning("No device to disconnect.")
            return
        try:
            device.disconnect()
            log.info(f"🔌 Disconnected from {DEVICE_NAME}")
        except Exception as e:
            log.warning(f"Disconnect warning: {e}")


# ===========================================================================
# Standalone entry-point
# ===========================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", required=True)
    args, unknown = parser.parse_known_args()
    testbed = loader.load(args.testbed)
    aetest.main(testbed=testbed)
