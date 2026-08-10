"""Gunicorn configuration for Aperte.

The API is I/O-bound (most requests wait on Postgres). Use multiple
processes * threads so cores are used while workers wait on the DB.

- workers = number of CPU cores (4 on the deployment box)
- threads = per-worker threads (async within a worker)
This gives 4 processes x 4 threads = 16 concurrent requests.
"""

import multiprocessing
import os

# 1 worker per core, 4 threads each
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count()))
threads = int(os.environ.get('GUNICORN_THREADS', 4))

# Bind to localhost; the reverse proxy (nginx) or tunnel fronts this.
bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8095')

# Allow the app to gracefully drain before restart
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
graceful_timeout = 30
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
