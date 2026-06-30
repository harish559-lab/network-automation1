#!/usr/bin/env python3

"""
======================================================================
Job File  : job_vlan_access_access.py

Purpose   :
    Cisco-recommended pyATS job entry point for the Access-to-Access
    VLAN testcase. Jenkins no longer calls the testscript directly;
    it executes this job instead:

        pyats run job jobs/layer2/job_vlan_access_access.py

    The job is responsible for:
        - Pointing pyATS at the testbed file
        - Pointing pyATS at the testscript
        - Passing the shared config file (Phase 4) into the
          testscript as a parameter, so VLAN ID / ports / hosts
          stay in one place instead of being hardcoded twice.

Author : Harish
======================================================================
"""

import os

from pyats.easypy import run


# ----------------------------------------------------------------------
# Paths (resolved relative to this job file, so it works regardless
# of the directory Jenkins invokes `pyats run job` from)
# ----------------------------------------------------------------------
JOB_DIR = os.path.dirname(__file__)

REPO_ROOT = os.path.abspath(
    os.path.join(JOB_DIR, "..", "..")
)

TESTSCRIPT = os.path.join(
    REPO_ROOT, "testcases", "layer2", "test_vlan_access_access.py"
)

TESTBED = os.path.join(
    REPO_ROOT, "testbed", "testbed.yaml"
)

CONFIG_FILE = os.path.join(
    REPO_ROOT, "config", "layer2", "vlan_access_access.yaml"
)


def main(runtime):

    run(
        testscript=TESTSCRIPT,
        testbed=TESTBED,
        runtime=runtime,
        config_file=CONFIG_FILE,
    )
