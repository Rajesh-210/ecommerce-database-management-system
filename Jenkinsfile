pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds() }
  environment {
    DOCKERHUB_USER = credentials('dockerhub-username')
    APP_HOST = 'REPLACE_WITH_APP_EC2_PUBLIC_IP'
    APP_USER = 'ubuntu'
    REMOTE_DIR = '/opt/edms'
  }
  stages {
    stage('Checkout') { steps { checkout scm } }
    stage('Validate') {
      steps {
        sh '''
          set -eu
          test -f docker-compose.yml
          test -f database/init.sql
          python3 -m py_compile backend/app.py
          MYSQL_ROOT_PASSWORD=validation-only MYSQL_PASSWORD=validation-only docker compose config -q
        '''
      }
    }
    stage('Build Images') {
      steps {
        sh '''
          docker build -t "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}" ./backend
          docker build -t "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}" ./frontend
          docker tag "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}" "$DOCKERHUB_USER/edms-backend:latest"
          docker tag "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}" "$DOCKERHUB_USER/edms-frontend:latest"
        '''
      }
    }
    stage('Push Images') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
          sh '''
            echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
            docker push "$DOCKERHUB_USER/edms-backend:${BUILD_NUMBER}"
            docker push "$DOCKERHUB_USER/edms-frontend:${BUILD_NUMBER}"
            docker push "$DOCKERHUB_USER/edms-backend:latest"
            docker push "$DOCKERHUB_USER/edms-frontend:latest"
            docker logout
          '''
        }
      }
    }
    stage('Deploy to Application EC2') {
      steps {
        withCredentials([file(credentialsId: 'edms-env-file', variable: 'ENV_FILE')]) {
        sshagent(credentials: ['edms-app-ec2-ssh']) {
          sh '''
            set -eu
            ssh -o StrictHostKeyChecking=accept-new "$APP_USER@$APP_HOST" "sudo mkdir -p $REMOTE_DIR && sudo chown $APP_USER:$APP_USER $REMOTE_DIR"
            scp docker-compose.yml "$APP_USER@$APP_HOST:$REMOTE_DIR/"
            scp "$ENV_FILE" "$APP_USER@$APP_HOST:$REMOTE_DIR/.env"
            scp -r database "$APP_USER@$APP_HOST:$REMOTE_DIR/"
            ssh "$APP_USER@$APP_HOST" "cd $REMOTE_DIR && BACKEND_IMAGE=$DOCKERHUB_USER/edms-backend:$BUILD_NUMBER FRONTEND_IMAGE=$DOCKERHUB_USER/edms-frontend:$BUILD_NUMBER docker compose pull && BACKEND_IMAGE=$DOCKERHUB_USER/edms-backend:$BUILD_NUMBER FRONTEND_IMAGE=$DOCKERHUB_USER/edms-frontend:$BUILD_NUMBER docker compose up -d --remove-orphans"
            ssh "$APP_USER@$APP_HOST" "curl -fsS http://localhost/health"
          '''
        }
        }
      }
    }
  }
  post {
    success { echo 'EDMS deployment completed successfully.' }
    failure { echo 'EDMS pipeline failed. Review the stage logs before retrying.' }
  }
}
