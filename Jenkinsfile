// =============================================================
// Jenkinsfile — MAC Address Table Expiry Interval Test Pipeline
// Agent       : Linux built-in node
// Flow        : Config → Traffic → pyATS Validation → Report
// =============================================================

pipeline {

    agent any   // Linux built-in node

    environment {
        PROJECT_DIR    = "${WORKSPACE}"
        TESTBED        = "${WORKSPACE}/pyats/testbed.yaml"
        PLAYBOOK       = "${WORKSPACE}/ansible/playbooks/mac_aging_config.yml"
        INVENTORY      = "${WORKSPACE}/ansible/inventory/hosts.ini"
        PYATS_TEST     = "${WORKSPACE}/pyats/testcases/test_mac_aging.py"
        TRAFFIC_SCRIPT = "${WORKSPACE}/scripts/MAC_generate_traffic.py"
        HELPER_SCRIPT  = "${WORKSPACE}/scripts/switch_cmd.py"
        REPORT_DIR     = "${WORKSPACE}/reports"
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
                    pip3 install paramiko scapy pyats[full] ansible --quiet
                    echo "✅ Dependencies installed"
                    python3 --version
                    ansible --version | head -1
                    pyats version
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
                    ansible-playbook \
                        -i ${INVENTORY} \
                        ${PLAYBOOK} \
                        -v \
                        2>&1 | tee ${WORKSPACE}/ansible_run.log

                    echo "✅ Ansible playbook completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'ansible_run.log',
                                     allowEmptyArchive: true
                }
                failure {
                    echo '❌ Ansible configuration FAILED — aborting pipeline'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 3 — Traffic Generation (Scapy)
        // -----------------------------------------------------------
        stage('Generate Bi-directional Traffic') {
            steps {
                echo '=== Sending bi-directional traffic via Scapy ==='
                sh '''
                    # Scapy needs root to send raw packets
                    sudo python3 ${TRAFFIC_SCRIPT} \
                        --interface enp2s0 \
                        2>&1 | tee ${WORKSPACE}/traffic_run.log

                    echo "✅ Traffic generation completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'traffic_run.log',
                                     allowEmptyArchive: true
                }
                failure {
                    echo '❌ Traffic generation FAILED'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 4 — pyATS: Run MAC Aging Validation Tests
        // -----------------------------------------------------------
        stage('Validate with pyATS') {
            steps {
                echo '=== Running pyATS test suite for MAC aging verification ==='
                sh '''
                    mkdir -p ${REPORT_DIR}

                    python3 ${PYATS_TEST} \
                        --testbed ${TESTBED} \
                        2>&1 | tee ${WORKSPACE}/pyats_run.log

                    echo "✅ pyATS validation completed"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'pyats_run.log',
                                     allowEmptyArchive: true

                    publishHTML(target: [
                        allowMissing:           true,
                        alwaysLinkToLastBuild:  true,
                        keepAll:                true,
                        reportDir:              'reports',
                        reportFiles:            '*.html',
                        reportName:             'pyATS Test Report'
                    ])
                }
                failure {
                    echo '❌ pyATS validation FAILED'
                }
            }
        }

        // -----------------------------------------------------------
        // STAGE 5 — Collect & Archive Reports
        // -----------------------------------------------------------
        stage('Collect Reports') {
            steps {
                echo '=== Collecting test artifacts and reports ==='
                sh '''
                    mkdir -p ${REPORT_DIR}

                    [ -f /tmp/mac_expiry_test_report.txt ] && \
                        cp /tmp/mac_expiry_test_report.txt ${REPORT_DIR}/ || true

                    [ -f /tmp/mac_table_snapshot.txt ] && \
                        cp /tmp/mac_table_snapshot.txt ${REPORT_DIR}/ || true

                    echo "📁 Report directory contents:"
                    ls -la ${REPORT_DIR}/ || true
                '''
                archiveArtifacts artifacts: 'reports/**/*',
                                 allowEmptyArchive: true
            }
        }
    }

    // -----------------------------------------------------------
    // POST — Final status
    // -----------------------------------------------------------
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
            ║  MAC Address Expiry Interval Test : FAIL     ║
            ║  Check archived logs for details.            ║
            ╚══════════════════════════════════════════════╝
            """
        }
        always {
            echo "Pipeline finished. Check archived logs and reports above."
        }
    }
}
