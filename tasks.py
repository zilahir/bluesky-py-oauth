import time
from typing import Dict, Any, List

from requests import request as req
from sqlalchemy.orm import Session
import os

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


def get_all_followers_for_account(handle: str) -> List[Dict]:
    """
    Fetch all followers for a given account handle using Bluesky API with pagination.

    Args:
        handle: The account handle to fetch followers for

    Returns:
        List of follower dictionaries
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
                followers.extend(page_followers)

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


def save_followers_to_db(
    campaign_id: int, account_handle: str, followers: List[Dict]
) -> None:
    """
    Save followers to the followers_to_get table.

    Args:
        campaign_id: The campaign ID
        account_handle: The account handle these followers belong to
        followers: List of follower data from Bluesky API
    """
    print(f"Saving {len(followers)} followers for {account_handle} to database")

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

        # Prepare new followers data, filtering out existing ones
        new_followers = []
        for follower in followers:
            follower_handle = follower.get("handle", "")
            if follower_handle and follower_handle not in existing_handles:
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

            print(
                f"Successfully added {len(new_followers)} new followers for {account_handle}"
            )
            print(f"Skipped {len(followers) - len(new_followers)} existing followers")
        else:
            print(
                f"All {len(followers)} followers for {account_handle} already exist in database"
            )

    except Exception as e:
        print(f"Error saving followers for {account_handle}: {e}")
        db.rollback()
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
                followers = get_all_followers_for_account(account_handle)

                if followers:
                    # Save followers to database
                    save_followers_to_db(campaign_id, account_handle, followers)
                    print(f"Saved {len(followers)} followers for {account_handle}")
                else:
                    print(f"No followers found for {account_handle}")

            except Exception as e:
                print(f"Error processing account {account}: {e}")
                continue  # Continue with next account

        print(f"\nCompleted processing all accounts for campaign: {campaign_name}")

        # set the is_setup_job_running to False on the campaign
        db = next(get_db())
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                campaign.is_setup_job_running = False
                db.commit()
                print(f"Campaign '{campaign_name}' setup job marked as complete")

                # Trigger the campaign execution worker
                print(f"Triggering campaign execution for campaign ID: {campaign_id}")
                queue = get_queue("campaign_execute")
                job = queue.enqueue(execute_campaign_task, campaign_id)
                print(f"Campaign execution job enqueued with ID: {job.id}")

            else:
                print(f"Campaign with ID {campaign_id} not found for update")
        except Exception as e:
            print(f"Error updating campaign status: {e}")
            db.rollback()
        finally:
            db.close()
    else:
        print("No accounts to process in followers_to_get")

    return f"Campaign '{campaign_name}' processed successfully"


def execute_campaign_task(campaign_id: int) -> str:
    """
    Execute the actual campaign by processing all collected followers.

    This function is triggered after the setup job completes and processes
    all followers that were collected for the campaign.

    Args:
        campaign_id: The ID of the campaign to execute

    Returns:
        str: Task completion message
    """
    try:
        print(
            f"execute_campaign_task --- Starting campaign execution for campaign ID: {campaign_id}"
        )

        if not campaign_id:
            print("Error: No campaign ID provided")
            return "Error: No campaign ID provided"

        # Get campaign from database
        db = next(get_db())
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()

            if not campaign:
                print(f"Error: Campaign with ID {campaign_id} not found")
                return f"Error: Campaign with ID {campaign_id} not found"

            # Extract campaign data
            campaign_name = campaign.name
            campaign_user_did = campaign.user_did
            is_setup_complete = not campaign.is_setup_job_running

            print(f"Campaign: {campaign_name}")
            print(f"User DID: {campaign_user_did}")
            print(f"Setup complete: {is_setup_complete}")

            if not is_setup_complete:
                print(
                    "Warning: Setup job is still running, but proceeding with execution"
                )

            # Set campaign as running
            campaign.is_campaign_running = True
            db.commit()
            print(f"Marked campaign '{campaign_name}' as running")

        except Exception as e:
            print(f"Error fetching campaign: {e}")
            return f"Error fetching campaign: {e}"
        finally:
            db.close()

        # Get all followers for this campaign
        db = next(get_db())
        try:
            followers = (
                db.query(FollowersToGet)
                .filter(FollowersToGet.campaign_id == campaign_id)
                .limit(10)
                .all()
            )

            follower_count = len(followers)
            print(
                f"Found {follower_count} followers to process for campaign '{campaign_name}'"
            )

            if follower_count == 0:
                print("No followers found to process")
                return f"No followers found for campaign '{campaign_name}'"

            # Get user's OAuth session for API authentication
            oauth_session = (
                db.query(OAuthSession)
                .filter(OAuthSession.did == campaign_user_did)
                .first()
            )
            if not oauth_session:
                print(
                    f"Error: No OAuth session found for user DID: {campaign_user_did}"
                )
                return f"Error: No OAuth session found for user"

            # Extract OAuth data for API calls
            access_token = oauth_session.access_token
            dpop_private_jwk_json = oauth_session.dpop_private_jwk
            dpop_pds_nonce = oauth_session.dpop_pds_nonce or ""

            # Process each follower
            processed_count = 0
            for follower in followers:
                try:
                    print(f"Processing follower: {follower.account_handle}")

                    # Skip if we already have a follow timestamp (already following)
                    if follower.me_following:
                        print(
                            f"Already following {follower.account_handle} since {follower.me_following}"
                        )
                        processed_count += 1
                        continue

                    # Check if we're already following this user via Bluesky API
                    try:
                        # Get the user's profile to get their DID
                        profile_url = f"https://bsky.social/xrpc/app.bsky.actor.getProfile?actor={follower.account_handle}"
                        profile_resp = pds_authed_req(
                            "GET",
                            profile_url,
                            access_token=access_token,
                            dpop_private_jwk_json=dpop_private_jwk_json,
                            user_did=campaign_user_did,
                            db=db,
                            dpop_pds_nonce=dpop_pds_nonce
                        )

                        if profile_resp.status_code not in [200, 201]:
                            print(
                                f"Failed to get profile for {follower.account_handle}: {profile_resp.status_code}"
                            )
                            continue

                        target_did = profile_resp.json().get("did")
                        if not target_did:
                            print(f"No DID found for {follower.account_handle}")
                            continue

                        # Check if we're already following them
                        following_url = f"https://bsky.social/xrpc/app.bsky.graph.getFollows?actor={campaign_user_did}&limit=100"
                        follows_resp = pds_authed_req(
                            "GET",
                            following_url,
                            access_token=access_token,
                            dpop_private_jwk_json=dpop_private_jwk_json,
                            user_did=campaign_user_did,
                            db=db,
                            dpop_pds_nonce=dpop_pds_nonce
                        )

                        already_following = False
                        if follows_resp.status_code in [200, 201]:
                            follows_data = follows_resp.json()
                            for follow in follows_data.get("follows", []):
                                if follow.get("did") == target_did:
                                    already_following = True
                                    # Update database with current timestamp since we're already following
                                    follower.me_following = datetime.utcnow()
                                    db.commit()
                                    print(
                                        f"Already following {follower.account_handle} - updated database"
                                    )
                                    break

                        if not already_following:
                            # Follow the user
                            follow_payload = {
                                "$type": "app.bsky.graph.follow",
                                "subject": target_did,
                                "createdAt": datetime.utcnow().isoformat() + "Z",
                            }

                            create_record_url = (
                                "https://bsky.social/xrpc/com.atproto.repo.createRecord"
                            )
                            create_record_payload = {
                                "repo": campaign_user_did,
                                "collection": "app.bsky.graph.follow",
                                "record": follow_payload,
                            }

                            follow_resp = pds_authed_req(
                                "POST",
                                create_record_url,
                                access_token=access_token,
                                dpop_private_jwk_json=dpop_private_jwk_json,
                                user_did=campaign_user_did,
                                db=db,
                                dpop_pds_nonce=dpop_pds_nonce,
                                body=create_record_payload,
                            )

                            if follow_resp.status_code in [200, 201]:
                                # Successfully followed, update database with timestamp
                                follower.me_following = datetime.utcnow()
                                db.commit()
                                print(
                                    f"Successfully followed {follower.account_handle}"
                                )
                            else:
                                print(
                                    f"Failed to follow {follower.account_handle}: {follow_resp.status_code}"
                                )
                                if follow_resp.status_code == 429:
                                    print("Rate limited - waiting before continuing...")
                                    time.sleep(5)  # Wait 5 seconds for rate limiting

                    except Exception as e:
                        print(
                            f"Error processing follow for {follower.account_handle}: {e}"
                        )

                    processed_count += 1

                    # Rate limiting - small delay between requests
                    time.sleep(1)

                    if processed_count % 100 == 0:
                        print(f"Processed {processed_count}/{follower_count} followers")

                except Exception as e:
                    print(f"Error processing follower {follower.account_handle}: {e}")
                    continue

            print(
                f"Campaign execution completed: {processed_count}/{follower_count} followers processed"
            )

        except Exception as e:
            print(f"Error processing followers: {e}")
            return f"Error processing followers: {e}"
        finally:
            db.close()

        # Mark campaign as completed
        db = next(get_db())
        try:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                # campaign.is_campaign_running = False
                db.commit()
                print(f"Campaign '{campaign_name}' execution marked as complete")
            else:
                print(f"Campaign with ID {campaign_id} not found for final update")
        except Exception as e:
            print(f"Error updating final campaign status: {e}")
        finally:
            db.close()

        return f"Campaign '{campaign_name}' executed successfully. Processed {processed_count} followers."

    except Exception as e:
        print(f"Unexpected error in execute_campaign_task: {e}")

        # Try to mark campaign as not running in case of error
        try:
            db = next(get_db())
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                # campaign.is_campaign_running = False
                db.commit()
        except:
            pass
        finally:
            try:
                db.close()
            except:
                pass

        return f"Error executing campaign: {e}"
