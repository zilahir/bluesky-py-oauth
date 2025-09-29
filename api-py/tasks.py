import time
from typing import Dict, Any, List

from requests import request as req
from sqlalchemy.orm import Session
import os

# Import metrics tracking functions
from metrics import track_rq_job, track_followers_processed
from logger_config import task_logger, log_exception, log_campaign_event

os.environ["no_proxy"] = "*"

from routes.utils.postgres_connection import (
    get_db,
    Campaign,
    FollowersToGet,
    OAuthSession,
)
from queue_config import get_queue
from atproto_oauth import pds_authed_req
from datetime import datetime

ACCOUNTS_TO_FOLLOW_PER_DAY = 10


def get_all_followers_for_account(handle: str, user_did: str = None) -> List[Dict]:
    """
    Fetch all followers for a given account handle using Bluesky API with pagination.

    Args:
        handle: The account handle to fetch followers for
        user_did: Current user's DID to exclude from followers list

    Returns:
        List of follower dictionaries (excludes current user if user_did provided)
    """
    try:
        print(
            f"get_all_followers_for_account --- Fetching followers for account: {handle}"
        )

        if not handle or not handle.strip():
            print("Error: Empty handle provided")
            return []

        # First get the account's DID

        print(f"executing profile request for handle: {handle.strip()}")
        try:
            profile_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={handle.strip()}"
            profile_resp = req("GET", profile_url, timeout=30)

            if profile_resp.status_code not in [200, 201]:
                print(
                    f"Failed to get profile for {handle}: HTTP {profile_resp.status_code}"
                )
                try:
                    error_data = profile_resp.json()
                    print(f"Error details: {error_data}")
                except:
                    print(f"Error body: {profile_resp.text[:200]}")
                return []

            profile_resp.raise_for_status()
            profile_data = profile_resp.json()

            if "did" not in profile_data:
                print(f"No DID found in profile response for {handle}")
                return []

            did = profile_data["did"]
            print(f"Found DID for {handle}: {did}")

        except Exception as e:
            print(f"Error getting profile for {handle}: {e}")
            return []

        # Now fetch all followers with pagination
        followers = []
        cursor = None
        page_count = 0

        while True:
            try:
                page_count += 1
                print(f"Fetching followers page {page_count} for {handle}")

                followers_url = f"https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?actor={did}&limit=100"
                if cursor:
                    followers_url += f"&cursor={cursor}"

                # Rate limiting - wait 1 second between requests
                time.sleep(1)

                resp = req("GET", followers_url, timeout=30)

                if resp.status_code not in [200, 201]:
                    print(
                        f"API Error fetching followers for {handle}: HTTP {resp.status_code}"
                    )
                    try:
                        error_data = resp.json()
                        print(f"Error details: {error_data}")
                    except:
                        print(f"Error body: {resp.text[:200]}")
                    break

                resp.raise_for_status()
                data = resp.json()

                page_followers = data.get("followers", [])

                # Filter out current user if user_did is provided
                if user_did:
                    filtered_followers = []
                    for follower in page_followers:
                        follower_did = follower.get("did", "")
                        follower_handle = follower.get("handle", "")

                        # Skip if this follower is the current user (match by DID or handle)
                        if follower_did == user_did:
                            print(
                                f"Excluding current user from followers (DID match): {follower_handle}"
                            )
                            continue

                        filtered_followers.append(follower)

                    followers.extend(filtered_followers)

                    excluded_count = len(page_followers) - len(filtered_followers)
                    if excluded_count > 0:
                        print(
                            f"Excluded {excluded_count} follower(s) matching current user on page {page_count}"
                        )
                else:
                    followers.extend(page_followers)

                # Calculate how many followers were actually added after filtering
                if user_did:
                    added_count = len(filtered_followers)
                    print(
                        f"Fetched {len(page_followers)} followers on page {page_count} ({added_count} after filtering), total: {len(followers)}"
                    )
                else:
                    print(
                        f"Fetched {len(page_followers)} followers on page {page_count}, total: {len(followers)}"
                    )

                cursor = data.get("cursor", None)

                # Break if no cursor (last page) or no followers returned
                if not cursor or len(page_followers) == 0:
                    break

                # Safety check to prevent infinite loops
                if page_count > 1000:  # Adjust as needed
                    print(f"Reached maximum page limit for {handle}")
                    break

            except Exception as e:
                print(f"Error fetching followers page {page_count} for {handle}: {e}")
                break

        print(
            f"Finished fetching followers for {handle}: {len(followers)} total followers"
        )
        return followers

    except Exception as e:
        print(f"Unexpected error in get_all_followers_for_account for {handle}: {e}")
        return []


def get_user_current_followers(user_did: str) -> set:
    """
    Get all current followers for a user to exclude them from campaign targets.

    Args:
        user_did: The user's DID

    Returns:
        Set of follower handles that are already following the user
    """
    try:
        task_logger.info(f"Fetching current followers for user: {user_did}")

        current_followers = set()
        cursor = None
        page_count = 0
        max_pages = 50  # Limit to prevent excessive API calls (5000 followers max)

        while page_count < max_pages:
            try:
                page_count += 1

                # Build followers URL with pagination
                followers_url = f"https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?actor={user_did}&limit=100"
                if cursor:
                    followers_url += f"&cursor={cursor}"

                task_logger.debug(f"Fetching followers page {page_count} for user")

                # Rate limiting
                time.sleep(1)

                resp = req("GET", followers_url, timeout=30)

                if resp.status_code not in [200, 201]:
                    task_logger.error(f"Error fetching user followers: HTTP {resp.status_code}")
                    break

                data = resp.json()
                page_followers = data.get("followers", [])

                # Add handles to the set
                for follower in page_followers:
                    handle = follower.get("handle", "")
                    if handle:
                        current_followers.add(handle.lower())  # Normalize to lowercase

                task_logger.debug(f"Page {page_count}: Found {len(page_followers)} followers, total: {len(current_followers)}")

                # Get cursor for next page
                cursor = data.get("cursor", None)

                # Break if no more pages
                if not cursor or len(page_followers) == 0:
                    break

            except Exception as e:
                task_logger.error(f"Error fetching followers page {page_count}: {e}")
                break

        task_logger.info(f"Found {len(current_followers)} current followers for user")
        return current_followers

    except Exception as e:
        log_exception(task_logger, "Error getting user current followers", e)
        return set()


def save_followers_to_db(
    campaign_id: int, account_handle: str, followers: List[Dict], exclude_followers: set = None
) -> None:
    """
    Save followers to the followers_to_get table.

    Args:
        campaign_id: The campaign ID
        account_handle: The account handle these followers belong to
        followers: List of follower data from Bluesky API
        exclude_followers: Set of follower handles to exclude (already following us)
    """
    if exclude_followers is None:
        exclude_followers = set()

    task_logger.info(f"Saving {len(followers)} followers for {account_handle} to database (excluding {len(exclude_followers)} existing followers)")

    # Create a fresh database session for this operation
    from routes.utils.postgres_connection import SessionLocal

    db = SessionLocal()

    try:
        # Get existing followers for this campaign to avoid duplicates
        existing_handles = set()
        existing_followers = (
            db.query(FollowersToGet.account_handle)
            .filter(FollowersToGet.campaign_id == campaign_id)
            .all()
        )
        for row in existing_followers:
            existing_handles.add(row[0])

        # Prepare new followers data, filtering out existing ones and current followers
        new_followers = []
        excluded_existing = 0
        excluded_current_followers = 0

        for follower in followers:
            follower_handle = follower.get("handle", "")
            if not follower_handle:
                continue

            # Skip if already in database
            if follower_handle in existing_handles:
                excluded_existing += 1
                continue

            # Skip if already following us
            if follower_handle.lower() in exclude_followers:
                excluded_current_followers += 1
                continue

            new_follower = FollowersToGet(
                campaign_id=campaign_id,
                account_handle=follower_handle,
                me_following=None,  # Will be set to timestamp when followed
                is_following_me=None,  # Will be set to timestamp when they follow back
            )
            new_followers.append(new_follower)

        if new_followers:
            # Bulk insert new followers
            db.add_all(new_followers)
            db.commit()

            task_logger.info(
                f"Successfully added {len(new_followers)} new followers for {account_handle}"
            )
            task_logger.info(f"Excluded {excluded_existing} existing followers from database")
            task_logger.info(f"Excluded {excluded_current_followers} accounts already following us")

            # Track followers processed
            track_followers_processed(str(campaign_id), len(new_followers))
        else:
            task_logger.info(
                f"No new followers to add for {account_handle}. Excluded: {excluded_existing} existing + {excluded_current_followers} current followers"
            )

    except Exception as e:
        log_exception(task_logger, f"Error saving followers for {account_handle}", e)
        db.rollback()
        # Track error
        track_rq_job("campaign_get_all_followers", "error")
        raise e
    finally:
        db.close()


def process_campaign_task(campaign_data: Dict[str, Any]) -> str:
    """
    Placeholder task function for processing campaign creation.

    Args:
        campaign_data: Dictionary containing campaign information

    Returns:
        str: Task completion message
    """
    campaign_id = campaign_data.get("campaign_id", None)

    if not campaign_id:
        print("Error: No campaign ID provided")
        return "Error: No campaign ID provided"

    # Get campaign from database and extract needed data
    db = next(get_db())
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

        if not campaign:
            print(f"Error: Campaign with ID {campaign_id} not found")
            return f"Error: Campaign with ID {campaign_id} not found"

        # Extract data we need before closing the session
        campaign_name = campaign.name
        campaign_user_did = campaign.user_did
        campaign_total_followers = campaign.total_followers_to_get
        followers_to_get = campaign.followers_to_get or []

        print(f"Starting campaign processing for: {campaign_name}")
        print(f"Campaign ID: {campaign_id}")
        print(f"User DID: {campaign_user_did}")
        print(f"Total followers to get: {campaign_total_followers}")
        print(f"Accounts to follow: {len(followers_to_get)} accounts")

    except Exception as e:
        print(f"Error fetching campaign: {e}")
        return f"Error fetching campaign: {e}"
    finally:
        db.close()

    # Get user's current followers to exclude them from campaign
    task_logger.info("Getting user's current followers to exclude from campaign...")
    current_followers = get_user_current_followers(campaign_user_did)
    task_logger.info(f"Found {len(current_followers)} current followers to exclude")

    # Process each account in followers_to_get
    if followers_to_get:
        print(f"Processing {len(followers_to_get)} accounts for followers...")

        for account in followers_to_get:
            try:
                # Handle both string and dict formats
                if isinstance(account, dict):
                    account_handle = account.get("handle", "")
                else:
                    account_handle = str(account)

                if not account_handle:
                    print("Skipping empty account handle")
                    continue

                print(f"\nProcessing account: {account_handle}")

                # Fetch all followers for this account
                followers = get_all_followers_for_account(
                    account_handle, campaign_user_did
                )

                if followers:
                    # Save followers to database (excluding current followers)
                    save_followers_to_db(campaign_id, account_handle, followers, current_followers)
                    task_logger.info(f"Processed {len(followers)} followers for {account_handle}")
                else:
                    task_logger.info(f"No followers found for {account_handle}")

            except Exception as e:
                log_exception(task_logger, f"Error processing account {account}", e)
                continue  # Continue with next account

        task_logger.info(f"Completed processing all accounts for campaign: {campaign_name}")

        # Track successful completion
        track_rq_job("campaign_get_all_followers", "success")

        # set the is_setup_job_running to False on the campaign
        db = next(get_db())
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                campaign.is_setup_job_running = False
                db.commit()
                log_campaign_event(campaign_id, f"Campaign '{campaign_name}' setup completed and ready for daily execution")
                task_logger.info(f"Campaign {campaign_id} will be processed automatically by the daily scheduler")

            else:
                task_logger.warning(f"Campaign with ID {campaign_id} not found for update")
        except Exception as e:
            log_exception(task_logger, "Error updating campaign status", e)
            db.rollback()
        finally:
            db.close()
    else:
        print("No accounts to process in followers_to_get")

    return f"Campaign '{campaign_name}' processed successfully"