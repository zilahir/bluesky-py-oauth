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
from metrics import (
    track_rq_job,
    track_follow_attempt,
    track_unfollow_attempt,
    track_bluesky_api_request,
    track_authentication_failure,
    update_active_campaigns_count,
)
from atproto_oauth import refresh_token_request
from settings import get_settings
from oauth_metadata import OauthMetadata
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

                # Update Prometheus metric with current active campaign count
                update_active_campaigns_count(len(active_campaigns))

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
        """Follow a specific account with detailed logging and metrics"""
        campaign_id = str(follower_record.campaign_id)
        account_handle = follower_record.account_handle

        start_time = time.time()

        try:
            campaign_logger.info(
                f"🎯 Attempting to follow {account_handle} (Campaign: {campaign_id})"
            )

            # Get the target account's DID
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={account_handle}"

            profile_start = time.time()
            profile_resp = req("GET", profile_url, timeout=30)
            profile_duration = time.time() - profile_start

            # Track API request
            track_bluesky_api_request(
                "getProfile", "GET", profile_resp.status_code, profile_duration
            )

            if profile_resp.status_code not in [200, 201]:
                failure_reason = "profile_api_error"
                campaign_logger.error(
                    f"❌ Failed to get profile for {account_handle}: HTTP {profile_resp.status_code}"
                )

                # Log response details for debugging
                try:
                    error_body = profile_resp.json()
                    campaign_logger.error(f"Profile API error details: {error_body}")
                except:
                    campaign_logger.error(
                        f"Profile API error body: {profile_resp.text[:200]}"
                    )

                track_follow_attempt(campaign_id, False, failure_reason)
                return False

            try:
                profile_data = profile_resp.json()
                target_did = profile_data.get("did")
            except Exception as e:
                failure_reason = "profile_parse_error"
                campaign_logger.error(
                    f"❌ Failed to parse profile response for {account_handle}: {e}"
                )
                track_follow_attempt(campaign_id, False, failure_reason)
                return False

            if not target_did:
                failure_reason = "no_did_found"
                campaign_logger.error(
                    f"❌ No DID found in profile for {account_handle}"
                )
                track_follow_attempt(campaign_id, False, failure_reason)
                return False

            campaign_logger.debug(f"📍 Found DID for {account_handle}: {target_did}")

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

            campaign_logger.debug(
                f"🔄 Creating follow record for {account_handle} at {create_record_url}"
            )

            follow_start = time.time()
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
            follow_duration = time.time() - follow_start

            # Track API request
            track_bluesky_api_request(
                "createRecord", "POST", follow_resp.status_code, follow_duration
            )

            total_duration = time.time() - start_time

            if follow_resp.status_code in [200, 201]:
                campaign_logger.info(
                    f"✅ Successfully followed {account_handle} in {total_duration:.2f}s (Campaign: {campaign_id})"
                )
                track_follow_attempt(campaign_id, True)
                return True
            else:
                # Check if this is a token expiry error and attempt refresh + retry
                try:
                    error_body = follow_resp.json()
                    is_token_expired = (
                        follow_resp.status_code == 400
                        and error_body.get("error") == "invalid_token"
                        and "exp" in error_body.get("message", "")
                    )

                    if is_token_expired:
                        campaign_logger.warning(
                            f"🔄 Token expired for {account_handle}, attempting refresh and retry"
                        )
                        track_authentication_failure("token_expired")

                        # Attempt to refresh the token
                        if self.refresh_oauth_token(oauth_session, db):
                            campaign_logger.info(
                                f"🔄 Token refreshed, retrying follow for {account_handle}"
                            )

                            # Retry the follow operation with refreshed token
                            retry_start = time.time()
                            retry_resp = pds_authed_req(
                                "POST",
                                create_record_url,
                                access_token=oauth_session.access_token,
                                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                                user_did=oauth_session.did,
                                db=db,
                                dpop_pds_nonce=getattr(
                                    oauth_session, "dpop_pds_nonce", ""
                                )
                                or "",
                                body=create_record_payload,
                            )
                            retry_duration = time.time() - retry_start

                            # Track the retry API request
                            track_bluesky_api_request(
                                "createRecord",
                                "POST",
                                retry_resp.status_code,
                                retry_duration,
                            )

                            if retry_resp.status_code in [200, 201]:
                                total_duration = time.time() - start_time
                                campaign_logger.info(
                                    f"✅ Successfully followed {account_handle} after token refresh in {total_duration:.2f}s (Campaign: {campaign_id})"
                                )
                                track_follow_attempt(campaign_id, True)
                                return True
                            else:
                                campaign_logger.error(
                                    f"❌ Follow retry failed for {account_handle} even after token refresh"
                                )
                                try:
                                    retry_error_body = retry_resp.json()
                                    campaign_logger.error(
                                        f"Retry error details: {retry_error_body}"
                                    )
                                except:
                                    campaign_logger.error(
                                        f"Retry error body: {retry_resp.text[:200]}"
                                    )
                        else:
                            campaign_logger.error(
                                f"❌ Token refresh failed for {account_handle}"
                            )
                            track_authentication_failure("token_refresh_failed")

                except Exception as parse_error:
                    campaign_logger.error(
                        f"Error parsing follow response: {parse_error}"
                    )

                # Original failure handling (for non-token errors or after failed refresh)
                failure_reason = self._categorize_follow_failure(
                    follow_resp.status_code, follow_resp
                )
                campaign_logger.error(
                    f"❌ Failed to follow {account_handle}: HTTP {follow_resp.status_code} in {total_duration:.2f}s (Campaign: {campaign_id})"
                )

                # Log detailed error information
                try:
                    error_body = follow_resp.json()
                    campaign_logger.error(f"Follow API error details: {error_body}")
                    if "message" in error_body:
                        campaign_logger.error(f"Error message: {error_body['message']}")
                except:
                    campaign_logger.error(
                        f"Follow API error body: {follow_resp.text[:200]}"
                    )

                track_follow_attempt(campaign_id, False, failure_reason)
                return False

        except Exception as e:
            total_duration = time.time() - start_time
            failure_reason = self._categorize_exception(e)

            campaign_logger.error(
                f"💥 Exception during follow attempt for {account_handle}: {type(e).__name__} in {total_duration:.2f}s (Campaign: {campaign_id})"
            )

            log_exception(
                campaign_logger,
                f"Follow exception details for {account_handle}",
                e,
            )

            track_follow_attempt(campaign_id, False, failure_reason)
            return False

    def _categorize_follow_failure(self, status_code: int, response) -> str:
        """Categorize follow failure based on HTTP status code and response"""
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 429:
            return "rate_limited"
        elif status_code >= 500:
            return "server_error"
        else:
            return "api_error"

    def _categorize_unfollow_failure(self, status_code: int, response) -> str:
        """Categorize unfollow failure based on HTTP status code and response"""
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "record_not_found"
        elif status_code == 429:
            return "rate_limited"
        elif status_code >= 500:
            return "server_error"
        else:
            return "api_error"

    def _categorize_exception(self, exception: Exception) -> str:
        """Categorize exceptions into failure types"""
        exception_type = type(exception).__name__
        exception_str = str(exception).lower()

        if "timeout" in exception_str or "timed out" in exception_str:
            return "timeout"
        elif "connection" in exception_str or "network" in exception_str:
            return "network_error"
        elif "json" in exception_str or "decode" in exception_str:
            return "parse_error"
        elif "auth" in exception_str or "token" in exception_str:
            return "auth_error"
        else:
            return "unknown_exception"

    def refresh_oauth_token(self, oauth_session, db: Session) -> bool:
        """Refresh OAuth token for a campaign user"""
        try:
            campaign_logger.info(
                f"🔄 Attempting to refresh OAuth token for user: {oauth_session.did}"
            )

            # Get settings for client_secret_jwk
            settings = get_settings()

            # Create user dict in the format expected by refresh_token_request
            user_dict = {
                "authserver_iss": oauth_session.authserver_iss,
                "refresh_token": oauth_session.refresh_token,
                "dpop_private_jwk": oauth_session.dpop_private_jwk,
                "dpop_authserver_nonce": oauth_session.dpop_authserver_nonce,
            }

            campaign_logger.debug(f"🔍 User dict for token refresh: {user_dict}")

            # Get the correct app URL from OAuth metadata
            oauth_config = OauthMetadata(
                "development"
            )  # TODO: Get environment from config
            app_url = oauth_config.ORIGIN

            # Request new tokens
            tokens, dpop_authserver_nonce = refresh_token_request(
                user_dict, app_url, settings.client_secret_jwk_obj
            )

            # Update the OAuth session with new tokens
            oauth_session.access_token = tokens["access_token"]
            oauth_session.refresh_token = tokens["refresh_token"]
            oauth_session.dpop_authserver_nonce = dpop_authserver_nonce
            oauth_session.updated_at = datetime.utcnow()

            db.commit()

            campaign_logger.info(
                f"✅ Successfully refreshed OAuth token for user: {oauth_session.did}"
            )
            return True

        except Exception as e:
            campaign_logger.error(
                f"❌ Failed to refresh OAuth token for user {oauth_session.did}: {e}"
            )
            log_exception(
                campaign_logger, f"Token refresh error for {oauth_session.did}", e
            )
            track_authentication_failure("token_refresh_failed")
            db.rollback()
            return False

    def unfollow_account(
        self, follower_record: FollowersToGet, oauth_session, db: Session
    ) -> bool:
        """Unfollow a specific account by deleting the follow record with detailed logging"""
        campaign_id = str(follower_record.campaign_id)
        account_handle = follower_record.account_handle

        start_time = time.time()

        try:
            campaign_logger.info(
                f"🎯 Attempting to unfollow {account_handle} (Campaign: {campaign_id})"
            )

            # Step 1: Get the target account's DID
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={account_handle}"

            profile_start = time.time()
            profile_resp = req("GET", profile_url, timeout=30)
            profile_duration = time.time() - profile_start

            # Track API request
            track_bluesky_api_request(
                "getProfile", "GET", profile_resp.status_code, profile_duration
            )

            if profile_resp.status_code not in [200, 201]:
                failure_reason = "profile_api_error"
                campaign_logger.error(
                    f"❌ Failed to get profile for {account_handle}: HTTP {profile_resp.status_code}"
                )

                try:
                    error_body = profile_resp.json()
                    campaign_logger.error(f"Profile API error details: {error_body}")
                except:
                    campaign_logger.error(
                        f"Profile API error body: {profile_resp.text[:200]}"
                    )

                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

            try:
                profile_data = profile_resp.json()
                target_did = profile_data.get("did")
            except Exception as e:
                failure_reason = "profile_parse_error"
                campaign_logger.error(
                    f"❌ Failed to parse profile response for {account_handle}: {e}"
                )
                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

            if not target_did:
                failure_reason = "no_did_found"
                campaign_logger.error(
                    f"❌ No DID found in profile for {account_handle}"
                )
                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

            campaign_logger.debug(f"📍 Found DID for {account_handle}: {target_did}")

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

            campaign_logger.debug(
                f"🔄 Listing follow records for {account_handle} at {list_records_url}"
            )

            list_start = time.time()
            list_resp = pds_authed_req(
                "GET",
                list_records_url,
                access_token=oauth_session.access_token,
                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                user_did=oauth_session.did,
                db=db,
                dpop_pds_nonce=getattr(oauth_session, "dpop_pds_nonce", "") or "",
            )
            list_duration = time.time() - list_start

            # Track API request
            track_bluesky_api_request(
                "listRecords", "GET", list_resp.status_code, list_duration
            )

            if list_resp.status_code not in [200, 201]:
                failure_reason = "list_records_api_error"
                campaign_logger.error(
                    f"❌ Failed to list follow records for {account_handle}: HTTP {list_resp.status_code}"
                )

                try:
                    error_body = list_resp.json()
                    campaign_logger.error(f"List records error details: {error_body}")
                except:
                    campaign_logger.error(
                        f"List records error body: {list_resp.text[:200]}"
                    )

                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

            # Step 3: Find the specific follow record for this account
            try:
                follow_records_data = list_resp.json()
                follow_records = follow_records_data.get("records", [])
            except Exception as e:
                failure_reason = "list_records_parse_error"
                campaign_logger.error(
                    f"❌ Failed to parse list records response for {account_handle}: {e}"
                )
                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

            follow_record_uri = None
            campaign_logger.debug(
                f"🔍 Searching through {len(follow_records)} follow records for {account_handle}"
            )

            for record in follow_records:
                if record.get("value", {}).get("subject") == target_did:
                    follow_record_uri = record.get("uri")
                    campaign_logger.debug(
                        f"📎 Found follow record URI: {follow_record_uri}"
                    )
                    break

            if not follow_record_uri:
                campaign_logger.info(
                    f"🤷 No follow record found for {account_handle} ({target_did}) - Already unfollowed or never followed"
                )
                # This might happen if we already unfollowed or there was an error
                # Consider this a success since the goal (not following) is achieved
                track_unfollow_attempt(campaign_id, True, "already_unfollowed")
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

            campaign_logger.debug(f"🗑️ Deleting follow record: {follow_record_uri}")

            delete_start = time.time()
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
            delete_duration = time.time() - delete_start

            # Track API request
            track_bluesky_api_request(
                "deleteRecord", "POST", delete_resp.status_code, delete_duration
            )

            total_duration = time.time() - start_time

            if delete_resp.status_code in [200, 201]:
                campaign_logger.info(
                    f"✅ Successfully unfollowed {account_handle} in {total_duration:.2f}s (Campaign: {campaign_id})"
                )
                track_unfollow_attempt(campaign_id, True)
                return True
            else:
                # Check if this is a token expiry error and attempt refresh + retry
                try:
                    error_data = delete_resp.json()
                    is_token_expired = (
                        delete_resp.status_code == 400
                        and error_data.get("error") == "invalid_token"
                        and "exp" in error_data.get("message", "")
                    )

                    if is_token_expired:
                        campaign_logger.warning(
                            f"🔄 Token expired during unfollow for {account_handle}, attempting refresh and retry"
                        )
                        track_authentication_failure("token_expired")

                        # Attempt to refresh the token
                        if self.refresh_oauth_token(oauth_session, db):
                            campaign_logger.info(
                                f"🔄 Token refreshed, retrying unfollow for {account_handle}"
                            )

                            # Retry the delete operation with refreshed token
                            retry_start = time.time()
                            retry_resp = pds_authed_req(
                                "POST",
                                delete_record_url,
                                access_token=oauth_session.access_token,
                                dpop_private_jwk_json=oauth_session.dpop_private_jwk,
                                user_did=oauth_session.did,
                                db=db,
                                dpop_pds_nonce=getattr(
                                    oauth_session, "dpop_pds_nonce", ""
                                )
                                or "",
                                body=delete_record_payload,
                            )
                            retry_duration = time.time() - retry_start

                            # Track the retry API request
                            track_bluesky_api_request(
                                "deleteRecord",
                                "POST",
                                retry_resp.status_code,
                                retry_duration,
                            )

                            if retry_resp.status_code in [200, 201]:
                                total_duration = time.time() - start_time
                                campaign_logger.info(
                                    f"✅ Successfully unfollowed {account_handle} after token refresh in {total_duration:.2f}s (Campaign: {campaign_id})"
                                )
                                track_unfollow_attempt(campaign_id, True)
                                return True
                            else:
                                campaign_logger.error(
                                    f"❌ Unfollow retry failed for {account_handle} even after token refresh"
                                )
                                try:
                                    retry_error_data = retry_resp.json()
                                    campaign_logger.error(
                                        f"Retry error details: {retry_error_data}"
                                    )
                                except:
                                    campaign_logger.error(
                                        f"Retry error body: {retry_resp.text[:200]}"
                                    )
                        else:
                            campaign_logger.error(
                                f"❌ Token refresh failed during unfollow for {account_handle}"
                            )
                            track_authentication_failure("token_refresh_failed")

                except Exception as parse_error:
                    campaign_logger.error(
                        f"Error parsing unfollow response: {parse_error}"
                    )

                # Original failure handling (for non-token errors or after failed refresh)
                failure_reason = self._categorize_unfollow_failure(
                    delete_resp.status_code, delete_resp
                )
                campaign_logger.error(
                    f"❌ Failed to unfollow {account_handle}: HTTP {delete_resp.status_code} in {total_duration:.2f}s (Campaign: {campaign_id})"
                )

                # Log detailed error information
                try:
                    error_data = delete_resp.json()
                    campaign_logger.error(f"Delete record error details: {error_data}")
                    if "message" in error_data:
                        campaign_logger.error(f"Error message: {error_data['message']}")
                except:
                    campaign_logger.error(
                        f"Delete record error body: {delete_resp.text[:200]}"
                    )

                track_unfollow_attempt(campaign_id, False, failure_reason)
                return False

        except Exception as e:
            total_duration = time.time() - start_time
            failure_reason = self._categorize_exception(e)

            campaign_logger.error(
                f"💥 Exception during unfollow attempt for {account_handle}: {type(e).__name__} in {total_duration:.2f}s (Campaign: {campaign_id})"
            )

            log_exception(
                campaign_logger,
                f"Unfollow exception details for {account_handle}",
                e,
            )

            track_unfollow_attempt(campaign_id, False, failure_reason)
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
