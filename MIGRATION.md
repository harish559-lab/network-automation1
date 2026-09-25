# Migration Guide — Old Structure → New Structure

## What to do on your machine

### 1. Copy the new files INTO your existing ~/Documents/network-automation/

Do NOT delete your existing folder. Just copy these new files over:

```
network-automation/          ← your existing folder
├── config/
│   └── lab_config.yaml      ← NEW (replaces testbed.yaml + vlan_access_access.yaml + hosts.ini)
├── lib/                     ← NEW folder
│   ├── config_loader.py
│   ├── common.py            ← absorbs scripts/switch_cmd.py
│   ├── testbed_generator.py ← replaces pyats/testbed.yaml
│   └── ansible_inventory.py ← replaces ansible/inventory/hosts.ini
├── tests/                   ← NEW folder (replaces pyats/testcases/)
│   ├── 01_mac/
│   │   └── test_mac.py
│   ├── 02_vlan/
│   │   ├── test_vlan_access_access.py   ← migrated from pyats/testcases/layer2/
│   │   └── test_vlan.py
│   ├── 03_rstp/ ... 14_scalability/     ← stubs, fill these in
├── jobs/
│   └── l2_full_job.py       ← replaces pyats/jobs/layer2/job_vlan_access_access.py
└── run.sh                   ← single launcher for everything
```

### 2. KEEP these files exactly as they are:
- `scripts/traffic_sender.py`    → unchanged
- `scripts/traffic_receiver.py`  → unchanged
- `scripts/generate_dashboard.py` → just update RESULT_JSON path if needed
- `ansible/playbooks/layer2/*.yml` → update `hosts:` to `switches` if not already
- `reports/dashboard.html`       → unchanged
- `Jenkinsfile`                  → update paths (see below)
- `requirements.txt`             → keep, add `pyyaml` if not there

### 3. DELETE these after migration is confirmed working:
- `pyats/testbed.yaml`                              → replaced by testbed_generator.py
- `config/layer2/vlan_access_access.yaml`           → merged into lab_config.yaml
- `ansible/inventory/hosts.ini`                     → auto-generated now
- `ansible/inventory/group_vars/switches.yml`       → auto-generated now
- `scripts/switch_cmd.py`                           → absorbed into lib/common.py

### 4. Migrate your other MAC test scripts

Your 3 MAC scripts follow the same pattern. At the top, replace:

```python
# OLD — hardcoded
SWITCH = "HFCL"
VLAN_ID = "10"
PORT1 = "Gigabitethernet 1/1"
```

```python
# NEW — from config
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from lib.config_loader import dev, intf, vlan, timer
from lib.common import send_cmd, connect_devices, log_banner

SWITCH  = 'HFCL'
VLAN_ID = str(vlan('test_vlan_1'))
PORT1   = intf('HFCL', 'access_port_1')
PORT2   = intf('HFCL', 'access_port_2')
```

Then move the migrated script to `tests/01_mac/test_mac_aging.py` etc.

### 5. Update Jenkinsfile

```groovy
// OLD
sh 'pyats run job pyats/jobs/layer2/job_vlan_access_access.py --testbed pyats/testbed.yaml'

// NEW
sh 'python lib/testbed_generator.py'
sh 'python lib/ansible_inventory.py'
sh 'pyats run job jobs/l2_full_job.py --groups vlan'
```

### 6. First run to verify

```bash
cd ~/Documents/network-automation

# Sanity check config
python lib/config_loader.py

# Generate testbeds
python lib/testbed_generator.py

# Run your existing VLAN test
./run.sh --tc tests/02_vlan/test_vlan_access_access.py
```

## The rule going forward

**Only ever edit `config/lab_config.yaml`.**  
IP changed? Edit `lab_config.yaml`. New VLAN? Edit `lab_config.yaml`.  
New port? Edit `lab_config.yaml`. Everything else updates automatically.
