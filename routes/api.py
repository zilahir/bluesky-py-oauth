from fastapi import APIRouter, Request
from fastapi import Depends

from atproto_oauth import pds_authed_req
from routes.utils.get_db import get_db
from routes.utils.get_user import get_logged_in_user
from requests import request as req


router = APIRouter(prefix="/api", include_in_schema=False)


@router.get("/get-bluesky-profile/{handle}")
def get_bluesky_account(
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
