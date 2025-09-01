import os
import multiprocessing

# Bind to all interfaces on the internal port
bind = "0.0.0.0:8000"

# Sensible defaults for Oracle Ampere Free Tier (tweak via env)
workers = int(os.getenv("WEB_CONCURRENCY", max(2, multiprocessing.cpu_count() // 2 or 1)))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Log to stdout/stderr so Docker can collect logs
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")

# Enable proxy headers if running behind nginx
forwarded_allow_ips = "*"
proxy_protocol = False