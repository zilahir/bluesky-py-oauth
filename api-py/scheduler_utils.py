"""
Scheduler Utilities

Utility functions for managing APScheduler jobs related to campaigns.
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.redis import RedisJobStore
from queue_config import get_redis_connection
from typing import Optional, List
from logger_config import scheduler_logger, log_exception


def get_scheduler_instance() -> Optional[BlockingScheduler]:
    """Get a scheduler instance for job management operations"""
    try:
        redis_conn = get_redis_connection()

        jobstores = {
            "default": RedisJobStore(
                host=redis_conn.connection_pool.connection_kwargs["host"],
                port=redis_conn.connection_pool.connection_kwargs["port"],
                db=redis_conn.connection_pool.connection_kwargs["db"],
                password=redis_conn.connection_pool.connection_kwargs.get("password"),
            )
        }

        # Create non-blocking scheduler for management operations
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone="UTC",
        )

        if not scheduler.running:
            scheduler.start()

        return scheduler

    except Exception as e:
        log_exception(scheduler_logger, "Error getting scheduler instance", e)
        return None


def remove_campaign_jobs(campaign_id: int) -> bool:
    """
    Remove all scheduled jobs related to a specific campaign.

    Args:
        campaign_id: The ID of the campaign whose jobs should be removed

    Returns:
        bool: True if jobs were found and removed, False otherwise
    """
    scheduler = get_scheduler_instance()
    if not scheduler:
        scheduler_logger.error(f"Could not get scheduler instance for campaign {campaign_id}")
        return False

    try:
        # Get all jobs and filter for campaign-specific ones
        jobs = scheduler.get_jobs()
        campaign_jobs = []

        for job in jobs:
            job_id = getattr(job, "id", "")
            # Look for jobs with campaign ID in the job ID
            if f"campaign_{campaign_id}_" in job_id:
                campaign_jobs.append(job)

        if not campaign_jobs:
            scheduler_logger.info(f"No scheduled jobs found for campaign {campaign_id}")
            return True

        # Remove each campaign-specific job
        removed_count = 0
        for job in campaign_jobs:
            try:
                job_id = getattr(job, "id", "")
                scheduler.remove_job(job_id)
                scheduler_logger.info(f"Removed scheduled job: {job_id}")
                removed_count += 1
            except Exception as e:
                log_exception(scheduler_logger, f"Error removing job {job_id}", e)

        scheduler_logger.info(f"Removed {removed_count} scheduled jobs for campaign {campaign_id}")
        return True

    except Exception as e:
        log_exception(scheduler_logger, f"Error removing jobs for campaign {campaign_id}", e)
        return False

    finally:
        # Don't shutdown the scheduler here as it might be used by other processes
        pass


def list_campaign_jobs(campaign_id: int) -> List[str]:
    """
    List all scheduled jobs for a specific campaign.

    Args:
        campaign_id: The ID of the campaign

    Returns:
        List[str]: List of job IDs related to the campaign
    """
    scheduler = get_scheduler_instance()
    if not scheduler:
        return []

    try:
        jobs = scheduler.get_jobs()
        campaign_job_ids = []

        for job in jobs:
            job_id = getattr(job, "id", "")
            if f"campaign_{campaign_id}_" in job_id:
                campaign_job_ids.append(job_id)

        return campaign_job_ids

    except Exception as e:
        log_exception(scheduler_logger, f"Error listing jobs for campaign {campaign_id}", e)
        return []


def cleanup_all_campaign_jobs() -> bool:
    """
    Remove all campaign-specific jobs (useful for maintenance).

    Returns:
        bool: True if cleanup was successful
    """
    scheduler = get_scheduler_instance()
    if not scheduler:
        return False

    try:
        jobs = scheduler.get_jobs()
        campaign_jobs = []

        for job in jobs:
            job_id = getattr(job, "id", "")
            # Look for jobs that start with 'campaign_' but exclude daily processor
            if job_id.startswith("campaign_") and job_id != "daily_campaign_processor":
                campaign_jobs.append(job)

        removed_count = 0
        for job in campaign_jobs:
            try:
                job_id = getattr(job, "id", "")
                scheduler.remove_job(job_id)
                scheduler_logger.info(f"Removed campaign job: {job_id}")
                removed_count += 1
            except Exception as e:
                log_exception(scheduler_logger, f"Error removing job {job_id}", e)

        scheduler_logger.info(f"Cleaned up {removed_count} campaign jobs")
        return True

    except Exception as e:
        log_exception(scheduler_logger, "Error during campaign job cleanup", e)
        return False

