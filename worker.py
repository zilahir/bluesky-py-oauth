#!/usr/bin/env python3
"""
RQ Worker for processing background tasks

Usage:
    python worker.py

This will start a worker that listens for tasks in the 'campaign_get_all_followers' queue.
"""

from rq import Worker
from queue_config import get_redis_connection
from routes.utils.postgres_connection import get_db

if __name__ == "__main__":
    redis_conn = get_redis_connection()

    worker = Worker(["campaign_get_all_followers", "campaign_execute"], connection=redis_conn)
    print(
        "Worker started. Listening for tasks on 'campaign_get_all_followers' and 'campaign_execute' queues..."
    )
    print("Press Ctrl+C to exit")
    worker.work()

