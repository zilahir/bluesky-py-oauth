"""
Campaign Scheduler

This module handles scheduling of daily campaign executions using APScheduler.
It can run as a separate worker process to maintain campaign schedules.
"""

import atexit
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger

# Check APScheduler version for compatibility
try:
    import apscheduler

    scheduler_logger.info(f"Using APScheduler version: {apscheduler.__version__}")
except Exception as e:
    scheduler_logger.warning(f"Could not detect APScheduler version: {e}")

from queue_config import get_redis_connection
from campaign_config import CampaignConfig
from daily_campaign_worker import process_daily_campaigns
from logger_config import scheduler_logger, log_exception, log_scheduler_event


def execute_daily_campaigns():
    """Execute daily campaigns - wrapper for logging"""
    try:
        scheduler_logger.info(f"Scheduled daily campaign execution starting at {datetime.utcnow()}")
        result = process_daily_campaigns()
        scheduler_logger.info(f"Scheduled daily campaign execution completed: {result}")
    except Exception as e:
        log_exception(scheduler_logger, "Error in scheduled daily campaign execution", e)
        raise


def test_job():
    """Test job for development - remove in production"""
    scheduler_logger.debug(f"Test job executed at {datetime.utcnow()}")


def execute_single_campaign(campaign_id: int):
    """Execute a single campaign"""
    try:
        from daily_campaign_worker import DailyCampaignWorker
        from routes.utils.postgres_connection import get_db

        scheduler_logger.info(f"Executing single campaign {campaign_id}")

        worker = DailyCampaignWorker()
        db = next(get_db())
        try:
            result = worker.process_single_campaign(campaign_id, db)
            scheduler_logger.info(f"Single campaign {campaign_id} execution completed: {result}")
        finally:
            db.close()

    except Exception as e:
        log_exception(scheduler_logger, f"Error executing single campaign {campaign_id}", e)
        raise


class CampaignScheduler:
    """Campaign scheduler using APScheduler"""

    def __init__(self):
        self.config = CampaignConfig()
        self.scheduler = None
        self._setup_scheduler()

    def _setup_scheduler(self):
        """Setup APScheduler with Redis jobstore"""
        try:
            # Use Redis for job persistence
            redis_conn = get_redis_connection()

            jobstores = {
                "default": RedisJobStore(
                    host=redis_conn.connection_pool.connection_kwargs["host"],
                    port=redis_conn.connection_pool.connection_kwargs["port"],
                    db=redis_conn.connection_pool.connection_kwargs["db"],
                    password=redis_conn.connection_pool.connection_kwargs.get(
                        "password"
                    ),
                )
            }

            executors = {
                "default": ThreadPoolExecutor(20),
            }

            job_defaults = {
                "coalesce": True,  # Combine multiple pending executions into one
                "max_instances": 1,  # Only allow one instance at a time
                "misfire_grace_time": 300,  # Allow 5 minutes grace for missed executions
            }

            self.scheduler = BlockingScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone="UTC",
            )

            scheduler_logger.info("Campaign scheduler initialized with Redis jobstore")

        except Exception as e:
            scheduler_logger.warning(f"Error setting up scheduler with Redis, falling back to memory: {e}")
            # Fallback to in-memory scheduler
            self.scheduler = BlockingScheduler(timezone="UTC")

    def start_scheduler(self):
        """Start the campaign scheduler"""
        try:
            scheduler_logger.info("Setting up scheduled jobs...")

            # Add daily campaign processing job
            self.scheduler.add_job(
                func=execute_daily_campaigns,
                trigger=CronTrigger(
                    hour=self.config.DAILY_EXECUTION_HOUR,
                    minute=self.config.DAILY_EXECUTION_MINUTE,
                ),
                id="daily_campaign_processor",
                name="Daily Campaign Processor",
                replace_existing=True,
            )
            scheduler_logger.info("✓ Daily campaign processor job added")

            # Add a test job that runs every 1 minutes for testing
            # Remove this in production
            self.scheduler.add_job(
                func=test_job,
                trigger=CronTrigger(minute="*/1"),  # Every 1 minutes
                id="test_campaign_job",
                name="Test Campaign Job",
                replace_existing=True,
            )
            scheduler_logger.info("✓ Test job added (every 1 minute)")

            scheduler_logger.info(
                f"Campaign scheduler started. Daily execution at {self.config.DAILY_EXECUTION_HOUR:02d}:{self.config.DAILY_EXECUTION_MINUTE:02d} UTC"
            )
            scheduler_logger.info("Scheduled jobs:")
            for job in self.scheduler.get_jobs():
                try:
                    # Handle different APScheduler versions
                    next_run = getattr(job, "next_run_time", "N/A")
                    scheduler_logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {next_run}")
                except AttributeError:
                    scheduler_logger.info(f"  - {job.name} (ID: {job.id}) - Next run: N/A")

            # Register shutdown handler
            atexit.register(self.shutdown_scheduler)

            scheduler_logger.debug(
                ">>> Listing jobs before starting scheduler (to check Redis jobstore)"
            )
            self.list_jobs()

            # Start scheduler (blocking)
            self.scheduler.start()

        except Exception as e:
            log_exception(scheduler_logger, "Error starting campaign scheduler", e)
            raise

    def shutdown_scheduler(self):
        """Gracefully shutdown the scheduler"""
        if self.scheduler and self.scheduler.running:
            scheduler_logger.info("Shutting down campaign scheduler...")
            self.scheduler.shutdown()
            scheduler_logger.info("Campaign scheduler shut down")

    def add_one_time_job(self, campaign_id: int, execution_time: datetime):
        """Add a one-time campaign execution job"""
        job_id = f"campaign_{campaign_id}_{execution_time.strftime('%Y%m%d_%H%M%S')}"

        try:
            self.scheduler.add_job(
                func=execute_single_campaign,
                trigger="date",
                run_date=execution_time,
                args=[campaign_id],
                id=job_id,
                name=f"Campaign {campaign_id} Execution",
                replace_existing=True,
            )
            log_scheduler_event(job_id, f"Added one-time job for campaign {campaign_id} at {execution_time}")
            return job_id
        except Exception as e:
            log_exception(scheduler_logger, f"Error adding one-time job for campaign {campaign_id}", e)
            return None

    def list_jobs(self):
        """List all scheduled jobs"""
        jobs = self.scheduler.get_jobs()
        scheduler_logger.info(f"Scheduled jobs ({len(jobs)}):")
        for job in jobs:
            try:
                next_run = getattr(job, "next_run_time", "N/A")
                trigger = getattr(job, "trigger", "N/A")
                scheduler_logger.info(f"  - {job.name} (ID: {job.id})")
                scheduler_logger.info(f"    Next run: {next_run}")
                scheduler_logger.info(f"    Trigger: {trigger}")
            except AttributeError as e:
                scheduler_logger.warning(
                    f"  - {job.name} (ID: {job.id}) - Error accessing job details: {e}"
                )

    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            log_scheduler_event(job_id, "Removed job")
        except Exception as e:
            log_exception(scheduler_logger, f"Error removing job {job_id}", e)


def start_campaign_scheduler():
    """Main entry point for starting the campaign scheduler"""
    scheduler_logger.info("Starting Campaign Scheduler...")

    scheduler = CampaignScheduler()

    try:
        scheduler.start_scheduler()
    except KeyboardInterrupt:
        scheduler_logger.info("Received interrupt signal")
    except Exception as e:
        log_exception(scheduler_logger, "Scheduler error", e)
    finally:
        scheduler.shutdown_scheduler()


if __name__ == "__main__":
    start_campaign_scheduler()

