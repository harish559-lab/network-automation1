#!/usr/bin/env bash
# =============================================================================
# run.sh — HFCL L2 Automation Launcher
# =============================================================================
set -e
cd "$(dirname "$0")"

GROUP=""
TC=""
GENERATE_ONLY=false

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --group)         GROUP="$2"; shift ;;
        --tc)            TC="$2";    shift ;;
        --generate-only) GENERATE_ONLY=true ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
    shift
done

echo "============================================================"
echo "  HFCL L2 Automation"
echo "============================================================"

echo ""
echo "► Generating testbeds from config/lab_config.yaml ..."
python3 lib/testbed_generator.py

echo ""
echo "► Generating Ansible inventory ..."
python3 lib/ansible_inventory.py

$GENERATE_ONLY && { echo "Done (--generate-only)."; exit 0; }

echo ""
if [[ -n "$TC" ]]; then
    # Auto-pick testbed based on script name
    if echo "$TC" | grep -qiE "erps|mstp"; then
        TB="testbeds/testbed_ring.yaml"
    elif echo "$TC" | grep -qiE "rstp|lag|oam|mvrp|qinq"; then
        TB="testbeds/testbed_dual.yaml"
    else
        TB="testbeds/testbed_single.yaml"
    fi

    # Absolute paths
    ABS_TC="$(cd "$(dirname "$TC")" && pwd)/$(basename "$TC")"
    ABS_TB="$(cd "$(dirname "$TB")" && pwd)/$(basename "$TB")"

    echo "► Running: $TC"
    echo "  Testbed : $ABS_TB"

    # Use pyats run job with --testbed-file — pyATS loads and injects
    # the Testbed object automatically into each subsection that needs it
    TMPJOB=$(mktemp /tmp/pyats_job_XXXXXX.py)
    cat > "$TMPJOB" << JOBEOF
def main(runtime):
    runtime.tasks.run(
        testscript="$ABS_TC",
    )
JOBEOF
    pyats run job "$TMPJOB" --testbed-file "$ABS_TB"
    rm -f "$TMPJOB"

elif [[ -n "$GROUP" ]]; then
    echo "► Running group(s): $GROUP"
    pyats run job jobs/l2_full_job.py --groups $GROUP

else
    echo "► Running ALL test cases ..."
    pyats run job jobs/l2_full_job.py
fi

echo ""
echo "============================================================"
echo "  Done."
echo "============================================================"
