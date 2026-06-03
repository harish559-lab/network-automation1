import re
import json

from pyats import aetest


def get_mac_count(output):

    match = re.search(
        r"Total learned dynamic addresses for the switch:\s+(\d+)", output
    )

    if match:
        return int(match.group(1))

    return 0


class MacMaxLearning(aetest.Testcase):
    @aetest.test
    def verify_mac_learning(self, testbed):

        device = testbed.devices["DUT"]

        output = device.execute("show mac address-table count")

        learned_macs = get_mac_count(output)

        expected_macs = 5000

        result = {}

        result["expected_macs"] = expected_macs
        result["learned_macs"] = learned_macs

        if learned_macs >= expected_macs:

            result["result"] = "PASS"

        else:

            result["result"] = "FAIL"

        with open("reports/results.json", "w") as f:

            json.dump(result, f, indent=4)

        if result["result"] == "FAIL":

            self.failed(f"Expected {expected_macs} " f"Learned {learned_macs}")
