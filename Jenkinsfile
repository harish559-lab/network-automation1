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
        TRAFFIC_SCRIPT = "${WORKSPACE}/scripts/MAC_generate_traffic.py"
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
                    # Check what python is available
                    which python3 || which python || echo "No python found"
                    python3 --version || python --version || echo "Python not available"

                    # Install pip if not available
                    apt-get update -qq && apt-get install -y -qq python3-pip || true

                    # Install dependencies using python3 -m pip
                    python3 -m pip install --quiet paramiko scapy pyats ansible || \
                    python3 -m pip install --quiet paramiko pyats ansible

                    echo "✅ Dependencies installed"
                    python3 --version
                    python3 -m ansible --version | head -1 || true
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

                    python3 -m ansible playbook \
                        -i ${INVENTORY} \
                        ${PLAYBOOK} \
                        -v \
                        2>&1 | tee ${REPORT_DIR}/ansible_run.log || \
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
        // -----------------------------------------------------------
        stage('Generate Bi-directional Traffic') {
            steps {
                echo '=== Sending bi-directional traffic via Scapy ==='
                sh '''
                    sudo python3 ${TRAFFIC_SCRIPT} \
                        --interface enp2s0 \
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
        // STAGE 5 — Collect Reports
        // -----------------------------------------------------------
        stage('Collect Reports') {
            steps {
                echo '=== Collecting reports ==='
                sh '''
                    mkdir -p ${REPORT_DIR}
                    [ -f /tmp/mac_expiry_test_report.txt ] && \
                        cp /tmp/mac_expiry_test_report.txt ${REPORT_DIR}/ || true
                    [ -f /tmp/mac_table_snapshot.txt ] && \
                        cp /tmp/mac_table_snapshot.txt ${REPORT_DIR}/ || true
                    echo "📁 Reports:"
                    ls -la ${REPORT_DIR}/ || true
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
