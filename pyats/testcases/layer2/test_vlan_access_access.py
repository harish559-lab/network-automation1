#!/usr/bin/env python3

"""
======================================================================
Testcase  : test_vlan_access_access.py

Purpose   :
    Validate Access-to-Access VLAN communication on HFCL Switch.

Automation Flow

    Jenkins
        ↓
    Ansible Configuration
        ↓
    Traffic Generation
        ↓
    pyATS Validation
        ↓
    HTML Report

Validation Performed

    ✓ VLAN Exists
    ✓ Access Port Configuration
    ✓ Interface Status
    ✓ MAC Learning
    ✓ Interface Counters
    ✓ Sender / Receiver Statistics

Author : Harish
======================================================================
"""

# ----------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------
# Notice:
#   No Scapy.
#   No Paramiko.
#   No Netmiko.
#   This file is only validation.
# ----------------------------------------------------------------------
import json
import logging
import os
import time

import yaml

from pyats import aetest
from genie.testbed import load


# ----------------------------------------------------------------------
# Logger
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s : %(message)s"
)

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Global Variables
# ----------------------------------------------------------------------
# These become the defaults.
# If tomorrow you automate VLAN 200, only this changes.
# ----------------------------------------------------------------------
SWITCH = "HFCL"

VLAN_ID = "100"

PORT1 = "Gigabitethernet 1/1"

PORT2 = "Gigabitethernet 1/2"

SENDER_JSON = "/tmp/sender_report.json"

RECEIVER_JSON = "/tmp/receiver_report.json"

# Path to the shared YAML config consumed by both Ansible and
# pyATS. Derived from __file__ so it resolves correctly regardless
# of the working directory pyATS easypy runs in.
# Layout: pyats/testcases/layer2/ → ../../.. → repo root → config/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.abspath(
    os.path.join(_SCRIPT_DIR, "..", "..", "..", "config", "layer2", "vlan_access_access.yaml")
)

# Phase 3: structured summary consumed by generate_dashboard.py
# (VLAN, ports, packet counts, loss %, MAC learned, exec time, status)
RESULT_JSON = "/tmp/vlan_access_access_result.json"


# ----------------------------------------------------------------------
# Helper Function 1 : Banner
# ----------------------------------------------------------------------
# Instead of dozens of print("xxxxxxxx") statements, we use
# log_banner("VERIFY VLAN") -- much cleaner.
# ----------------------------------------------------------------------
def log_banner(message):

    log.info("")
    log.info("=" * 70)
    log.info(message)
    log.info("=" * 70)


# ----------------------------------------------------------------------
# Helper Function 2 : Execute CLI
# ----------------------------------------------------------------------
# Every testcase now becomes:
#   output = execute_cli(device, "show vlan brief")
# ----------------------------------------------------------------------
def execute_cli(device, command):
    """
    Execute CLI command on switch.

    Returns
    -------
    str
        Raw CLI Output
    """

    log.info(f"Executing : {command}")

    output = device.execute(command)

    log.info(output)

    return output


# ----------------------------------------------------------------------
# Helper Function 3 : Verify Text
# ----------------------------------------------------------------------
# Later:
#   if verify_output_contains(output, "100"):
#       self.passed()
# instead of `if "100" in output:` everywhere.
# ----------------------------------------------------------------------
def verify_output_contains(output, expected):
    """
    Check whether expected text exists in CLI output.
    """

    return expected in output


# ----------------------------------------------------------------------
# Helper Function 4 : Load JSON
# ----------------------------------------------------------------------
# Later:
#   sender = load_json(SENDER_JSON)
# Very reusable.
# ----------------------------------------------------------------------
def load_json(path):
    """
    Load sender/receiver JSON report.
    """

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"{path} not found."
        )

    with open(path) as fp:

        return json.load(fp)


# ----------------------------------------------------------------------
# Helper Function 5 : Load YAML Config
# ----------------------------------------------------------------------
# Reads the shared testcase config (Phase 4). Same file is also
# consumed by the Ansible playbook, so VLAN ID, ports, hosts,
# etc. only ever live in one place.
# ----------------------------------------------------------------------
def load_yaml(path):
    """
    Load shared YAML config (used by both Ansible and pyATS).
    """

    if not os.path.exists(path):

        raise FileNotFoundError(
            f"{path} not found."
        )

    with open(path) as fp:

        return yaml.safe_load(fp)


# ----------------------------------------------------------------------
# CommonSetup
# ----------------------------------------------------------------------
# Notice:
#   We're storing `device` inside self.parent.parameters
#   Every testcase will automatically use it. No reconnecting.
# ----------------------------------------------------------------------
class CommonSetup(aetest.CommonSetup):

    @aetest.subsection
    def load_config(self, config_file=CONFIG_FILE):
        """
        Load the shared YAML config (Phase 4) and override the
        module-level defaults (VLAN_ID, PORT1, PORT2, SENDER_JSON,
        RECEIVER_JSON, etc).

        `config_file` can be overridden per-run from the job file:

            run(
                testscript="testcases/layer2/test_vlan_access_access.py",
                testbed="testbed/testbed.yaml",
                config_file="config/layer2/vlan_access_access.yaml"
            )

        Every testcase below keeps referencing the same globals
        (VLAN_ID, PORT1, PORT2 ...) untouched -- only their values
        change, so no testcase code needs to be rewritten.
        """

        log_banner("Loading Shared Config")

        global SWITCH, VLAN_ID, PORT1, PORT2, SENDER_JSON, RECEIVER_JSON

        config = load_yaml(config_file)

        SWITCH = config.get("switch_name", SWITCH)

        VLAN_ID = str(config.get("vlan_id", VLAN_ID))

        PORT1 = config.get("access_port1", PORT1)

        PORT2 = config.get("access_port2", PORT2)

        SENDER_JSON = config.get("sender_report", SENDER_JSON)

        RECEIVER_JSON = config.get("receiver_report", RECEIVER_JSON)

        self.parent.parameters["config"] = config

        log.info(f"Config Loaded From : {config_file}")
        log.info(f"SWITCH   : {SWITCH}")
        log.info(f"VLAN_ID  : {VLAN_ID}")
        log.info(f"PORT1    : {PORT1}")
        log.info(f"PORT2    : {PORT2}")

    @aetest.subsection
    def connect_to_device(self, testbed):

        log_banner("Connecting to Switch")

        self.parent.parameters["start_time"] = time.time()

        self.parent.parameters["device"] = testbed.devices[SWITCH]

        device = self.parent.parameters["device"]

        device.connect()

        log.info("Connected Successfully")


# ----------------------------------------------------------------------
# TC01 : Verify VLAN
# ----------------------------------------------------------------------
class TC01_Verify_VLAN(aetest.Testcase):

    @aetest.test
    def verify_vlan_exists(self):

        log_banner("TC01 - VERIFY VLAN EXISTS")

        device = self.parent.parameters["device"]

        output = execute_cli(
            device,
            "show vlan brief"
        )

        if verify_output_contains(output, VLAN_ID):

            log.info(f"VLAN {VLAN_ID} exists.")

            self.passed(
                f"VLAN {VLAN_ID} found successfully."
            )

        else:

            self.failed(
                f"VLAN {VLAN_ID} not found."
            )


# ----------------------------------------------------------------------
# TC02 : Verify Access Port Configuration
# ----------------------------------------------------------------------
class TC02_Verify_Interface_Config(aetest.Testcase):

    @aetest.test
    def verify_access_port_configuration(self):

        log_banner("TC02 - VERIFY ACCESS PORT CONFIGURATION")

        device = self.parent.parameters["device"]

        interfaces = [PORT1, PORT2]

        errors = []

        for interface in interfaces:

            output = execute_cli(
                device,
                f"show running-config interface {interface}"
            )

            checks = [
                ("switchport mode access",
                 f"{interface} is not configured as an access port."),

                (f"switchport access vlan {VLAN_ID}",
                 f"{interface} is not assigned to VLAN {VLAN_ID}."),

                ("no shutdown",
                 f"{interface} is administratively down.")
            ]

            for expected, error_msg in checks:

                if expected not in output:

                    errors.append(error_msg)

        if errors:

            self.failed("\n".join(errors))

        log.info("Both interfaces are correctly configured.")

        self.passed()


# ----------------------------------------------------------------------
# TC03 : Verify Interface Link Status
# ----------------------------------------------------------------------
class TC03_Verify_Link_Status(aetest.Testcase):

    @aetest.test
    def verify_link_status(self):

        log_banner("TC03 - VERIFY INTERFACE LINK STATUS")

        device = self.parent.parameters["device"]

        output = execute_cli(
            device,
            "show interface status"
        )

        errors = []

        interfaces = [PORT1, PORT2]

        for interface in interfaces:

            if interface not in output:

                errors.append(f"{interface} not found in interface status output.")

                continue

            line = next(
                (l for l in output.splitlines() if interface in l),
                None
            )

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

        log_banner("TC04 - VERIFY MAC ADDRESS LEARNING")

        device = self.parent.parameters["device"]

        output = execute_cli(
            device,
            f"show mac address-table vlan {VLAN_ID}"
        )

        errors = []

        if "dynamic" not in output.lower():

            errors.append("No dynamically learned MAC addresses found.")

        interfaces = [PORT1, PORT2]

        for interface in interfaces:

            if interface not in output:

                errors.append(
                    f"No MAC learned on {interface}."
                )

        if errors:

            self.failed("\n".join(errors))

        learned = [
            line for line in output.splitlines()
            if "dynamic" in line.lower()
        ]

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

        log_banner("TC05 - VERIFY INTERFACE COUNTERS")

        device = self.parent.parameters["device"]

        errors = []

        interfaces = [PORT1, PORT2]

        for interface in interfaces:

            output = execute_cli(
                device,
                f"show interface statistics {interface}"
            )

            log.info(f"\nStatistics for {interface}\n")

            log.info(output)

            numbers = []

            for token in output.replace(",", " ").split():

                if token.isdigit():

                    numbers.append(int(token))

            if not numbers:

                errors.append(
                    f"Unable to parse statistics for {interface}."
                )

                continue

            if max(numbers) == 0:

                errors.append(
                    f"No traffic counters incremented on {interface}."
                )

        if errors:

            self.failed("\n".join(errors))

        self.passed("Interface counters validated successfully.")


# ----------------------------------------------------------------------
# TC06 : Verify Traffic (Sender / Receiver JSON Reports)
# ----------------------------------------------------------------------
class TC06_Verify_Traffic(aetest.Testcase):

    @aetest.test
    def verify_traffic(self):

        log_banner("TC06 - VERIFY TRAFFIC")

        errors = []

        # -------------------------------------------------
        # Load JSON Reports
        # -------------------------------------------------

        sender = load_json(SENDER_JSON)

        receiver = load_json(RECEIVER_JSON)

        log.info("\nSender Report")

        log.info(json.dumps(sender, indent=4))

        log.info("\nReceiver Report")

        log.info(json.dumps(receiver, indent=4))

        # -------------------------------------------------
        # Verify Script Status
        # -------------------------------------------------

        if sender.get("status") != "PASS":

            errors.append("Sender script did not complete successfully.")

        if receiver.get("status") != "PASS":

            errors.append("Receiver script did not complete successfully.")

        # -------------------------------------------------
        # Verify Packet Counts
        # -------------------------------------------------

        packets_sent = sender.get("packets_sent", 0)

        packets_received = receiver.get("packets_received", 0)

        if packets_sent <= 0:

            errors.append("Sender transmitted zero packets.")

        if packets_received <= 0:

            errors.append("Receiver captured zero packets.")

        # -------------------------------------------------
        # Packet Loss Calculation
        # -------------------------------------------------

        if packets_sent > 0:

            packet_loss = packets_sent - packets_received

            packet_loss_percent = round(
                (packet_loss / packets_sent) * 100,
                2
            )

        else:

            packet_loss = packets_sent

            packet_loss_percent = 100

        log.info("")
        log.info("Traffic Statistics")
        log.info("------------------------------")
        log.info(f"Packets Sent     : {packets_sent}")
        log.info(f"Packets Received : {packets_received}")
        log.info(f"Packet Loss      : {packet_loss}")
        log.info(f"Loss Percentage  : {packet_loss_percent}%")
        log.info("------------------------------")

        # Allow 1% packet loss

        if packet_loss_percent > 1:

            errors.append(
                f"Packet loss exceeded threshold ({packet_loss_percent}%)."
            )

        # -------------------------------------------------
        # Verify MAC Addresses
        # -------------------------------------------------

        sender_mac = sender.get("source_mac")

        receiver_source_macs = receiver.get(
            "source_macs",
            []
        )

        if sender_mac not in receiver_source_macs:

            errors.append(
                f"Sender MAC {sender_mac} not observed by receiver."
            )

        sender_dst = sender.get("destination_mac")

        receiver_dst = receiver.get(
            "destination_macs",
            []
        )

        if sender_dst not in receiver_dst:

            errors.append(
                "Destination MAC mismatch."
            )

        # -------------------------------------------------
        # Phase 3 : Write Dashboard Summary
        # -------------------------------------------------
        # Structured data for generate_dashboard.py -- avoids
        # scraping pyATS logs for the table columns (VLAN,
        # Ports, Packets Sent/Received, Loss %, MAC Learned,
        # Execution Time, PASS/FAIL).
        # -------------------------------------------------

        start_time = self.parent.parameters.get("start_time", time.time())

        execution_time = round(time.time() - start_time, 2)

        mac_learned = (
            sender_mac in receiver_source_macs
            if sender_mac else False
        )

        summary = {

            "test_name": "VLAN_Access_to_Access",

            "vlan": VLAN_ID,

            "ports": f"{PORT1} / {PORT2}",

            "packets_sent": packets_sent,

            "packets_received": packets_received,

            "packet_loss_percent": packet_loss_percent,

            "mac_learned": mac_learned,

            "execution_time_seconds": execution_time,

            "status": "FAIL" if errors else "PASS",

            "errors": errors,

        }

        with open(RESULT_JSON, "w") as fp:

            json.dump(summary, fp, indent=4)

        log.info(f"Dashboard summary written to {RESULT_JSON}")

        # -------------------------------------------------
        # Final Result
        # -------------------------------------------------

        if errors:

            log.error("\nTraffic Validation Failed")

            for err in errors:

                log.error(err)

            self.failed("\n".join(errors))

        self.passed("Traffic validation completed successfully.")


# ----------------------------------------------------------------------
# CommonCleanup
# ----------------------------------------------------------------------
class CommonCleanup(aetest.CommonCleanup):

    @aetest.subsection
    def disconnect_device(self):

        log_banner("Disconnecting Device")

        device = self.parent.parameters["device"]

        if device.is_connected():

            device.disconnect()

            log.info("Disconnected Successfully")


# ----------------------------------------------------------------------
# Main Entry Point
# ----------------------------------------------------------------------
if __name__ == "__main__":

    aetest.main()
