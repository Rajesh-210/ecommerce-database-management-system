
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        DOCKERHUB_USER = credentials('dockerhub-username')
        APP_HOST = '15.207.21.195'
        APP_USER = 'ubuntu'
        REMOTE_DIR = '/opt/edms'
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Validate') {
            steps {
                sh '''
                    set -eu

                    test -f docker-compose.yml
                    test -f database/init.sql
                    test -f sonar-project.properties

                    python3 -m py_compile backend/app.py

                    MYSQL_ROOT_PASSWORD=validation-only \
                    MYSQL_PASSWORD=validation-only \
                    docker compose config -q

                    echo "Application validation successful"
                '''
            }
        }

        stage('SonarQube Code Analysis') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'

                    withSonarQubeEnv('SonarQube-EDMS') {
                        sh """
                            "${scannerHome}/bin/sonar-scanner"
                        """
                    }
                }
            }
        }

        stage('SonarQube Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Trivy Filesystem Scan') {
            steps {
                sh '''
                    set -eu

                    echo "Starting Trivy filesystem scan"

                    cd /tmp

                    trivy --config "" fs \
                        --scanners vuln,secret \
                        --severity HIGH,CRITICAL \
                        --exit-code 1 \
                        --format json \
                        --output "$WORKSPACE/trivy-fs-report.json" \
                        "$WORKSPACE"

                    echo "Filesystem scan completed successfully"
                '''
            }
        }

        stage('Build Images') {
            steps {
                sh '''
                    set -eu

                    docker build \
                        -t "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}" \
                        ./backend

                    docker build \
                        -t "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}" \
                        ./frontend

                    docker tag \
                        "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}" \
                        "$DOCKERHUB_USER/edms-backend:latest"

                    docker tag \
                        "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}" \
                        "$DOCKERHUB_USER/edms-frontend:latest"
                '''
            }
        }

        stage('Trivy Docker Image Scan') {
            steps {
                sh '''
                    set -eu

                    cd /tmp

                    echo "Scanning backend Docker image"

                    trivy --config "" image \
                        --severity HIGH,CRITICAL \
                        --exit-code 1 \
                        --format json \
                        --output "$WORKSPACE/trivy-backend-report.json" \
                        "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}"

                    echo "Scanning frontend Docker image"

                    trivy --config "" image \
                        --severity HIGH,CRITICAL \
                        --exit-code 1 \
                        --format json \
                        --output "$WORKSPACE/trivy-frontend-report.json" \
                        "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}"

                    echo "Docker image scans completed successfully"
                '''
            }
        }

        stage('Push Images') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-creds',
                        usernameVariable: 'DH_USER',
                        passwordVariable: 'DH_PASS'
                    )
                ]) {
                    sh '''
                        set -eu
                        set +x

                        trap 'docker logout >/dev/null 2>&1 || true' EXIT

                        printf '%s' "$DH_PASS" | \
                            docker login -u "$DH_USER" --password-stdin

                        docker push "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}"
                        docker push "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}"

                        docker push "$DOCKERHUB_USER/edms-backend:latest"
                        docker push "$DOCKERHUB_USER/edms-frontend:latest"
                    '''
                }
            }
        }

        stage('Deploy to Application EC2') {
            steps {
                withCredentials([
                    file(
                        credentialsId: 'edms-env-file',
                        variable: 'ENV_FILE'
                    )
                ]) {
                    sshagent(credentials: ['edms-app-ec2-ssh']) {

                        sh '''
                            set -eu

                            ssh -o StrictHostKeyChecking=accept-new \
                                "$APP_USER@$APP_HOST" \
                                "sudo mkdir -p $REMOTE_DIR &&
                                 sudo chown $APP_USER:$APP_USER $REMOTE_DIR"

                            scp docker-compose.yml \
                                "$APP_USER@$APP_HOST:$REMOTE_DIR/"

                            scp "$ENV_FILE" \
                                "$APP_USER@$APP_HOST:/tmp/edms.env"

                            ssh "$APP_USER@$APP_HOST" \
                                "sudo install -o $APP_USER -g $APP_USER \
                                 -m 600 /tmp/edms.env $REMOTE_DIR/.env &&
                                 rm -f /tmp/edms.env"

                            scp -r database \
                                "$APP_USER@$APP_HOST:$REMOTE_DIR/"

                            ssh "$APP_USER@$APP_HOST" \
                                "cd $REMOTE_DIR &&
                                 BACKEND_IMAGE=$DOCKERHUB_USER/edms-backend:$BUILD_NUMBER \
                                 FRONTEND_IMAGE=$DOCKERHUB_USER/edms-frontend:$BUILD_NUMBER \
                                 docker compose pull &&
                                 BACKEND_IMAGE=$DOCKERHUB_USER/edms-backend:$BUILD_NUMBER \
                                 FRONTEND_IMAGE=$DOCKERHUB_USER/edms-frontend:$BUILD_NUMBER \
                                 docker compose up -d --remove-orphans"

                            ssh "$APP_USER@$APP_HOST" \
                                "curl -fsS http://localhost/health"
                        '''
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: 'trivy-*-report.json',
                allowEmptyArchive: true
            )
        }

        success {
            echo 'EDMS deployment and DevSecOps pipeline completed successfully.'
        }

        failure {
            echo 'EDMS pipeline failed. Review the stage logs before retrying.'
        }
    }
}
