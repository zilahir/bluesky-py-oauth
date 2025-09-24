import time
from typing import Dict, Any, List

from requests import request as req
from sqlalchemy.orm import Session
import os

os.environ["no_proxy"] = "*"

from routes.utils.postgres_connection import get_db, Campaign, FollowersToGet


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

    db = next(get_db())
    try:
        for follower in followers:
            follower_handle = follower.get("handle", "")

            # Check if this follower already exists for this campaign
            existing = (
                db.query(FollowersToGet)
                .filter(
                    FollowersToGet.campaign_id == campaign_id,
                    FollowersToGet.account_handle == follower_handle,
                )
                .first()
            )

            if not existing:
                new_follower = FollowersToGet(
                    campaign_id=campaign_id,
                    account_handle=follower_handle,
                    me_following=False,  # Default values
                    is_following_me=False,
                )
                db.add(new_follower)

        db.commit()
        print(f"Successfully saved followers for {account_handle}")

    except Exception as e:
        print(f"Error saving followers for {account_handle}: {e}")
        db.rollback()
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
    else:
        print("No accounts to process in followers_to_get")

    return f"Campaign '{campaign_name}' processed successfully"
