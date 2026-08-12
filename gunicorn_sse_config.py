"""Gunicorn configuration for the Aperte SSE stream server.

SSE streams are long-lived connections (one per open browser). They are
mostly idle (the generator sleeps between DB polls), so thread-per-stream
is fine: 2 workers x 128 threads = 256 concurrent streams while the main
API server keeps its 16 threads for regular requests.
"""

import os

# 2 workers (a worker crash drops its streams; 2 gives some resilience)
workers = int(os.environ.get('GUNICORN_SSE_WORKERS', 2))
# threads handle the concurrent streams (mostly sleeping)
threads = int(os.environ.get('GUNICORN_SSE_THREADS', 128))

bind = os.environ.get('GUNICORN_SSE_BIND', '127.0.0.1:8097')

timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
graceful_timeout = 30
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
