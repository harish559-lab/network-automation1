"""
MVRP Test Cases — Stub
Follow the pattern in test_mac.py / test_vlan.py / test_rstp.py.
All IPs and interfaces come from lib/config_loader.py — nothing hardcoded here.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from pyats import aetest
from lib.common import connect_devices, disconnect_all

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        pass  # replace with connect_devices() calls

class TC_Stub(aetest.Testcase):
    """Expand with MVRP test cases."""
    @aetest.test
    def placeholder(self):
        self.passed("Stub — implement test cases here")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        disconnect_all(testbed)
