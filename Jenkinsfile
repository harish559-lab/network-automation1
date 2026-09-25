// =============================================================
// Jenkinsfile — Layer 2 Test Pipeline
// =============================================================
// Structure:
//   config/lab_config.yaml  ← single source of truth (IPs, ports, VLANs)
//   lib/testbed_generator.py ← auto-generates testbeds/
//   lib/ansible_inventory.py ← auto-generates inventory + config shim
//   jobs/l2_full_job.py      ← master pyATS job (all 104 TCs)
//
// Flow per test group:
//   Generate Config → Ansible Configure → Traffic → pyATS Validate → Dashboard
// =============================================================

pipeline {

    agent any

    environment {
        PROJECT_DIR = "${WORKSPACE}"
        VENV        = "${WORKSPACE}/networkvenv"
        REPORT_DIR  = "${WORKSPACE}/reports"

        // ── Generated automatically — never edit these paths directly ──
        TESTBED_SINGLE   = "${WORKSPACE}/testbeds/testbed_single.yaml"
        TESTBED_DUAL     = "${WORKSPACE}/testbeds/testbed_dual.yaml"
        INVENTORY        = "${WORKSPACE}/ansible/inventory/hosts.ini"

        // ── Ansible playbooks ──────────────────────────────────────────
        VLAN_AA_PLAYBOOK  = "${WORKSPACE}/ansible/playbooks/layer2/vlan_access_access.yml"
        AGING_PLAYBOOK    = "${WORKSPACE}/ansible/playbooks/layer2/mac_aging_config.yml"
        MOVEMENT_PLAYBOOK = "${WORKSPACE}/ansible/playbooks/layer2/mac_movement_config.yml"

        // ── pyATS job file (runs all test groups) ─────────────────────
        L2_JOB = "${WORKSPACE}/jobs/l2_full_job.py"

        // ── Traffic scripts (paths on the remote machines) ────────────
        AGING_SCRIPT     = "/home/harish/Documents/network-automation/scripts/MAC_generate_traffic.py"
        MOVEMENT_SCRIPT1 = "/home/harish/Documents/network-automation/scripts/MAC_movement_traffic.py"
        MOVEMENT_SCRIPT2 = "/home/lab-testing/Documents/network-automation/scripts/MAC_movement_traffic.py"
    }

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // -----------------------------------------------------------
        // STAGE 1 — Environment Setup
        // Activate venv, install deps, generate testbeds + inventory
        // from lab_config.yaml — everything else reads from those files
        // -----------------------------------------------------------
        stage('Environment Setup') {
            steps {
                echo '=== Setting up environment ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8

                    # Activate venv
                    . ${VENV}/bin/activate

                    python3 --version
                    pip install paramiko pyats genie pyyaml ansible \
                        --quiet --timeout 120 || true

                    echo ""
                    echo "=== Generating testbeds from lab_config.yaml ==="
                    python3 ${PROJECT_DIR}/lib/testbed_generator.py

                    echo ""
                    echo "=== Generating Ansible inventory + config shim ==="
                    python3 ${PROJECT_DIR}/lib/ansible_inventory.py

                    echo ""
                    echo "=== Generated files ==="
                    ls -la ${PROJECT_DIR}/testbeds/
                    ls -la ${PROJECT_DIR}/ansible/inventory/
                    ls -la ${PROJECT_DIR}/config/layer2/

                    echo "✅ Environment ready"
                '''
            }
        }

        // -----------------------------------------------------------
        // STAGE 2 — MAC Aging: Configure + Traffic
        // -----------------------------------------------------------
        stage('MAC Aging - Configure & Traffic') {
            steps {
                echo '=== MAC Aging: Ansible configure ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${AGING_PLAYBOOK} -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_aging_run.log || true

                    echo "=== Generating MAC Aging traffic ==="
                    ssh -o StrictHostKeyChecking=no harish@192.168.89.65 \
                        "sudo python3 ${AGING_SCRIPT} --interface enp2s0" \
                        2>&1 | tee ${REPORT_DIR}/traffic_aging_run.log || true

                    echo "✅ MAC Aging configure + traffic done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible_aging_run.log,reports/traffic_aging_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 3 — MAC Aging: Validate with pyATS
        // -----------------------------------------------------------
        stage('MAC Aging - Validate') {
            steps {
                echo '=== MAC Aging: pyATS validation ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    # Generate temp job file — pyats run job injects testbed correctly
                    cat > /tmp/pyats_mac_aging_job.py << JOBEOF
def main(runtime):
    runtime.tasks.run(
        testscript="${PROJECT_DIR}/tests/01_mac/test_mac_aging.py",
    )
JOBEOF

                    pyats run job /tmp/pyats_mac_aging_job.py \
                        --testbed-file ${TESTBED_SINGLE} \
                        2>&1 | tee ${REPORT_DIR}/pyats_aging_run.log || true

                    echo "✅ MAC Aging pyATS validation done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/pyats_aging_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 4 — MAC Movement: Configure + Traffic
        // -----------------------------------------------------------
        stage('MAC Movement - Configure & Traffic') {
            steps {
                echo '=== MAC Movement: Ansible configure ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${MOVEMENT_PLAYBOOK} -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_movement_run.log || true

                    echo "✅ MAC Movement configure done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible_movement_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 5 — MAC Movement: Validate with pyATS
        // -----------------------------------------------------------
        stage('MAC Movement - Validate') {
            steps {
                echo '=== MAC Movement: pyATS validation ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    cat > /tmp/pyats_mac_movement_job.py << JOBEOF
def main(runtime):
    runtime.tasks.run(
        testscript="${PROJECT_DIR}/tests/01_mac/test_mac_movement.py",
    )
JOBEOF

                    pyats run job /tmp/pyats_mac_movement_job.py \
                        --testbed-file ${TESTBED_SINGLE} \
                        2>&1 | tee ${REPORT_DIR}/pyats_movement_run.log || true

                    echo "✅ MAC Movement pyATS validation done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/pyats_movement_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 6 — VLAN Access-Access: Configure + Traffic
        // Ansible playbook handles both switch config AND traffic
        // (receiver start, sender run, report copy) in one shot
        // -----------------------------------------------------------
        stage('VLAN Access-Access - Configure & Traffic') {
            steps {
                echo '=== VLAN Access-Access: Ansible configure + traffic ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${VLAN_AA_PLAYBOOK} -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_vlan_aa_run.log || true

                    echo "✅ VLAN Access-Access configure + traffic done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible_vlan_aa_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 7 — VLAN Access-Access: Validate with pyATS
        // -----------------------------------------------------------
        stage('VLAN Access-Access - Validate') {
            steps {
                echo '=== VLAN Access-Access: pyATS validation ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    cat > /tmp/pyats_vlan_aa_job.py << JOBEOF
def main(runtime):
    runtime.tasks.run(
        testscript="${PROJECT_DIR}/tests/02_vlan/test_vlan_access_access.py",
    )
JOBEOF

                    pyats run job /tmp/pyats_vlan_aa_job.py \
                        --testbed-file ${TESTBED_SINGLE} \
                        2>&1 | tee ${REPORT_DIR}/pyats_vlan_aa_run.log || true

                    echo "✅ VLAN Access-Access pyATS validation done"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/pyats_vlan_aa_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 8 — Generate Dashboard
        // -----------------------------------------------------------
        stage('Generate Dashboard') {
            steps {
                echo '=== Collecting reports and generating dashboard ==='
                sh '''
                    set -e
                    export LANG=en_US.UTF-8
                    export LC_ALL=en_US.UTF-8
                    . ${VENV}/bin/activate
                    mkdir -p ${REPORT_DIR}

                    # Copy structured result JSON from /tmp
                    cp /tmp/vlan_access_access_result.json \
                        ${REPORT_DIR}/vlan_access_access_result.json || true

                    # Generate HTML dashboard
                    python3 ${PROJECT_DIR}/scripts/generate_dashboard.py \
                        --log         ${REPORT_DIR}/pyats_aging_run.log \
                        --log2        ${REPORT_DIR}/pyats_movement_run.log \
                        --log3        ${REPORT_DIR}/pyats_vlan_aa_run.log \
                        --ansible     ${REPORT_DIR}/ansible_aging_run.log \
                        --ansible2    ${REPORT_DIR}/ansible_movement_run.log \
                        --ansible3    ${REPORT_DIR}/ansible_vlan_aa_run.log \
                        --result-json ${REPORT_DIR}/vlan_access_access_result.json \
                        --output      ${REPORT_DIR}/dashboard.html \
                        --device      "HFCL Switch (192.168.89.61)" \
                        --module      "Layer 2 - MAC Aging, MAC Movement, VLAN Access-Access" \
                        --aging       "50 seconds" || true

                    echo ""
                    echo "=== Reports ==="
                    ls -la ${REPORT_DIR}/

                    # Copy dashboard for direct viewing (if mounted)
                    cp ${REPORT_DIR}/dashboard.html /var/reports/dashboard.html || true

                    echo "✅ Dashboard generated"
                '''
                archiveArtifacts artifacts: 'reports/**/*',
                                 allowEmptyArchive: true
            }
        }
    }

    post {
        success {
            echo """
╔══════════════════════════════════════════════╗
║  ✅  PIPELINE PASSED                         ║
║  Layer 2 Tests : PASS                        ║
╚══════════════════════════════════════════════╝
            """
        }
        failure {
            echo """
╔══════════════════════════════════════════════╗
║  ❌  PIPELINE FAILED                         ║
║  Check archived logs in Build Artifacts.     ║
╚══════════════════════════════════════════════╝
            """
        }
        always {
            echo "Pipeline finished. Check archived artifacts for dashboard.html and all logs."
        }
    }
}
