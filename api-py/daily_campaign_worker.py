"""
Daily Campaign Worker

This worker handles the daily execution of active campaigns:
- Follows new accounts (max 5 per day per campaign)
- Checks for follow-backs
- Unfollows accounts that haven't followed back after the delay period
"""

import time
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from routes.utils.postgres_connection import (
    get_db,
    Campaign,
    FollowersToGet,
    OAuthSession,
    CampaignExecutionLog,
)
from campaign_config import CampaignConfig, CampaignMetrics, CAMPAIGN_EXECUTION_STATES
from atproto_oauth import pds_authed_req
from requests import request as req
from metrics import track_rq_job
from logger_config import campaign_logger, log_exception, log_campaign_event


class DailyCampaignWorker:
    """Daily campaign execution worker"""

    def __init__(self):
        self.config = CampaignConfig()

    def process_all_active_campaigns(self) -> str:
        """
        Main entry point for daily campaign processing.
        Processes all active campaigns.
        """
        start_time = datetime.utcnow()
        total_campaigns_processed = 0
        total_follows = 0
        total_unfollows = 0
        total_follow_backs = 0

        try:
            campaign_logger.info(f"Starting daily campaign processing at {start_time}")

            if self.config.DEBUG_MODE:
                campaign_logger.info(
                    "🐛 DEBUG MODE: Running every minute with verbose logging"
                )

            # Get all active campaigns (setup complete but not deleted)
            db = next(get_db())
            try:
                active_campaigns = (
                    db.query(Campaign)
                    .filter(
                        and_(
                            Campaign.is_setup_job_running
                            == False,  # Setup must be complete
                            Campaign.deleted_at.is_(None),  # Not deleted
                        )
                    )
                    .all()
                )

                campaign_logger.info(
                    f"Found {len(active_campaigns)} active campaigns to process"
                )

                if self.config.DEBUG_MODE:
                    for campaign in active_campaigns:
                        campaign_logger.debug(
                            f"🐛 Campaign {campaign.id}: '{campaign.name}' (User: {campaign.user_did})"
                        )

                for campaign in active_campaigns:
                    try:
                        result = self.process_single_campaign(campaign.id, db)
                        if result:
                            total_campaigns_processed += 1
                            total_follows += result.get("follows_count", 0)
                            total_unfollows += result.get("unfollows_count", 0)
                            total_follow_backs += result.get("follow_backs_count", 0)
                    except Exception as e:
                        log_exception(
                            campaign_logger,
                            f"Error processing campaign {campaign.id}",
                            e,
                        )
                        continue

            finally:
                db.close()

            # Track successful completion
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            track_rq_job("campaign_daily_execution", "success")

            result_message = (
                f"Daily campaign processing completed successfully. "
                f"Processed {total_campaigns_processed} campaigns in {execution_time:.1f}s. "
                f"Follows: {total_follows}, Unfollows: {total_unfollows}, "
                f"Follow-backs detected: {total_follow_backs}"
            )

            campaign_logger.info(result_message)
            return result_message

        except Exception as e:
            track_rq_job("campaign_daily_execution", "error")
            error_message = f"Error in daily campaign processing: {e}"
            campaign_logger.error(error_message)
            return error_message

    def process_single_campaign(self, campaign_id: int, db: Session) -> Dict[str, Any]:
        """Process a single campaign for the day"""
        campaign_start_time = datetime.utcnow()

        try:
            log_campaign_event(campaign_id, "Processing campaign")

            # Get campaign details
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                campaign_logger.warning(f"Campaign {campaign_id} not found")
                return {}

            # Get OAuth session for the campaign user
            oauth_session = (
                db.query(OAuthSession)
                .filter(OAuthSession.did == campaign.user_did)
                .first()
            )

            if not oauth_session:
                campaign_logger.warning(
                    f"No OAuth session found for campaign {campaign_id}"
                )
                return {}

            # Check for follow-backs first
            follow_backs_count = self.check_follow_backs(campaign_id, oauth_session, db)

            # Process follows (respecting daily limit)
            follows_count = self.process_follows(campaign_id, oauth_session, db)

            # Process unfollows (accounts that haven't followed back)
            unfollows_count = self.process_unfollows(campaign_id, oauth_session, db)

            # Log execution
            execution_duration = int(
                (datetime.utcnow() - campaign_start_time).total_seconds()
            )

            self.log_campaign_execution(
                campaign_id=campaign_id,
                follows_count=follows_count,
                unfollows_count=unfollows_count,
                follow_backs_count=follow_backs_count,
                execution_duration_seconds=execution_duration,
                db=db,
            )

            # Track metrics
            CampaignMetrics.track_daily_execution(
                campaign_id, follows_count, unfollows_count, follow_backs_count
            )

            return {
                "follows_count": follows_count,
                "unfollows_count": unfollows_count,
                "follow_backs_count": follow_backs_count,
            }

        except Exception as e:
            log_exception(
                campaign_logger, f"Error processing campaign {campaign_id}", e
            )
            # Log failed execution
            self.log_campaign_execution(
                campaign_id=campaign_id,
                follows_count=0,
                unfollows_count=0,
                follow_backs_count=0,
                errors_count=1,
                status="failed",
                error_message=str(e),
                db=db,
            )
            return {}

    def check_follow_backs(self, campaign_id: int, oauth_session, db: Session) -> int:
        """Check for accounts that have followed back"""
        log_campaign_event(campaign_id, "Checking follow-backs")

        # Get accounts we're following but haven't confirmed follow-back yet
        accounts_to_check = (
            db.query(FollowersToGet)
            .filter(
                and_(
                    FollowersToGet.campaign_id == campaign_id,
                    FollowersToGet.me_following.isnot(None),
                    FollowersToGet.is_following_me.is_(None),
                    FollowersToGet.unfollowed_at.is_(None),
                )
            )
            .limit(20)
            .all()
        )  # Limit to prevent API overload

        follow_backs_detected = 0

        for account in accounts_to_check:
            try:
                # Check if they're following us back
                is_following_back = self.check_if_following_back(
                    account.account_handle, oauth_session, db
                )

                if is_following_back:
                    account.is_following_me = datetime.utcnow()
                    account.status = CAMPAIGN_EXECUTION_STATES["FOLLOWING_BACK"]
                    follow_backs_detected += 1
                    campaign_logger.info(
                        f"✓ {account.account_handle} is following back!"
                    )

                account.last_checked_at = datetime.utcnow()

                # Rate limiting
                time.sleep(self.config.REQUEST_DELAY_SECONDS)

            except Exception as e:
                log_exception(
                    campaign_logger,
                    f"Error checking follow-back for {account.account_handle}",
                    e,
                )
                continue

        if accounts_to_check:
            db.commit()
            log_campaign_event(
                campaign_id, f"Detected {follow_backs_detected} new follow-backs"
            )

        return follow_backs_detected

    def process_follows(self, campaign_id: int, oauth_session, db: Session) -> int:
        """Process new follows for the campaign (respecting daily limits)"""
        log_campaign_event(campaign_id, "Processing follows")

        # Check today's follow count
        today = datetime.utcnow().date()
        today_follows = (
            db.query(FollowersToGet)
            .filter(
                and_(
                    FollowersToGet.campaign_id == campaign_id,
                    FollowersToGet.me_following.isnot(None),
                    func.date(FollowersToGet.me_following) == today,
                )
            )
            .count()
        )

        remaining_follows = max(0, self.config.MAX_FOLLOWS_PER_DAY - today_follows)

        if remaining_follows == 0:
            log_campaign_event(campaign_id, "Daily follow limit already reached")
            return 0

        # Get accounts ready to follow
        accounts_to_follow = (
            db.query(FollowersToGet)
            .filter(
                and_(
                    FollowersToGet.campaign_id == campaign_id,
                    FollowersToGet.me_following.is_(None),
                    FollowersToGet.unfollowed_at.is_(None),
                    FollowersToGet.follow_attempt_count
                    < self.config.MAX_FOLLOW_ATTEMPTS,
                )
            )
            .limit(remaining_follows)
            .all()
        )

        follows_count = 0

        for account in accounts_to_follow:
            try:
                success = self.follow_account(account, oauth_session, db)
                if success:
                    follows_count += 1
                    account.me_following = datetime.utcnow()
                    account.status = CAMPAIGN_EXECUTION_STATES["WAITING_FOR_FOLLOWBACK"]

                # Rate limiting
                time.sleep(self.config.REQUEST_DELAY_SECONDS)

            except Exception as e:
                log_exception(
                    campaign_logger, f"Error following {account.account_handle}", e
                )
                account.follow_attempt_count += 1
                continue

        if accounts_to_follow:
            db.commit()
            log_campaign_event(
                campaign_id, f"Successfully followed {follows_count} accounts"
            )

        return follows_count

    def process_unfollows(self, campaign_id: int, oauth_session, db: Session) -> int:
        """Process unfollows for accounts that haven't followed back"""
        log_campaign_event(campaign_id, "Processing unfollows")

        cutoff_date = self.config.get_unfollow_cutoff_date()

        # Get accounts to unfollow
        accounts_to_unfollow = (
            db.query(FollowersToGet)
            .filter(
                and_(
                    FollowersToGet.campaign_id == campaign_id,
                    FollowersToGet.me_following.isnot(None),
                    FollowersToGet.me_following < cutoff_date,
                    FollowersToGet.is_following_me.is_(None),
                    FollowersToGet.unfollowed_at.is_(None),
                    FollowersToGet.unfollow_attempt_count
                    < self.config.MAX_UNFOLLOW_ATTEMPTS,
                )
            )
            .limit(self.config.MAX_UNFOLLOWS_PER_DAY)
            .all()
        )

        unfollows_count = 0

        for account in accounts_to_unfollow:
            try:
                success = self.unfollow_account(account, oauth_session, db)
                if success:
                    unfollows_count += 1
                    account.unfollowed_at = datetime.utcnow()
                    account.status = CAMPAIGN_EXECUTION_STATES["UNFOLLOWED"]

                account.unfollow_attempt_count += 1

                # Rate limiting
                time.sleep(self.config.REQUEST_DELAY_SECONDS)

            except Exception as e:
                log_exception(
                    campaign_logger, f"Error unfollowing {account.account_handle}", e
                )
                account.unfollow_attempt_count += 1
                continue

        if accounts_to_unfollow:
            db.commit()
            log_campaign_event(
                campaign_id, f"Successfully unfollowed {unfollows_count} accounts"
            )

        return unfollows_count

    def follow_account(
        self, follower_record: FollowersToGet, oauth_session, db: Session
    ) -> bool:
        """Follow a specific account"""
        try:
            # Get the target account's DID
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={follower_record.account_handle}"
            profile_resp = req("GET", profile_url, timeout=30)

            if profile_resp.status_code not in [200, 201]:
                campaign_logger.warning(
                    f"Failed to get profile for {follower_record.account_handle}"
                )
                return False

            target_did = profile_resp.json().get("did")
            if not target_did:
                campaign_logger.warning(
                    f"No DID found for {follower_record.account_handle}"
                )
                return False

            # Create follow record
            follow_payload = {
                "$type": "app.bsky.graph.follow",
                "subject": target_did,
                "createdAt": datetime.utcnow().isoformat() + "Z",
            }

            create_record_url = (
                f"{oauth_session.pds_url}/xrpc/com.atproto.repo.createRecord"
            )
            create_record_payload = {
                "repo": oauth_session.did,
                "collection": "app.bsky.graph.follow",
                "record": follow_payload,
            }

            follow_resp = pds_authed_req(
                "POST",
                create_record_url,
                access_token=oauth_session.access_token,
                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                user_did=oauth_session.did,
                db=db,
                dpop_pds_nonce=getattr(oauth_session, "dpop_pds_nonce", "") or "",
                body=create_record_payload,
            )

            if follow_resp.status_code in [200, 201]:
                campaign_logger.info(
                    f"✓ Successfully followed {follower_record.account_handle}"
                )
                return True
            else:
                campaign_logger.warning(
                    f"✗ Failed to follow {follower_record.account_handle}: HTTP {follow_resp.status_code}"
                )
                return False

        except Exception as e:
            log_exception(
                campaign_logger,
                f"Error in follow_account for {follower_record.account_handle}",
                e,
            )
            return False

    def unfollow_account(
        self, follower_record: FollowersToGet, oauth_session, db: Session
    ) -> bool:
        """Unfollow a specific account by deleting the follow record"""
        try:
            campaign_logger.info(
                f"Attempting to unfollow {follower_record.account_handle}"
            )

            # Step 1: Get the target account's DID
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={follower_record.account_handle}"
            profile_resp = req("GET", profile_url, timeout=30)

            if profile_resp.status_code not in [200, 201]:
                campaign_logger.warning(
                    f"Failed to get profile for {follower_record.account_handle}"
                )
                return False

            target_did = profile_resp.json().get("did")
            if not target_did:
                campaign_logger.warning(
                    f"No DID found for {follower_record.account_handle}"
                )
                return False

            # Step 2: Find our follow records to locate the specific one for this account
            # Construct URL with query parameters for GET request
            list_records_params = {
                "repo": oauth_session.did,
                "collection": "app.bsky.graph.follow",
                "limit": 100,  # Get recent follows
            }

            # Build query string
            from urllib.parse import urlencode

            query_string = urlencode(list_records_params)
            list_records_url = f"{oauth_session.pds_url}/xrpc/com.atproto.repo.listRecords?{query_string}"

            list_resp = pds_authed_req(
                "GET",
                list_records_url,
                access_token=oauth_session.access_token,
                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                user_did=oauth_session.did,
                db=db,
                dpop_pds_nonce=getattr(oauth_session, "dpop_pds_nonce", "") or "",
            )

            if list_resp.status_code not in [200, 201]:
                campaign_logger.error(
                    f"Failed to list follow records: HTTP {list_resp.status_code}"
                )
                return False

            # Step 3: Find the specific follow record for this account
            follow_record_uri = None
            follow_records = list_resp.json().get("records", [])

            for record in follow_records:
                if record.get("value", {}).get("subject") == target_did:
                    follow_record_uri = record.get("uri")
                    break

            if not follow_record_uri:
                campaign_logger.warning(
                    f"No follow record found for {follower_record.account_handle} ({target_did})"
                )
                # This might happen if we already unfollowed or there was an error
                # Consider this a success since the goal (not following) is achieved
                return True

            # Step 4: Delete the follow record to unfollow
            delete_record_url = (
                f"{oauth_session.pds_url}/xrpc/com.atproto.repo.deleteRecord"
            )

            # Extract rkey from URI (format: at://did:plc:xxx/app.bsky.graph.follow/rkey)
            rkey = follow_record_uri.split("/")[-1]

            delete_record_payload = {
                "repo": oauth_session.did,
                "collection": "app.bsky.graph.follow",
                "rkey": rkey,
            }

            campaign_logger.debug(f"Deleting follow record: {follow_record_uri}")

            delete_resp = pds_authed_req(
                "POST",
                delete_record_url,
                access_token=oauth_session.access_token,
                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                user_did=oauth_session.did,
                db=db,
                dpop_pds_nonce=getattr(oauth_session, "dpop_pds_nonce", "") or "",
                body=delete_record_payload,
            )

            if delete_resp.status_code in [200, 201]:
                campaign_logger.info(
                    f"✓ Successfully unfollowed {follower_record.account_handle}"
                )
                return True
            else:
                campaign_logger.warning(
                    f"✗ Failed to unfollow {follower_record.account_handle}: HTTP {delete_resp.status_code}"
                )
                try:
                    error_data = delete_resp.json()
                    campaign_logger.error(f"Error details: {error_data}")
                except:
                    campaign_logger.error(f"Error response: {delete_resp.text[:200]}")
                return False

        except Exception as e:
            log_exception(
                campaign_logger,
                f"Error in unfollow_account for {follower_record.account_handle}",
                e,
            )
            return False

    def check_if_following_back(
        self, account_handle: str, oauth_session, db: Session
    ) -> bool:
        """Check if an account is following us back by checking our followers"""
        try:
            campaign_logger.debug(f"Checking if {account_handle} is following back")

            # Step 1: Get the account's DID
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={account_handle}"
            profile_resp = req("GET", profile_url, timeout=30)

            if profile_resp.status_code not in [200, 201]:
                campaign_logger.warning(f"Failed to get profile for {account_handle}")
                return False

            target_did = profile_resp.json().get("did")
            if not target_did:
                campaign_logger.warning(f"No DID found for {account_handle}")
                return False

            # Step 2: Check if they appear in our followers list
            # Use public API to get our followers
            from urllib.parse import urlencode

            followers_params = {
                "actor": oauth_session.did,
                "limit": 100,
            }

            query_string = urlencode(followers_params)
            followers_url = f"https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?{query_string}"

            # Check multiple pages if necessary (limited search for performance)
            for page in range(3):  # Check first 3 pages (300 followers max)
                if page > 0:
                    # Add cursor for pagination
                    followers_params["cursor"] = cursor
                    query_string = urlencode(followers_params)
                    followers_url = f"https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?{query_string}"

                followers_resp = req("GET", followers_url, timeout=30)

                if followers_resp.status_code not in [200, 201]:
                    campaign_logger.error(
                        f"Failed to get followers: HTTP {followers_resp.status_code}"
                    )
                    break

                followers_data = followers_resp.json()
                followers = followers_data.get("followers", [])

                # Check if target_did is in our followers
                for follower in followers:
                    if follower.get("did") == target_did:
                        campaign_logger.info(f"✓ {account_handle} is following back!")
                        return True

                # Check if there are more pages
                cursor = followers_data.get("cursor")
                if not cursor or len(followers) == 0:
                    break

                # Rate limiting between pages
                time.sleep(1)

            campaign_logger.debug(f"✗ {account_handle} is not following back")
            return False

        except Exception as e:
            log_exception(
                campaign_logger, f"Error checking follow-back for {account_handle}", e
            )
            return False

    def log_campaign_execution(
        self,
        campaign_id: int,
        follows_count: int = 0,
        unfollows_count: int = 0,
        follow_backs_count: int = 0,
        errors_count: int = 0,
        execution_duration_seconds: int = 0,
        status: str = "success",
        error_message: str = None,
        db: Session = None,
    ):
        """Log campaign execution results"""
        if not db:
            db = next(get_db())
            should_close = True
        else:
            should_close = False

        try:
            log_entry = CampaignExecutionLog(
                campaign_id=campaign_id,
                execution_date=datetime.utcnow(),
                follows_count=follows_count,
                unfollows_count=unfollows_count,
                follow_backs_count=follow_backs_count,
                errors_count=errors_count,
                execution_duration_seconds=execution_duration_seconds,
                status=status,
                error_message=error_message,
            )

            db.add(log_entry)
            db.commit()

        except Exception as e:
            log_exception(campaign_logger, "Error logging campaign execution", e)
            if db:
                db.rollback()
        finally:
            if should_close:
                db.close()


# Main worker function for RQ
def process_daily_campaigns() -> str:
    """Main entry point for daily campaign processing worker"""
    worker = DailyCampaignWorker()
    return worker.process_all_active_campaigns()
