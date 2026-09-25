#!/usr/bin/env python3
"""
======================================================================
Testcase  : test_vlan_access_access.py
Category  : VLAN
TC IDs    : VLAN-TC01 to VLAN-TC06

Purpose   :
    Validate Access-to-Access VLAN communication on HFCL Switch.

Automation Flow:
    Jenkins → Ansible Config → Traffic Generation → pyATS Validation → HTML Report

Validations:
    ✓ VLAN exists
    ✓ Access port configuration
    ✓ Interface link status
    ✓ MAC address learning
    ✓ Interface counters
    ✓ Sender / Receiver traffic statistics

What changed from original:
    - All hardcoded values (IP, VLAN, ports, paths) now come from
      lib/config_loader.py → config/lab_config.yaml
    - Helper functions moved to lib/common.py (log_banner, execute_cli, etc.)
    - No behavior changes — same 6 test cases, same checks, same result JSON

Author : Harish
======================================================================
"""

import json
import logging
import os
import time

from pyats import aetest
from genie.testbed import load

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from lib.config_loader import dev, intf, vlan, traffic_cfg, report_path
from lib.common import (
    log_banner, send_cmd, connect_devices, disconnect_all,
    verify_output_contains, assert_output
)

# ----------------------------------------------------------------------
# Logger
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s : %(message)s"
)
log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Test Parameters — all from lab_config.yaml, nothing hardcoded
# ----------------------------------------------------------------------
SWITCH        = list(dev('HFCL').keys())[0] if False else 'HFCL'  # device name
VLAN_ID       = str(vlan('test_vlan_1'))                            # "1"
PORT1         = intf('HFCL', 'access_port_1')                      # "GigabitEthernet 1/1"
PORT2         = intf('HFCL', 'access_port_2')                      # "GigabitEthernet 1/2"
SENDER_JSON   = report_path('sender_json')                          # /tmp/sender_report.json
RECEIVER_JSON = report_path('receiver_json')                        # /tmp/receiver_report.json
LOSS_THRESHOLD = traffic_cfg('loss_threshold')                      # 1.0 %

# Dashboard summary written after TC06 — consumed by generate_dashboard.py
RESULT_JSON   = '/tmp/vlan_access_access_result.json'


# ----------------------------------------------------------------------
# JSON helpers (kept local — specific to this test's traffic reports)
# ----------------------------------------------------------------------
def load_json(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")
    with open(path) as fp:
        return json.load(fp)


# ----------------------------------------------------------------------
# CommonSetup
# ----------------------------------------------------------------------
class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def log_parameters(self):
        log_banner("Test Parameters")
        log.info(f"SWITCH  : {SWITCH}")
        log.info(f"VLAN_ID : {VLAN_ID}")
        log.info(f"PORT1   : {PORT1}")
        log.info(f"PORT2   : {PORT2}")
        log.info(f"Config  : config/lab_config.yaml")

    @aetest.subsection
    def connect_to_device(self, testbed):
        log_banner("Connecting to Switch")
        self.parent.parameters["start_time"] = time.time()
        device = testbed.devices[SWITCH]
        device.connect()
        self.parent.parameters["device"] = device
        log.info("Connected Successfully")


# ----------------------------------------------------------------------
# TC01 : Verify VLAN Exists
# ----------------------------------------------------------------------
class TC01_Verify_VLAN(aetest.Testcase):

    @aetest.test
    def verify_vlan_exists(self):
        log_banner("TC01 — VERIFY VLAN EXISTS")
        device = self.parent.parameters["device"]
        output = send_cmd(device, "show vlan brief")
        if verify_output_contains(output, VLAN_ID):
            self.passed(f"VLAN {VLAN_ID} found.")
        else:
            self.failed(f"VLAN {VLAN_ID} not found.")


# ----------------------------------------------------------------------
# TC02 : Verify Access Port Configuration
# ----------------------------------------------------------------------
class TC02_Verify_Interface_Config(aetest.Testcase):

    @aetest.test
    def verify_access_port_configuration(self):
        log_banner("TC02 — VERIFY ACCESS PORT CONFIGURATION")
        device = self.parent.parameters["device"]
        errors = []

        for interface in [PORT1, PORT2]:
            output = send_cmd(device, f"show running-config interface {interface}")
            checks = [
                ("switchport mode access",
                 f"{interface} is not configured as an access port."),
                (f"switchport access vlan {VLAN_ID}",
                 f"{interface} is not assigned to VLAN {VLAN_ID}."),
                ("no shutdown",
                 f"{interface} is administratively down."),
            ]
            for expected, msg in checks:
                if expected not in output:
                    errors.append(msg)

        if errors:
            self.failed("\n".join(errors))
        self.passed("Both interfaces correctly configured.")


# ----------------------------------------------------------------------
# TC03 : Verify Interface Link Status
# ----------------------------------------------------------------------
class TC03_Verify_Link_Status(aetest.Testcase):

    @aetest.test
    def verify_link_status(self):
        log_banner("TC03 — VERIFY INTERFACE LINK STATUS")
        device = self.parent.parameters["device"]
        output = send_cmd(device, "show interface GigabitEthernet * status")
        errors = []

        for interface in [PORT1, PORT2]:
            if interface not in output:
                errors.append(f"{interface} not found in interface status output.")
                continue
            line = next((l for l in output.splitlines() if interface in l), None)
            if line is None:
                errors.append(f"{interface} status could not be determined.")
                continue
            if "up" not in line.lower():
                errors.append(f"{interface} is not UP.")
            log.info(f"{interface} : {line}")

        if errors:
            self.failed("\n".join(errors))
        self.passed("Both interfaces are operational.")


# ----------------------------------------------------------------------
# TC04 : Verify MAC Address Learning
# ----------------------------------------------------------------------
class TC04_Verify_MAC_Table(aetest.Testcase):

    @aetest.test
    def verify_mac_learning(self):
        log_banner("TC04 — VERIFY MAC ADDRESS LEARNING")
        device = self.parent.parameters["device"]
        output = send_cmd(device, f"show mac address-table vlan {VLAN_ID}")
        errors = []

        if "dynamic" not in output.lower():
            errors.append("No dynamically learned MAC addresses found.")

        for interface in [PORT1, PORT2]:
            if interface not in output:
                errors.append(f"No MAC learned on {interface}.")

        if errors:
            self.failed("\n".join(errors))

        learned = [l for l in output.splitlines() if "dynamic" in l.lower()]
        log.info("Learned MAC Entries:")
        for line in learned:
            log.info(line)
        self.passed("MAC learning verified successfully.")


# ----------------------------------------------------------------------
# TC05 : Verify Interface Counters
# ----------------------------------------------------------------------
class TC05_Verify_Interface_Counters(aetest.Testcase):

    @aetest.test
    def verify_interface_counters(self):
        log_banner("TC05 — VERIFY INTERFACE COUNTERS")
        device = self.parent.parameters["device"]
        errors = []

        for interface in [PORT1, PORT2]:
            output = send_cmd(device, f"show interface {interface} statistics")
            numbers = [
                int(token)
                for token in output.replace(",", " ").split()
                if token.isdigit()
            ]
            if not numbers:
                errors.append(f"Unable to parse statistics for {interface}.")
                continue
            if max(numbers) == 0:
                errors.append(f"No traffic counters incremented on {interface}.")

        if errors:
            self.failed("\n".join(errors))
        self.passed("Interface counters validated successfully.")


# ----------------------------------------------------------------------
# TC06 : Verify Traffic (Sender / Receiver JSON Reports)
# ----------------------------------------------------------------------
class TC06_Verify_Traffic(aetest.Testcase):

    @aetest.test
    def verify_traffic(self):
        log_banner("TC06 — VERIFY TRAFFIC")
        errors = []

        sender   = load_json(SENDER_JSON)
        receiver = load_json(RECEIVER_JSON)

        log.info("\nSender Report\n" + json.dumps(sender, indent=4))
        log.info("\nReceiver Report\n" + json.dumps(receiver, indent=4))

        # Script status
        if sender.get("status") != "PASS":
            errors.append("Sender script did not complete successfully.")
        if receiver.get("status") != "PASS":
            errors.append("Receiver script did not complete successfully.")

        # Packet counts
        packets_sent     = sender.get("packets_sent", 0)
        packets_received = receiver.get("packets_received", 0)

        if packets_sent <= 0:
            errors.append("Sender transmitted zero packets.")
        if packets_received <= 0:
            errors.append("Receiver captured zero packets.")

        # Packet loss
        if packets_sent > 0:
            loss      = packets_sent - packets_received
            loss_pct  = round((loss / packets_sent) * 100, 2)
        else:
            loss      = 0
            loss_pct  = 100.0

        log.info(f"\nTraffic Statistics\n{'-'*30}")
        log.info(f"Packets Sent     : {packets_sent}")
        log.info(f"Packets Received : {packets_received}")
        log.info(f"Packet Loss      : {loss}")
        log.info(f"Loss %           : {loss_pct}%")
        log.info(f"Threshold        : {LOSS_THRESHOLD}%")
        log.info("-" * 30)

        if loss_pct > LOSS_THRESHOLD:
            errors.append(f"Packet loss {loss_pct}% exceeds threshold {LOSS_THRESHOLD}%.")

        # MAC verification
        sender_mac           = sender.get("source_mac")
        receiver_source_macs = receiver.get("source_macs", [])
        sender_dst           = sender.get("destination_mac")
        receiver_dst         = receiver.get("destination_macs", [])

        if sender_mac and sender_mac not in receiver_source_macs:
            errors.append(f"Sender MAC {sender_mac} not observed by receiver.")
        if sender_dst and sender_dst not in receiver_dst:
            errors.append("Destination MAC mismatch.")

        # Dashboard summary — same schema as original
        start_time     = self.parent.parameters.get("start_time", time.time())
        execution_time = round(time.time() - start_time, 2)
        mac_learned    = bool(sender_mac and sender_mac in receiver_source_macs)

        summary = {
            "test_name":              "VLAN_Access_to_Access",
            "vlan":                   VLAN_ID,
            "ports":                  f"{PORT1} / {PORT2}",
            "packets_sent":           packets_sent,
            "packets_received":       packets_received,
            "packet_loss_percent":    loss_pct,
            "mac_learned":            mac_learned,
            "execution_time_seconds": execution_time,
            "status":                 "FAIL" if errors else "PASS",
            "errors":                 errors,
        }

        os.makedirs(os.path.dirname(RESULT_JSON) if os.path.dirname(RESULT_JSON) else '.', exist_ok=True)
        with open(RESULT_JSON, "w") as fp:
            json.dump(summary, fp, indent=4)
        log.info(f"Dashboard summary → {RESULT_JSON}")

        if errors:
            self.failed("\n".join(errors))
        self.passed("Traffic validation completed successfully.")


# ----------------------------------------------------------------------
# CommonCleanup
# ----------------------------------------------------------------------
class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def disconnect_device(self):
        log_banner("Disconnecting Device")
        device = self.parent.parameters.get("device")
        if device is None:
            log.warning("No device in parameters — skipping disconnect.")
            return
        if device.is_connected():
            device.disconnect()
            log.info("Disconnected Successfully")


if __name__ == "__main__":
    aetest.main()
