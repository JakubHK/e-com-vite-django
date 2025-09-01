# Security Hardening Guide

This document consolidates security practices for deploying this project on Oracle Cloud with Docker, Nginx, Postgres, and GitHub Actions.

Related files:
- Base compose: [docker-compose.yml](../docker-compose.yml)
- Production overlay: [docker-compose.prod.yml](../docker-compose.prod.yml)
- Deploy overlay: [docker-compose.deploy.yml](../docker-compose.deploy.yml)
- Nginx config: [docker/nginx/default.conf](../docker/nginx/default.conf)
- App settings: [ecom/settings.py](../ecom/settings.py)
- Env example: [.env.example](../.env.example)
- CI/CD workflow: [.github/workflows/deploy.yml](../.github/workflows/deploy.yml)

## Network Security

Oracle Cloud components (quick map)
- VCN (Virtual Cloud Network): your private network (RFC1918 CIDR such as 10.0.0.0/16).
- Subnet: IP ranges inside the VCN. “Public Subnet” = can assign public IPv4 addresses.
- Internet Gateway (IGW): enables outbound/inbound internet traffic for public subnets.
- Route Table: tells subnets where 0.0.0.0/0 traffic goes (to IGW for public subnets).
- NSG (Network Security Group) vs Security List:
  - Security Lists apply to all VNICs in a subnet (coarser).
  - NSGs attach to specific VNICs/instances (finer, recommended). Prefer NSG.

Recommended layout for this app
- Use a VCN with a Public Subnet that has:
  - A route table containing a default route 0.0.0.0/0 → Internet Gateway
  - DHCP options (defaults are fine)
- Launch the compute instance into this Public Subnet with a Public IPv4 (Ephemeral OK; Reserved IP optional).
- Attach an NSG to the instance and place tight inbound rules on that NSG (preferred over broad Security List changes).

Inbound rules (NSG or Security List)
- HTTP (80/tcp): Source CIDR 0.0.0.0/0 (allow the world to read your site)
- HTTPS (443/tcp, optional): Source CIDR 0.0.0.0/0 (for future TLS)
- SSH (22/tcp): Source CIDR = YOUR_PUBLIC_IP/32 (single-address CIDR). Never 0.0.0.0/0.
  - YOUR_PUBLIC_IP means your workstation’s public IPv4 on the internet (not 192.168.x or 10.x).
  - Find it:
    - curl -4 ifconfig.me
    - curl -4 https://api.ipify.org
    - dig +short myip.opendns.com @resolver1.opendns.com
  - Convert to CIDR by appending /32; e.g., 203.0.113.45 → 203.0.113.45/32.
  - Dynamic IP? You must update the rule when it changes. Alternatives:
    - Use Oracle Bastion for temporary, IP-bound SSH sessions.
    - Use a VPN or jump host with a static egress IP.
    - If absolutely necessary, temporarily widen the CIDR but reduce the time window and revert quickly.

Outbound rules (egress)
- Allow 0.0.0.0/0 so the VM can install packages and pull container images (default is typically OK).

OS firewall (on the VM)
- Ubuntu (ufw):
  - sudo ufw allow 22/tcp
  - sudo ufw allow 80/tcp
  - sudo ufw allow 443/tcp   # only if using TLS
  - sudo ufw enable
- Oracle Linux (firewalld):
  - sudo firewall-cmd --add-service=http --permanent
  - sudo firewall-cmd --add-service=https --permanent   # only if using TLS
  - sudo firewall-cmd --reload

Database exposure
- Do not expose the database on a public interface. The db service must NOT publish host ports.
- Access Postgres only via the internal Docker network (service name db). Keep rules restricted to the Docker network namespace.

Additional notes
- Consider reserving a Public IPv4 if you need a stable address across reboots.
- IPv6 is optional and out of scope here; if enabled, mirror the same principles (tight SSH, open 80/443 as needed).
- Prefer NSGs on the instance for precise control; avoid loosening the entire subnet via Security Lists unless necessary.

## Identity and Secrets

- Do not commit any secrets to Git. Never commit `.env`.
- Server-side `.env` contains:
  - SECRET_KEY: strong, random, at least 50 chars
  - POSTGRES_PASSWORD: strong
  - DEBUG=false for production
  - ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS set to your public IP and/or domain (CSRF values must include scheme, e.g. https://example.com)
- GitHub Actions Secrets:
  - SSH_HOST, SSH_USER, SSH_KEY, SSH_PATH
  - If GHCR images are private: GHCR_USERNAME, GHCR_TOKEN (PAT with read:packages)
- Principle of least privilege:
  - Use a non-root deploy user on the server and add only to the `docker` group
  - Restrict SSH ingress to your IP in Oracle Security List / NSG

## Application Security

- Django config (production):
  - DEBUG=false (set in environment)
  - SECRET_KEY set via environment
  - ALLOWED_HOSTS contains the production hostname(s)
  - CSRF_TRUSTED_ORIGINS includes scheme + host for your site (http or https)
- Static files:
  - Served by Nginx from a read-only volume (`/staticfiles/`)
- Gunicorn:
  - Bound to `0.0.0.0:8000` internally; only Nginx should be exposed publicly

## TLS and HTTPS

- Recommended: Oracle Load Balancer (Always Free) to terminate TLS and forward HTTP to the instance
- Alternative: Certbot with Nginx on the instance (not included here)
- Always prefer HTTPS for user-facing traffic to protect credentials and cookies

## CI/CD Security

- Protect the “production” environment in GitHub:
  - Require reviewers (manual approval) before deployment
  - Restrict branches allowed to deploy
- Avoid building images on the production server:
  - Images are built in CI (linux/arm64) and pulled to the server with a pinned tag (commit SHA)
- Rollback capability:
  - Keep previous image tags available in GHCR
  - Redeploy with the prior SHA quickly if needed

## Database Security and Backups

- Do not expose Postgres port on the host
- Use strong credentials from `.env`
- Backups:
  - Periodic `pg_dump` to a secure off-host location
  - Encrypt stored backups at rest
- Resource monitoring: ensure the Postgres data volume has sufficient disk space

## OS and Runtime Security

- Keep OS packages up to date (security updates)
- Lock down SSH:
  - Public key authentication
  - Disable password login
  - Restrict to your IP range
- Keep Docker and dependencies updated
- Least privileges for services and files (e.g., limit write access to only necessary directories)

## Incident Response Basics

- Logs:
  - `docker compose logs -f nginx web db`
- Quick isolation:
  - If compromise suspected, block inbound at Oracle Security List / NSG, stop services (`docker compose down`), rotate credentials (SECRET_KEY, DB password), and redeploy clean images
- Inventory:
  - Keep track of what images/tags are deployed (commit SHAs), and what secrets are active

## Checklist

- [ ] Oracle Security List / NSG configured (22 restricted, 80 open, optional 443)
- [ ] OS firewall configured consistently with Oracle rules
- [ ] `.env` present on server with strong secrets
- [ ] DEBUG=false in production
- [ ] ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS set correctly
- [ ] Nginx serves `/static` from read-only volume
- [ ] Database not exposed publicly
- [ ] CI/CD environment protected with manual approval
- [ ] Backups scheduled and tested
- [ ] TLS plan documented (Load Balancer or certbot)