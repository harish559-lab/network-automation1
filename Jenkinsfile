// =============================================================
// Jenkinsfile — MAC Address Table Expiry Interval Test Pipeline
// Agent       : Linux built-in node (Jenkins Docker container)
// =============================================================

pipeline {

    agent any

    environment {
        PROJECT_DIR    = "${WORKSPACE}"
        TESTBED        = "${WORKSPACE}/pyats/testbed.yaml"
        PLAYBOOK       = "${WORKSPACE}/ansible/playbooks/layer2/mac_aging_config.yml"
        INVENTORY      = "${WORKSPACE}/ansible/inventory/hosts.ini"
        PYATS_TEST     = "${WORKSPACE}/pyats/testcases/layer2/test_mac_aging.py"
        REPORT_DIR     = "${WORKSPACE}/reports"
        LOCAL_MACHINE  = "192.168.180.95"       // your local machine IP
        LOCAL_USER     = "harish"
        TRAFFIC_SCRIPT = "/home/harish/Documents/network-automation/scripts/MAC_generate_traffic.py"
        TRAFFIC_IFACE  = "enp2s0"
    }

    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
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
        // STAGE 2 — Ansible: Configure MAC Aging Time on Switch
        // -----------------------------------------------------------
        stage('Configure Device (Ansible)') {
            steps {
                echo '=== Running Ansible playbook to configure MAC aging-time ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${PLAYBOOK} \
                        -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_run.log
                    echo "✅ Ansible playbook completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/ansible_run.log',
                                     allowEmptyArchive: true
                }
                failure {
                    echo '❌ Ansible configuration FAILED'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 3 — Traffic Generation
        // Run on LOCAL MACHINE (192.168.180.95) via SSH
        // because Jenkins Docker has no enp2s0 interface
        // -----------------------------------------------------------
        stage('Generate Bi-directional Traffic') {
            steps {
                echo '=== Sending bi-directional traffic via local machine ==='
                sh '''
                    ssh -o StrictHostKeyChecking=no \
                        ${LOCAL_USER}@${LOCAL_MACHINE} \
                        "sudo python3 ${TRAFFIC_SCRIPT} --interface ${TRAFFIC_IFACE}" \
                        2>&1 | tee ${REPORT_DIR}/traffic_run.log
                    echo "✅ Traffic generation completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/traffic_run.log',
                                     allowEmptyArchive: true
                }
                failure {
                    echo '❌ Traffic generation FAILED'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 4 — pyATS Validation
        // -----------------------------------------------------------
        stage('Validate with pyATS') {
            steps {
                echo '=== Running pyATS test suite ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    python3 ${PYATS_TEST} \
                        --testbed ${TESTBED} \
                        2>&1 | tee ${REPORT_DIR}/pyats_run.log
                    echo "✅ pyATS validation completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/pyats_run.log',
                                     allowEmptyArchive: true
                }
                failure {
                    echo '❌ pyATS validation FAILED'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 5 — Collect Reports + Generate Dashboard
        // -----------------------------------------------------------
        stage('Collect Reports') {
            steps {
                echo '=== Collecting reports and generating dashboard ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    [ -f /tmp/mac_expiry_test_report.txt ] && \
                        cp /tmp/mac_expiry_test_report.txt ${REPORT_DIR}/ || true
                    [ -f /tmp/mac_table_snapshot.txt ] && \
                        cp /tmp/mac_table_snapshot.txt ${REPORT_DIR}/ || true

                    # Generate HTML dashboard from pyATS log
                    python3 ${WORKSPACE}/scripts/generate_dashboard.py \
                        --log  ${REPORT_DIR}/pyats_run.log \
                        --output ${REPORT_DIR}/dashboard.html \
                        --device "Hfcl-Switch (192.168.180.96)" \
                        --module "Layer 2 - MAC Aging" \
                        --aging  "50 seconds" \
                        2>&1 || true

                    echo "📁 Reports:"
                    ls -la ${REPORT_DIR}/
                '''
                archiveArtifacts artifacts: 'reports/**/*',
                                 allowEmptyArchive: true
                publishHTML(target: [
                    allowMissing:          true,
                    alwaysLinkToLastBuild: true,
                    keepAll:               true,
                    reportDir:             'reports',
                    reportFiles:           'dashboard.html',
                    reportName:            'Test Dashboard'
                ])
            }
        }
    }

    post {
        success {
            echo """
            ╔══════════════════════════════════════════════╗
            ║  ✅  PIPELINE PASSED                         ║
            ║  MAC Address Expiry Interval Test : PASS     ║
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
            echo "Pipeline finished. Check archived logs and reports above."
        }
    }
}
