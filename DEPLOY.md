# Deploy: Django + Vite on Oracle Cloud Free Tier (Ampere ARM64)

This project is containerized for production with:
- Django served by Gunicorn
- Postgres 16 (Alpine)
- Nginx reverse proxy serving /static and proxying app traffic

Files created:
- Docker runtime: [Dockerfile](Dockerfile)
- Entrypoint: [docker/entrypoint.sh](docker/entrypoint.sh)
- Gunicorn config: [gunicorn.conf.py](gunicorn.conf.py)
- Nginx config: [docker/nginx/default.conf](docker/nginx/default.conf)
- Compose (base): [docker-compose.yml](docker-compose.yml)
- Compose (prod overlay): [docker-compose.prod.yml](docker-compose.prod.yml)
- Env template: [.env.example](.env.example)
- Docker ignore: [.dockerignore](.dockerignore)

Important app config references:
- Settings: [ecom/settings.py](ecom/settings.py)
- Vite config: [vite.config.mjs](vite.config.mjs)
- Requirements: [requirements.txt](requirements.txt)

## 1) Prerequisites

- Docker and Docker Compose plugin installed on your Oracle instance.
- Oracle instance should be ARM-based (Ampere) for best performance/cost.

Oracle networking:
- Open ingress on TCP/80 to the instance (use Security List and/or NSG as applicable).

## 2) Environment configuration

Create a .env from the example and set a strong SECRET_KEY:

```bash
cp .env.example .env
# edit .env:
# - SECRET_KEY=your-strong-key
# - ALLOWED_HOSTS=your.public.ip,your.domain
# - CSRF_TRUSTED_ORIGINS=http://your.public.ip,https://your.domain
```

Defaults:
- DATABASE_URL=postgresql://app:app@db:5432/ecom
- POSTGRES_USER=app, POSTGRES_PASSWORD=app, POSTGRES_DB=ecom

## 3) Build and run

If you are building directly on the Oracle Ampere instance, just build and run:

```bash
# first run (build images, create volumes)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

If you build on x86 and push to the ARM host, use `buildx` and set `--platform linux/arm64`:

```bash
docker buildx create --use --name arm64builder || true
docker buildx build --platform linux/arm64 -t yourrepo/ecom:latest --push .
# On the Ampere instance:
#   docker pull yourrepo/ecom:latest
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Services:
- db: Postgres 16-alpine
- web: Django + Gunicorn (builds Vite assets and runs migrations/collectstatic on start)
- nginx: serves /static and proxies to web:8000 (published on host port 80)

## 4) Static assets and Vite

- Vite builds into `static/dist` with base `/static/dist/` and manifest enabled, see [vite.config.mjs](vite.config.mjs).
- `collectstatic` copies static files to `/app/staticfiles` which is shared via a Docker volume and mounted read-only into Nginx at `/staticfiles`.
- Nginx serves `/static/*` from `/staticfiles/*` with caching headers.

## 5) First-time setup

Create a Django superuser (optional but recommended):

```bash
docker compose exec web python manage.py createsuperuser
```

Load sample data (optional) if provided:

```bash
docker compose exec web python manage.py loaddata core/fixtures/sample.json
```

## 6) Logs and health

Check logs:

```bash
docker compose logs -f db
docker compose logs -f web
docker compose logs -f nginx
```

Healthchecks:
- Postgres: `pg_isready`
- web: TCP check on 8000
- nginx: GET /

## 7) Common operations

Rebuild after code changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Run a one-off management command:

```bash
docker compose exec web python manage.py migrate
```

Open a shell inside the web container:

```bash
docker compose exec web bash
```

## 8) SSL/TLS

This setup exposes HTTP on port 80. For TLS:
- Option 1 (recommended): Terminate TLS at an Oracle Load Balancer and send HTTP to instance.
- Option 2: Extend the Nginx config to serve HTTPS with Let's Encrypt (e.g., via certbot sidecar). Not included in this repo.

## 9) Data persistence

Named volumes:
- `postgres-data`: Postgres data directory
- `staticfiles`: collectstatic output shared between web and nginx

To map Postgres to a specific host path or block volume, modify the `db` service volume:

```yaml
services:
  db:
    volumes:
      - /mnt/block-volume/postgres:/var/lib/postgresql/data
```

## 10) Troubleshooting

- 403 or CSRF errors:
  - Ensure your domain/IP is in `ALLOWED_HOSTS`
  - Ensure `CSRF_TRUSTED_ORIGINS` includes scheme + host (http/https)
- Static files not loading:
  - `docker compose exec web python manage.py collectstatic --noinput`
  - Verify `nginx` container mounts `staticfiles` volume and config path is correct.
- Database connection issues:
  - Confirm `DATABASE_URL` and Postgres health.
  - Check `docker compose logs -f db`.

## 11) Development (local)

To run without nginx (expose app directly):

```bash
docker compose up --build
# Then browse http://localhost:8000 (if you add ports to web service) or add nginx overlay for port 80.
```

Note: When using only the base compose, the `web` service is not published to host by default to avoid conflicts; add `ports: ["8000:8000"]` to `web` if needed for local-only testing.
