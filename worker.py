#!/usr/bin/env python3
"""
RQ Worker for processing background tasks

Usage:
    python worker.py

This will start a worker that listens for tasks in the 'campaign_processing' queue.
"""

from rq import Worker
from queue_config import get_redis_connection

if __name__ == '__main__':
    redis_conn = get_redis_connection()
    worker = Worker(['campaign_processing'], connection=redis_conn)
    print("Worker started. Listening for tasks on 'campaign_processing' queue...")
    print("Press Ctrl+C to exit")
    worker.work()