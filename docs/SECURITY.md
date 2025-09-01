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

- Oracle Security List / NSG:
  - Allow inbound:
    - TCP 80 (HTTP) from 0.0.0.0/0
    - Optional TCP 443 (HTTPS) from 0.0.0.0/0
    - TCP 22 (SSH) only from your IP/CIDR
  - Deny or restrict everything else
- OS firewall:
  - Ubuntu (ufw): allow 22, 80, optional 443; deny others
  - Oracle Linux (firewalld): enable http/https services, reload rules
- Do not expose the database on a public interface. The `db` service must not publish ports; it should only be reachable on the internal Docker network via service name `db`.

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