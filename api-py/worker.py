#!/usr/bin/env python3
"""
RQ Worker for processing background tasks

Usage:
    python worker.py [--scheduler]

Options:
    --scheduler    Start the campaign scheduler instead of RQ worker

This will start a worker that listens for tasks in campaign queues.
"""
import sys
from rq import Worker
from queue_config import get_redis_connection
from routes.utils.postgres_connection import get_db


def start_rq_worker():
    """Start the RQ worker for processing campaign tasks"""
    redis_conn = get_redis_connection()

    # Add the new daily campaign execution queue
    queues = [
        "campaign_get_all_followers",
        "campaign_execute",
        "campaign_daily_execution"  # New queue for daily processing
    ]

    worker = Worker(queues, connection=redis_conn)
    print(f"RQ Worker started. Listening for tasks on queues: {', '.join(queues)}")
    print("Press Ctrl+C to exit")
    worker.work()


def start_scheduler():
    """Start the campaign scheduler"""
    from campaign_scheduler import start_campaign_scheduler
    start_campaign_scheduler()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--scheduler":
        print("Starting Campaign Scheduler...")
        start_scheduler()
    else:
        print("Starting RQ Worker...")
        start_rq_worker()

