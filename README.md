# E-Commerce Database Management System (EDMS)

A learning/portfolio project: Nginx frontend + FastAPI REST API + MySQL 8.0, deployed with Docker Compose on AWS EC2 and delivered by Jenkins.

## Architecture

- EC2-1: Jenkins + Docker (CI/CD)
- EC2-2: Docker Compose app stack (Nginx frontend, FastAPI backend, MySQL)
- Docker Hub: backend and frontend image registry
- MySQL named volume: `edms_mysql_data`

## 1. Local prerequisites

Docker Engine, Docker Compose v2, Git, and a Docker Hub account.

```bash
cp .env.example .env
# Edit .env and set strong unique passwords and your Docker Hub username
docker compose up -d --build
docker compose ps
```

Open `http://localhost`. API docs: `http://localhost/docs` is not exposed by Nginx; use `http://localhost:8000/docs` only if you temporarily publish backend port 8000 for local development, or use `docker compose exec backend ...`.

## 2. AWS network design

Create two Ubuntu 24.04 LTS EC2 instances in the same VPC. Suggested lab size: t3.medium each; verify regional quotas and pricing. Attach a persistent EBS volume to the application EC2 for Docker/MySQL data if you want data to survive replacement of the root disk.

Security groups:
- Jenkins EC2: TCP 22 from your trusted public IP; TCP 8080 from your trusted public IP. Do not expose Jenkins to the whole internet.
- App EC2: TCP 22 from your trusted IP and Jenkins EC2 security group; TCP 80 from intended client IP ranges (0.0.0.0/0 only if deliberately public).
- Do NOT open MySQL TCP 3306 to the internet. The database is only reachable on the private Docker network.

Use an EC2 key pair. Prefer private networking/SSM for production. This lab uses SSH from Jenkins to the app instance.

## 3. Install Docker on both EC2 instances

Run on each Ubuntu instance:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
docker compose version
```

## 4. Jenkins EC2

Install Java 21 and Jenkins using the current official Jenkins LTS installation instructions for Ubuntu. Then:
1. Open Jenkins at `http://JENKINS_PUBLIC_IP:8080` from your trusted IP.
2. Complete setup and install suggested plugins.
3. Install/verify: Pipeline, Git, Credentials Binding, SSH Agent.
4. Ensure Jenkins can use Docker. Add the Jenkins service account to the docker group, restart Jenkins, and verify `sudo -u jenkins docker ps`. Docker group access is effectively root-level access.
5. Create a Docker Hub repository named `edms-backend` and another named `edms-frontend`.

## 5. Application EC2

Install Docker as above. Create the deployment directory:

```bash
sudo mkdir -p /opt/edms
sudo chown ubuntu:ubuntu /opt/edms
```

Clone this repository to a working directory on your laptop or Jenkins. On the app EC2, deployment files are copied by the pipeline.

## 6. Configure secrets

On the app EC2, create `/opt/edms/.env` with strong unique values:

```bash
cd /opt/edms
cp .env.example .env   # if copied into this directory
nano .env
chmod 600 .env
```

At minimum set `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD`. Never commit `.env` to Git. For stronger secret handling, use AWS Secrets Manager or SSM Parameter Store.

The Jenkins pipeline copies `.env` from the Jenkins workspace to the app EC2. To make that happen safely:
- Store the app `.env` as a Jenkins Secret file credential with ID `edms-env-file`. The provided Jenkinsfile copies this credential to `$REMOTE_DIR/.env` during deployment.
- Do not commit `.env` or print its contents in pipeline logs.

## 7. Jenkins credentials and pipeline

Create these credentials in Jenkins:
- `dockerhub-creds`: Username with password/token for Docker Hub.
- `dockerhub-username`: Secret text containing your Docker Hub username (used by the Jenkinsfile environment binding).
- `edms-app-ec2-ssh`: SSH private key credential for the EC2 key pair. The matching public key must be in `/home/ubuntu/.ssh/authorized_keys` on the app EC2.
- `edms-env-file`: Secret file credential containing the app `.env` file with strong `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD` values.

Update Jenkinsfile:
- Replace `APP_HOST` with the app EC2 public IP or private IP reachable from Jenkins.
- Confirm Docker Hub image names match your account.
- Create a Pipeline job connected to your GitHub repository and select “Pipeline script from SCM”.
- Configure GitHub webhook or Poll SCM.
- The pipeline retrieves `.env` from the `edms-env-file` Secret file credential and copies it to the app EC2; do not put passwords in source control.

**Important:** Jenkinsfile is a starter example. The `dockerhub-username` credential should be Secret text, and `dockerhub-creds` should be Username with password. For a production pipeline, use immutable image tags, protected branches, vulnerability scanning, approval gates, and managed secrets.

## 8. Deploy manually first

From the repository root on the application EC2:

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
curl -fsS http://localhost/health
```

Open `http://APP_EC2_PUBLIC_IP`.

## 9. Verify database

```bash
docker exec -it edms-mysql mysql -u edms_user -p ecommerce_db
```

Useful SQL:

```sql
SHOW TABLES;
SELECT * FROM customers;
SELECT product_name, price, stock_quantity FROM products;
SELECT * FROM v_country_sales;
CALL sp_customer_count_by_country('India');
```

Create an order in the dashboard and confirm:
```sql
SELECT * FROM orders ORDER BY order_id DESC;
SELECT * FROM order_items ORDER BY order_item_id DESC;
SELECT * FROM payments ORDER BY payment_id DESC;
```

## 10. Backup and restore

Backup:
```bash
mkdir -p ~/edms-backups
docker exec edms-mysql sh -c 'exec mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction ecommerce_db' > ~/edms-backups/ecommerce_$(date +%F_%H%M%S).sql
```

Restore into the database (test carefully; restore overwrites matching objects):
```bash
cat ~/edms-backups/your-backup.sql | docker exec -i edms-mysql sh -c 'exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" ecommerce_db'
```

## 11. Operations

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f db
docker compose restart backend
docker compose down                 # retains named volume
docker compose down -v              # DELETES database volume; destructive
```

## 12. Important limitations and hardening

- Payment is simulated; no real payment gateway is integrated.
- This is a portfolio/learning starter, not a production-certified commerce system.
- Add authentication/authorization, rate limiting, TLS, CSRF protections where applicable, audit logs, migrations, secret manager integration, and automated backup retention before public production use.
- The frontend currently supports creating customers/products/orders and deleting products. Product update endpoint is available in the API; an edit UI can be added as an enhancement.
- SQL init scripts execute only when the MySQL data directory is empty. Changing `database/init.sql` does not rerun it on an existing named volume.
- For schema changes, use versioned migrations (for example Alembic/Flyway) rather than deleting the database volume.
