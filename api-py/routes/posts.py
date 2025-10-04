from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from requests import HTTPError
from sqlalchemy.orm import Session

from atproto_oauth import pds_authed_req
from routes.utils.get_user import get_logged_in_user
from routes.utils.postgres_connection import get_db

router = APIRouter(prefix="/posts", include_in_schema=False)


@router.post("/create", status_code=201)
async def create_post(
    request: Request, user=Depends(get_logged_in_user), db: Session = Depends(get_db)
):
    # Get OAuth session from logged-in user
    oauth_session = user

    # Get PDS URL from the user's OAuth session
    pds_url = oauth_session.pds_url
    req_url = f"{pds_url}/xrpc/com.atproto.repo.createRecord"

    body = await request.json()
    if not body or "post" not in body:
        return HTTPError("Invalid request body: 'post_text' is required")

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Get user DID from OAuth session
    user_did = oauth_session.did

    body = {
        "repo": user_did,
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": body["post"],
            "createdAt": now,
        },
    }

    # Get credentials from OAuth session
    access_token = oauth_session.access_token
    dpop_pds_nonce = oauth_session.dpop_pds_nonce or ""
    dpop_private_jwk_json = oauth_session.dpop_private_jwk

    resp = pds_authed_req(
        "POST",
        req_url,
        access_token=access_token,
        dpop_private_jwk_json=dpop_private_jwk_json,
        user_did=user_did,
        db=db,
        dpop_pds_nonce=dpop_pds_nonce,
        body=body,
    )
    if resp.status_code not in [200, 201]:
        print(f"PDS HTTP Error: {resp.json()}")
    resp.raise_for_status()
