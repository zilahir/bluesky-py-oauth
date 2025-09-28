"""
Campaign execution configuration and constants
"""
from datetime import timedelta
from enum import Enum


class CampaignStatus(Enum):
    """Campaign status enum"""
    SETUP = "setup"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class CampaignConfig:
    """Configuration settings for campaign execution"""

    # Follow/Unfollow limits
    MAX_FOLLOWS_PER_DAY = 5
    MAX_UNFOLLOWS_PER_DAY = 10  # Allow more unfollows than follows

    # Timing configuration
    UNFOLLOW_DELAY_DAYS = 5  # Days to wait before unfollowing if no follow-back
    FOLLOW_BACK_CHECK_INTERVAL_HOURS = 24  # How often to check for follow-backs

    # Retry configuration
    MAX_FOLLOW_ATTEMPTS = 3
    MAX_UNFOLLOW_ATTEMPTS = 2

    # Rate limiting
    REQUEST_DELAY_SECONDS = 2  # Delay between API requests
    FOLLOW_BATCH_SIZE = 5  # Process follows in batches
    UNFOLLOW_BATCH_SIZE = 10  # Process unfollows in batches

    # Campaign execution timing
    DAILY_EXECUTION_HOUR = 10  # Execute campaigns at 10 AM
    DAILY_EXECUTION_MINUTE = 0

    @classmethod
    def get_unfollow_cutoff_date(cls):
        """Get the cutoff date for unfollowing accounts"""
        from datetime import datetime, timedelta
        return datetime.utcnow() - timedelta(days=cls.UNFOLLOW_DELAY_DAYS)

    @classmethod
    def get_follow_back_check_cutoff(cls):
        """Get cutoff date for checking follow-backs"""
        from datetime import datetime, timedelta
        return datetime.utcnow() - timedelta(hours=cls.FOLLOW_BACK_CHECK_INTERVAL_HOURS)


class CampaignMetrics:
    """Metrics tracking for campaigns"""

    @staticmethod
    def track_daily_execution(campaign_id: int, follows_count: int, unfollows_count: int,
                            follow_backs_count: int = 0):
        """Track daily campaign execution metrics"""
        from metrics import (
            track_followers_processed,
            track_unfollows_processed,
            track_follow_backs_detected,
            track_daily_campaign_execution
        )

        # Track all the metrics
        if follows_count > 0:
            track_followers_processed(str(campaign_id), follows_count)
        if unfollows_count > 0:
            track_unfollows_processed(str(campaign_id), unfollows_count)
        if follow_backs_count > 0:
            track_follow_backs_detected(str(campaign_id), follow_backs_count)

        # Track successful daily execution
        track_daily_campaign_execution("success")

        # Log execution stats
        print(f"Campaign {campaign_id} daily execution:")
        print(f"  - Follows: {follows_count}")
        print(f"  - Unfollows: {unfollows_count}")
        print(f"  - New follow-backs: {follow_backs_count}")


# Campaign execution states for better tracking
CAMPAIGN_EXECUTION_STATES = {
    "READY_TO_FOLLOW": "ready_to_follow",
    "DAILY_LIMIT_REACHED": "daily_limit_reached",
    "WAITING_FOR_FOLLOWBACK": "waiting_for_followback",
    "READY_TO_UNFOLLOW": "ready_to_unfollow",
    "UNFOLLOWED": "unfollowed",
    "FOLLOWING_BACK": "following_back"
}