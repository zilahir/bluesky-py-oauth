from datetime import datetime
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.config import Config
from requests import HTTPError, request as req

from starlette.responses import HTMLResponse
from atproto_identity import (
    is_valid_did,
    is_valid_handle,
    pds_endpoint,
    resolve_identity,
)
from atproto_oauth import (
    fetch_authserver_meta,
    initial_token_request,
    refresh_token_request,
    resolve_pds_authserver,
    send_par_auth_request,
)
from atproto_security import is_safe_url
from authlib.jose import JsonWebKey

from oauth_metadata import OauthMetadata
from routes.utils.get_user import get_logged_in_user
from routes.utils.postgres_connection import (
    get_db,
    OAuthAuthRequest,
    OAuthSession,
    User,
)
from settings import get_settings


router = APIRouter(prefix="/auth", include_in_schema=False)


@router.post("/oauth/login")
def oauth_login_submit(
    request: Request,
    username: str = Form(...),
    settings=Depends(get_settings),
    db: Session = Depends(get_db),
):
    # Login can start with a handle, DID, or auth server URL. We are calling whatever the user supplied the "username".
    if is_valid_handle(username) or is_valid_did(username):
        # If starting with an account identifier, resolve the identity (bi-directionally), fetch the PDS URL, and resolve to the Authorization Server URL
        login_hint = username
        did, handle, did_doc = resolve_identity(username)
        pds_url = pds_endpoint(did_doc)
        print(f"account PDS: {pds_url}")
        authserver_url = resolve_pds_authserver(pds_url)
    elif username.startswith("https://") and is_safe_url(username):
        # When starting with an auth server, we don't know about the account yet.
        did, handle, pds_url = None, None, None
        login_hint = None
        # Check if this is a Resource Server (PDS) URL; otherwise assume it is authorization server
        initial_url = username
        try:
            authserver_url = resolve_pds_authserver(initial_url)
        except Exception:
            authserver_url = initial_url
    else:
        request.session["flash_message"] = "Not a valid handle, DID, or auth server URL"

        # return error
        return JSONResponse(
            {
                "error": "Invalid input. Please provide a valid handle, DID, or auth server URL."
            },
            status_code=400,
        )

    # Fetch Auth Server metadata. For a self-hosted PDS, this will be the same server (the PDS). For large-scale PDS hosts like Bluesky, this may be a separate "entryway" server filling the Auth Server role.
    # IMPORTANT: Authorization Server URL is untrusted input, SSRF mitigations are needed
    print(f"account Authorization Server: {authserver_url}")
    assert is_safe_url(authserver_url)
    try:
        authserver_meta = fetch_authserver_meta(authserver_url)
    except Exception as err:
        print(f"failed to fetch auth server metadata: {err}")
        # raise err
        request.session["flash_message"] = (
            "Failed to fetch Auth Server (Entryway) OAuth metadata"
        )

        return JSONResponse(
            {"error": "Failed to fetch Auth Server (Entryway) OAuth metadata"},
            status_code=400,
        )

    # Generate DPoP private signing key for this account session. In theory this could be defered until the token request at the end of the athentication flow, but doing it now allows early binding during the PAR request.
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True)

    oauth_config = OauthMetadata("development")
    oauth_meta = oauth_config.get_config()

    # OAuth scopes requested by this app
    # scope = "atproto transition:generic"
    scope = oauth_meta["scope"]

    # Dynamically compute our "client_id" based on the request HTTP Host
    app_url = str(request.url).replace("http://", "https://").rstrip("/oauth/login")
    # redirect_uri = f"{app_url}oauth/callback"
    # client_id = f"{app_url}oauth/client-metadata.json"

    redirect_uri = oauth_meta["redirect_uris"][0]

    client_id = oauth_meta["client_id"]

    # Submit OAuth Pushed Authentication Request (PAR). We could have constructed a more complex authentication request URL below instead, but there are some advantages with PAR, including failing fast, early DPoP binding, and no URL length limitations.
    pkce_verifier, state, dpop_authserver_nonce, resp = send_par_auth_request(
        authserver_url,
        authserver_meta,
        login_hint,
        client_id,
        redirect_uri,
        scope,
        settings.client_secret_jwk_obj,
        dpop_private_jwk,
    )
    if resp.status_code == 400:
        print(f"PAR HTTP 400: {resp.json()}")
    resp.raise_for_status()
    # This field is confusingly named: it is basically a token to refering back to the successful PAR request.
    par_request_uri = resp.json()["request_uri"]

    print(f"saving oauth_auth_request to DB  state={state}")
    auth_request = OAuthAuthRequest(
        state=state,
        authserver_iss=authserver_meta["issuer"],
        did=did,  # might be None
        handle=handle,  # might be None
        pds_url=pds_url,  # might be None
        pkce_verifier=pkce_verifier,
        scope=scope,
        dpop_authserver_nonce=dpop_authserver_nonce,
        dpop_private_jwk=dpop_private_jwk.as_json(is_private=True),
    )
    db.add(auth_request)
    db.commit()

    # Forward the user to the Authorization Server to complete the browser auth flow.
    # IMPORTANT: Authorization endpoint URL is untrusted input, security mitigations are needed before redirecting user
    auth_url = authserver_meta["authorization_endpoint"]
    assert is_safe_url(auth_url)
    qparam = urlencode({"client_id": client_id, "request_uri": par_request_uri})

    return JSONResponse({"redirect_url": f"{auth_url}?{qparam}"})


@router.get("/oauth/callback")
def oauth_callback(
    request: Request,
    state: str,
    iss: str,
    code: str,
    settings=Depends(get_settings),
    db: Session = Depends(get_db),
):
    authserver_iss = iss
    authorization_code = code

    # Lookup auth request by the "state" token (which we randomly generated earlier)
    auth_request = (
        db.query(OAuthAuthRequest).filter(OAuthAuthRequest.state == state).first()
    )
    if auth_request is None:
        return JSONResponse(
            {"error": "Invalid state parameter. Please try again."},
            status_code=400,
        )

    # Delete row to prevent response replay
    db.delete(auth_request)
    db.commit()

    # Verify query param "iss" against earlier oauth request "iss"
    if str(auth_request.authserver_iss) != authserver_iss:
        raise ValueError("Authorization server issuer mismatch")
    # This is redundant with the above SQL query, but also double-checking that the "state" param matches the original request
    if str(auth_request.state) != state:
        raise ValueError("State parameter mismatch")

    # Complete the auth flow by requesting auth tokens from the authorization server.
    app_url = (
        str(request.url).replace("http://", "https://").split("/oauth/callback")[0]
    )
    # Convert SQLAlchemy model to dictionary for initial_token_request function
    auth_request_dict = {
        "authserver_iss": auth_request.authserver_iss,
        "pkce_verifier": auth_request.pkce_verifier,
        "dpop_private_jwk": auth_request.dpop_private_jwk,
        "dpop_authserver_nonce": auth_request.dpop_authserver_nonce,
    }
    tokens, dpop_authserver_nonce = initial_token_request(
        auth_request_dict,
        authorization_code,
        app_url,
        settings.client_secret_jwk_obj,
    )

    # Now we verify the account authentication against the original request
    if auth_request.did:
        # If we started with an account identifier, this is simple
        did, handle, pds_url = (
            auth_request.did,
            auth_request.handle,
            auth_request.pds_url,
        )
        assert tokens["sub"] == did
    else:
        # If we started with an auth server URL, now we need to resolve the identity
        did = tokens["sub"]
        assert is_valid_did(did)
        did, handle, did_doc = resolve_identity(did)
        pds_url = pds_endpoint(did_doc)
        authserver_url = resolve_pds_authserver(pds_url)

        # Verify that Authorization Server matches
        assert authserver_url == authserver_iss

    # Verify that returned scope matches request (waiting for PDS update)
    assert auth_request.scope == tokens["scope"]

    # Save session (including auth tokens) in database
    print(f"saving oauth_session to DB  {did}")
    # Check if session already exists
    existing_session = db.query(OAuthSession).filter(OAuthSession.did == did).first()
    if existing_session:
        # Update existing session
        existing_session.handle = handle
        existing_session.pds_url = pds_url
        existing_session.authserver_iss = authserver_iss
        existing_session.access_token = tokens["access_token"]
        existing_session.refresh_token = tokens["refresh_token"]
        existing_session.dpop_authserver_nonce = dpop_authserver_nonce
        existing_session.dpop_pds_nonce = None  # Will be set when making PDS requests
        existing_session.dpop_private_jwk = auth_request.dpop_private_jwk
    else:
        # Create new session
        oauth_session = OAuthSession(
            did=did,
            handle=handle,
            pds_url=pds_url,
            authserver_iss=authserver_iss,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            dpop_authserver_nonce=dpop_authserver_nonce,
            dpop_pds_nonce=None,  # Will be set when making PDS requests
            dpop_private_jwk=auth_request.dpop_private_jwk,
        )
        db.add(oauth_session)
    db.commit()

    # Check if user exists in database
    existing_user = db.query(User).filter(User.did == did).first()
    if existing_user is None:
        print("no user yet inserint to the database")
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

        user = {
            "did": did,
            "handle": account.get("handle", ""),
            "avatar": account.get("avatar", ""),
            "display_name": account.get("displayName", ""),
            "description": account.get("description", ""),
        }

        # Insert new user into the database
        new_user = User(
            did=user["did"],
            handle=user["handle"],
            avatar=user["avatar"],
            display_name=user["display_name"],
            description=user["description"],
        )
        db.add(new_user)
        db.commit()

    # Set a (secure) session cookie in the user's browser, for authentication between the browser and this app
    request.session["user_did"] = did
    # Note that the handle might change over time, and should be re-resolved periodically in a real app
    request.session["user_handle"] = handle

    # return RedirectResponse(url="http://localhost:5174/oauth/callback", status_code=303)

    html = """
    <html>
      <body>
        <script>
          window.location.href = "http://127.0.0.1:5174/oauth/callback";
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)


@router.get("/oauth/logout")
def oauth_logout(
    request: Request, user=Depends(get_logged_in_user), db: Session = Depends(get_db)
):
    # Delete the session from database
    session_to_delete = (
        db.query(OAuthSession).filter(OAuthSession.did == user.did).first()
    )
    if session_to_delete:
        db.delete(session_to_delete)
        db.commit()
    request.session.clear()
    return JSONResponse(
        {"message": "LOGOUT_SUCCESS"},
        status_code=200,
    )


@router.post("/oauth/refresh")
def oauth_refresh(
    request: Request,
    user=Depends(get_logged_in_user),
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
):
    """
    Refresh the OAuth tokens for the current user.

    This endpoint refreshes the access token using the refresh token,
    and updates the tokens in the PostgreSQL database.
    """
    try:
        # Get the app URL from the request
        app_url = (
            str(request.url).replace("http://", "https://").split("/oauth/refresh")[0]
        )

        # Create user dict in the format expected by refresh_token_request
        user_dict = {
            "authserver_iss": user.authserver_iss,
            "refresh_token": user.refresh_token,
            "dpop_private_jwk": user.dpop_private_jwk,
            "dpop_authserver_nonce": user.dpop_authserver_nonce,
        }

        # Request new tokens
        tokens, dpop_authserver_nonce = refresh_token_request(
            user_dict, app_url, settings.client_secret_jwk_obj
        )

        # Update the existing OAuth session with new tokens
        user.access_token = tokens["access_token"]
        user.refresh_token = tokens["refresh_token"]
        user.dpop_authserver_nonce = dpop_authserver_nonce
        user.updated_at = datetime.utcnow()

        db.commit()

        print(f"Token refreshed successfully for user: {user.did}")

        return JSONResponse(
            {
                "message": "Token refreshed successfully",
                "timestamp": user.updated_at.isoformat() if user.updated_at else None,
            }
        )

    except Exception as e:
        print(f"Error refreshing token for user {user.did}: {e}")
        db.rollback()
        return JSONResponse(
            {"error": "Failed to refresh token", "detail": str(e)},
            status_code=500,
        )
    finally:
        db.close()
