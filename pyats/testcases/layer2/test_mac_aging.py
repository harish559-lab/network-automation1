#!/usr/bin/env python3
"""
test_mac_aging.py
-----------------
pyATS test script for: "Verify MAC address expiry interval"

Device CLI reference (HFCL Switch):
  Show MAC table   : show mac address-table
  Show aging time  : show mac address-table aging-time
    → Output format: "MAC Age Time: 50"
  Set aging time   : mac address-table aging-time <seconds>

Test Cases:
  TC-01 : Verify MAC aging-time is correctly configured
  TC-02 : Verify MAC entries are learned after bi-directional traffic
  TC-03 : Verify dynamic MAC entries are flushed after aging-time expires
  TC-04 : Verify static MAC entries remain after aging-time expires

Usage:
  sudo python3 pyats/testcases/layer2/test_mac_aging.py --testbed pyats/testbed.yaml
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
DEVICE_NAME    = "Hfcl-Switch"
TRAFFIC_IFACE  = "enp2s0"
MAC_AGING_TIME = 50        # seconds
TRAFFIC_SCRIPT = "/home/harish/Documents/network-automation/scripts/MAC_generate_traffic.py"

# MACs injected by generate_traffic.py
SRC_MAC = "00:11:22:33:44:aa"
DST_MAC = "00:11:22:33:44:bb"

log = logging.getLogger(__name__)


# ===========================================================================
# Common Setup — connect to device
# ===========================================================================
class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to Hfcl-Switch via SSH."""
        device = testbed.devices[DEVICE_NAME]
        device.connect(log_stdout=True)
        # Store device so all testcases and cleanup can access it
        self.parent.parameters["device"] = device
        log.info(f"✅ Connected to {DEVICE_NAME}")


# ===========================================================================
# TC-01 : Verify MAC aging-time configuration
# ===========================================================================
class TC01_VerifyMacAgingConfig(aetest.Testcase):

    @aetest.test
    def verify_aging_time(self, device):
        """
        Command : show mac address-table aging-time
        Expected: MAC Age Time: 50
        """
        output = device.execute("show mac address-table aging-time")
        log.info(f"Aging-time output:\n{output}")

        match = re.search(r"MAC Age Time:\s*(\d+)", output)
        if not match:
            self.failed(
                f"❌ TC-01 FAIL: Could not parse 'MAC Age Time' from output:\n{output}"
            )

        configured_time = int(match.group(1))
        if configured_time == MAC_AGING_TIME:
            log.info(f"✅ TC-01 PASS: MAC Age Time = {configured_time}s (expected {MAC_AGING_TIME}s)")
            self.passed(f"MAC aging-time correctly set to {MAC_AGING_TIME} seconds")
        else:
            self.failed(
                f"❌ TC-01 FAIL: MAC Age Time = {configured_time}s "
                f"but expected {MAC_AGING_TIME}s"
            )


# ===========================================================================
# TC-02 : Verify MAC entries learned after bi-directional traffic
# ===========================================================================
class TC02_VerifyMacLearning(aetest.Testcase):

    @aetest.setup
    def send_bidirectional_traffic(self):
        """
        Launch Scapy traffic generator with sudo.
        Scapy requires raw socket access which needs root privileges.
        """
        log.info("🚦 Sending bi-directional traffic via Scapy (sudo)...")
        result = subprocess.run(
            ["sudo", "python3", TRAFFIC_SCRIPT, "--interface", TRAFFIC_IFACE],
            capture_output=True, text=True, timeout=60
        )
        log.info(f"Traffic stdout:\n{result.stdout}")
        if result.returncode != 0:
            log.warning(f"Traffic stderr:\n{result.stderr}")
            log.warning("⚠️  Traffic generation failed — TC-02 MAC checks may fail.")
        else:
            log.info("✅ Traffic generation successful.")

        log.info("⏳ Waiting 5 seconds for switch MAC table to update...")
        time.sleep(5)

    @aetest.test
    def verify_src_mac_learned(self, device):
        """Verify SRC MAC is listed as Dynamic in the MAC table."""
        output = device.execute("show mac address-table")
        log.info(f"MAC table:\n{output}")

        if SRC_MAC in output.lower():
            log.info(f"✅ TC-02a PASS: SRC MAC {SRC_MAC} learned.")
        else:
            self.failed(f"❌ TC-02a FAIL: SRC MAC {SRC_MAC} NOT found in MAC table.")

    @aetest.test
    def verify_dst_mac_learned(self, device):
        """Verify DST MAC is listed as Dynamic in the MAC table."""
        output = device.execute("show mac address-table")

        if DST_MAC in output.lower():
            log.info(f"✅ TC-02b PASS: DST MAC {DST_MAC} learned.")
        else:
            self.failed(f"❌ TC-02b FAIL: DST MAC {DST_MAC} NOT found in MAC table.")

    @aetest.test
    def verify_entries_are_dynamic(self, device):
        """Verify learned entries show type 'Dynamic' (not Static)."""
        output = device.execute("show mac address-table")
        lines = output.splitlines()

        for mac in [SRC_MAC, DST_MAC]:
            for line in lines:
                if mac in line.lower():
                    if "dynamic" in line.lower():
                        log.info(f"✅ {mac} is correctly marked as Dynamic: {line.strip()}")
                    else:
                        self.failed(
                            f"❌ {mac} found but NOT marked Dynamic: {line.strip()}"
                        )


# ===========================================================================
# TC-03 : Verify dynamic MAC entries flushed after aging-time expires
# ===========================================================================
class TC03_VerifyMacFlushedAfterExpiry(aetest.Testcase):

    @aetest.setup
    def snapshot_before_expiry(self, device):
        """Snapshot MAC table before waiting for expiry."""
        output = device.execute("show mac address-table")
        log.info(f"📸 MAC table BEFORE expiry:\n{output}")

    @aetest.test
    def wait_for_aging_expiry(self):
        """Wait aging-time + 30s buffer for entries to age out."""
        wait_time = MAC_AGING_TIME + 30
        log.info(f"⏳ Waiting {wait_time}s for MAC entries to age out...")
        time.sleep(wait_time)

    @aetest.test
    def verify_dynamic_macs_flushed(self, device):
        """
        After expiry, SRC and DST MACs must NOT appear in MAC table.
        Static entries are expected to remain.
        """
        output = device.execute("show mac address-table")
        log.info(f"📋 MAC table AFTER expiry:\n{output}")

        output_lower = output.lower()
        src_flushed = SRC_MAC not in output_lower
        dst_flushed = DST_MAC not in output_lower

        if src_flushed and dst_flushed:
            log.info(f"✅ TC-03 PASS: Both dynamic MACs flushed after {MAC_AGING_TIME}s.")
            self.passed("Dynamic MAC entries correctly flushed after aging-time expiry.")
        else:
            still_present = []
            if not src_flushed:
                still_present.append(SRC_MAC)
            if not dst_flushed:
                still_present.append(DST_MAC)
            self.failed(
                f"❌ TC-03 FAIL: MACs still present after expiry: {still_present}"
            )


# ===========================================================================
# TC-04 : Verify static MAC entries remain after aging-time expires
# ===========================================================================
class TC04_VerifyStaticMacsRemain(aetest.Testcase):

    @aetest.test
    def verify_static_entries_present(self, device):
        """
        Static MACs (Type = Static in 'show mac address-table') must
        remain even after the aging timer fires.
        """
        output = device.execute("show mac address-table")
        log.info(f"📋 MAC table for static check:\n{output}")

        lines = output.splitlines()
        static_entries = [
            line for line in lines
            if line.strip().lower().startswith("static")
        ]

        if static_entries:
            log.info(f"✅ TC-04 PASS: {len(static_entries)} static entry(ies) found:")
            for entry in static_entries:
                log.info(f"   {entry.strip()}")
            self.passed("Static MAC entries remain after aging-time expiry.")
        else:
            log.warning(
                "⚠️  No static entries found — acceptable if none are configured."
            )
            self.skipped(
                "No static MAC entries configured on switch — verify manually."
            )


# ===========================================================================
# Common Cleanup — disconnect
# ===========================================================================
class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def disconnect(self):
        """
        FIX: 'device' must be fetched from self.parent.parameters, not
        injected as a function argument — CommonCleanup has no testcase
        scope so aetest cannot inject 'device' directly.
        """
        device = self.parent.parameters.get("device")
        if device is None:
            log.warning("No device to disconnect (connection may have failed earlier).")
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
    parser.add_argument("--testbed", required=True, help="Path to testbed YAML")
    args, unknown = parser.parse_known_args()
    testbed = loader.load(args.testbed)
    aetest.main(testbed=testbed)
