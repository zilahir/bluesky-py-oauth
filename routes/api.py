from fastapi import APIRouter, Request
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from atproto_oauth import pds_authed_req
from routes.utils.get_db import get_db
from routes.utils.get_user import get_logged_in_user
from requests import HTTPError, request as req
from routes.utils.postgres_connection import Campaign, get_db as get_pg_db
from queue_config import get_queue
from tasks import process_campaign_task


router = APIRouter(prefix="/api", include_in_schema=False)


@router.get("/campaigns")
async def get_campaigns(
    user=Depends(get_logged_in_user),
    db: Session = Depends(get_pg_db),
):
    """
    Get all campaigns for the logged-in user.
    """
    try:
        if not user:
            raise HTTPError("Authentication required")

        campaigns = db.query(Campaign).filter(Campaign.user_did == user.did).all()

        return {
            "data": [campaign.__dict__ for campaign in campaigns],
        }
    finally:
        db.close()


@router.post("/new-campaign")
async def new_campaign(
    request: Request,
    user=Depends(get_logged_in_user),
    db: Session = Depends(get_pg_db),
):
    """
    Create a new campaign.
    """
    try:
        body = await request.json()
        if not body:
            # return proper error response if body is empty
            raise HTTPError("Request body is empty. Please provide the necessary data.")

        followers_to_get = body.get("accountsToFollow", [])

        if not followers_to_get:
            raise HTTPError("No accounts to follow provided in the request body.")

        insert_campaign = (
            insert(Campaign)
            .values(
                name=body.get("name"),
                followers_to_get=followers_to_get,
                user_did=user.did,
            )
            .on_conflict_do_nothing()
        )

        db.execute(insert_campaign)
        db.commit()

        # Enqueue the campaign processing task
        queue = get_queue("campaign_processing")
        job = queue.enqueue(process_campaign_task, body)

        return {
            "message": "Campaign created successfully",
            "data": body,
            "job_id": job.id,
        }
    finally:
        db.close()


def get_all_followers_of_account(
    request: Request, handle: str, user=Depends(get_logged_in_user), db=Depends(get_db)
):
    try:
        body = {}
        # pds_url = user["pds_url"]

        req_url = (
            f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={handle}"
        )
        # resp = pds_authed_req("GET", req_url, user=user, db=db)
        profile_resp = req(
            "GET",
            req_url,
        )
        if profile_resp.status_code not in [200, 201]:
            print(f"PDS HTTP Error: {profile_resp.json()}")
        profile_resp.raise_for_status()

        did = profile_resp.json()["did"]

        followers = []
        cursor = None

        while True:
            req_url = f"https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?actor={did}&limit=100"
            if cursor:
                req_url += f"&cursor={cursor}"

            resp = req(
                "GET",
                req_url,
            )
            if resp.status_code not in [200, 201]:
                print(f"PDS HTTP Error: {resp.json()}")
            resp.raise_for_status()

            followers.extend(resp.json().get("followers", []))
            cursor = resp.json().get("cursor", None)

            if not cursor:
                break

            if len(resp.json().get("followers", [])) == 0:
                break

        return {
            "account": resp.json(),
            "followers": followers,
            "followers_count": len(followers),
        }
    finally:
        db.close()


@router.get("/get-bluesky-profile/{handle}")
def get_bluesky_profile(
    request: Request, handle: str, user=Depends(get_logged_in_user), db=Depends(get_db)
):
    try:
        req_url = (
            f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={handle}"
        )
        profile_resp = req(
            "GET",
            req_url,
        )
        if profile_resp.status_code not in [200, 201]:
            print(f"PDS HTTP Error: {profile_resp.json()}")
        profile_resp.raise_for_status()

        did = profile_resp.json()["did"]

        account = profile_resp.json()

        followers_count = account.get("followersCount", 0)

        return {
            "account": account,
            "followers_count": followers_count,
        }
    finally:
        db.close()
