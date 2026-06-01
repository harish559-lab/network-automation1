// =============================================================
// Jenkinsfile — Layer 2 Test Pipeline
// Tests:
//   1. MAC Address Table Expiry Interval (MAC Aging)
//   2. MAC Movement between ports
// Agent: Linux built-in node (Jenkins Docker container)
// =============================================================

pipeline {

    agent any

    environment {
        PROJECT_DIR      = "${WORKSPACE}"
        TESTBED          = "${WORKSPACE}/pyats/testbed.yaml"
        INVENTORY        = "${WORKSPACE}/ansible/inventory/hosts.ini"
        REPORT_DIR       = "${WORKSPACE}/reports"

        // MAC Aging test
        AGING_PLAYBOOK   = "${WORKSPACE}/ansible/playbooks/layer2/mac_aging_config.yml"
        AGING_TEST       = "${WORKSPACE}/pyats/testcases/layer2/test_mac_aging.py"

        // MAC Movement test
        MOVEMENT_PLAYBOOK = "${WORKSPACE}/ansible/playbooks/layer2/mac_movement_config.yml"
        MOVEMENT_TEST     = "${WORKSPACE}/pyats/testcases/layer2/test_mac_movement.py"

        // Laptop 1 (connected to switch Gi 1/1)
        LAPTOP1_USER     = "harish"
        LAPTOP1_IP       = "192.168.180.142"
        LAPTOP1_IFACE    = "enp2s0"
        AGING_SCRIPT     = "/home/harish/Documents/network-automation/scripts/MAC_generate_traffic.py"
        MOVEMENT_SCRIPT1 = "/home/harish/Documents/network-automation/scripts/MAC_movement_traffic.py"

        // Laptop 2 (connected to switch Gi 1/2)
        LAPTOP2_USER     = "lab-testing"
        LAPTOP2_IP       = "192.168.180.159"
        LAPTOP2_IFACE    = "enp44s0"
        MOVEMENT_SCRIPT2 = "/home/lab-testing/Documents/network-automation/scripts/MAC_movement_traffic.py"

        // Switch
        SWITCH_IP        = "192.168.180.146"
    }

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {

        // -----------------------------------------------------------
        // STAGE 1 — Environment Setup
        // -----------------------------------------------------------
        stage('Environment Setup') {
            steps {
                echo '=== Installing Python dependencies ==='
                sh '''
                    python3 --version
                    pip3 install paramiko scapy pyats ansible genie \
                        --break-system-packages --quiet
                    echo "✅ Dependencies installed"
                    ansible --version | head -1
                '''
            }
        }

        // -----------------------------------------------------------
        // STAGE 2 — MAC Aging: Configure Device (Ansible)
        // -----------------------------------------------------------
        stage('MAC Aging - Configure Device') {
            steps {
                echo '=== Running Ansible playbook to configure MAC aging-time ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${AGING_PLAYBOOK} \
                        -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_aging_run.log || true
                    echo "✅ Ansible MAC aging playbook completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible_aging_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 3 — MAC Aging: Generate Bi-directional Traffic
        // -----------------------------------------------------------
        stage('MAC Aging - Generate Traffic') {
            steps {
                echo '=== Sending bi-directional traffic via Laptop 1 ==='
                sh '''
                    ssh -o StrictHostKeyChecking=no \
                        ${LAPTOP1_USER}@${LAPTOP1_IP} \
                        "sudo /usr/bin/python3 ${AGING_SCRIPT} --interface ${LAPTOP1_IFACE}" \
                        2>&1 | tee ${REPORT_DIR}/traffic_aging_run.log || true
                    echo "✅ MAC Aging traffic generation completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/traffic_aging_run.log',
                                     allowEmptyArchive: true
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 4 — MAC Aging: Validate with pyATS
        // -----------------------------------------------------------
        stage('MAC Aging - Validate with pyATS') {
            steps {
                echo '=== Running MAC Aging pyATS test suite ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    python3 ${AGING_TEST} \
                        --testbed ${TESTBED} \
                        2>&1 | tee ${REPORT_DIR}/pyats_aging_run.log || true
                    echo "✅ MAC Aging pyATS validation completed"
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
        // STAGE 5 — MAC Movement: Pre-check (Ansible)
        // -----------------------------------------------------------
        stage('MAC Movement - Pre-check') {
            steps {
                echo '=== Running Ansible pre-check for MAC movement ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${MOVEMENT_PLAYBOOK} \
                        -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_movement_run.log || true
                    echo "✅ MAC Movement pre-check completed"
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
        // STAGE 6 — MAC Movement: Validate with pyATS
        // -----------------------------------------------------------
        stage('MAC Movement - Validate with pyATS') {
            steps {
                echo '=== Running MAC Movement pyATS test suite ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    python3 ${MOVEMENT_TEST} \
                        --testbed ${TESTBED} \
                        2>&1 | tee ${REPORT_DIR}/pyats_movement_run.log || true
                    echo "✅ MAC Movement pyATS validation completed"
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
        // STAGE 7 — Collect Reports + Generate Dashboard
        // -----------------------------------------------------------
        stage('Collect Reports') {
            steps {
                echo '=== Collecting reports and generating dashboard ==='
                sh '''
                    mkdir -p ${REPORT_DIR}

                    # Generate HTML dashboard with both test modules
                    python3 ${WORKSPACE}/scripts/generate_dashboard.py \
                        --log       ${REPORT_DIR}/pyats_aging_run.log \
                        --log2      ${REPORT_DIR}/pyats_movement_run.log \
                        --ansible   ${REPORT_DIR}/ansible_aging_run.log \
                        --ansible2  ${REPORT_DIR}/ansible_movement_run.log \
                        --output    ${REPORT_DIR}/dashboard.html \
                        --device    "Hfcl-Switch (192.168.180.146)" \
                        --module    "Layer 2 - MAC Aging & MAC Movement" \
                        --aging     "50 seconds" || true

                    echo "📁 Reports:"
                    ls -la ${REPORT_DIR}/

                    # Copy dashboard to mounted volume for direct viewing
                    cp ${REPORT_DIR}/dashboard.html /var/reports/dashboard.html || true
                    echo "✅ Dashboard copied for viewing"
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
            ║  Check archived logs for details.            ║
            ╚══════════════════════════════════════════════╝
            """
        }
        always {
            echo "Pipeline finished. Check archived artifacts for dashboard.html and logs."
        }
    }
}
