#!/bin/bash
gunicorn -k eventlet -w 4 -b 0.0.0.0:8000 run:app \
    --reload \
    --log-level debug \
    --no-sendfile \
    --timeout 180 \
    --graceful-timeout 180 \
    --max-requests 1000 \
    --max-requests-jitter 100