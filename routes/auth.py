from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
import sqlite3
from starlette.config import Config
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
    resolve_pds_authserver,
    send_par_auth_request,
)
from atproto_security import is_safe_url
from authlib.jose import JsonWebKey

from oauth_metadata import OauthMetadata
from routes.utils.get_user import get_logged_in_user
from settings import get_settings


def query_db(query, args=(), one=False, db=None):
    if db is None:
        db_path = get_settings().dp_path
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        should_close = True
    else:
        conn = db
        should_close = False

    try:
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        conn.commit()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    finally:
        if should_close:
            conn.close()


router = APIRouter(prefix="/auth", include_in_schema=False)


@router.post("/oauth/login")
def oauth_login_submit(
    request: Request,
    username: str = Form(...),
    settings=Depends(get_settings),
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
    query_db(
        "INSERT INTO oauth_auth_request (state, authserver_iss, did, handle, pds_url, pkce_verifier, scope, dpop_authserver_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?);",
        [
            state,
            authserver_meta["issuer"],
            did,  # might be None
            handle,  # might be None
            pds_url,  # might be None
            pkce_verifier,
            scope,
            dpop_authserver_nonce,
            dpop_private_jwk.as_json(is_private=True),
        ],
    )

    # Forward the user to the Authorization Server to complete the browser auth flow.
    # IMPORTANT: Authorization endpoint URL is untrusted input, security mitigations are needed before redirecting user
    auth_url = authserver_meta["authorization_endpoint"]
    assert is_safe_url(auth_url)
    qparam = urlencode({"client_id": client_id, "request_uri": par_request_uri})

    return JSONResponse({"redirect_url": f"{auth_url}?{qparam}"})


@router.get("/oauth/callback")
def oauth_callback(
    request: Request, state: str, iss: str, code: str, settings=Depends(get_settings)
):
    authserver_iss = iss
    authorization_code = code

    # Lookup auth request by the "state" token (which we randomly generated earlier)
    row = query_db(
        "SELECT * FROM oauth_auth_request WHERE state = ?;",
        [state],
        one=True,
    )
    if row is None:
        return JSONResponse(
            {"error": "Invalid state parameter. Please try again."},
            status_code=400,
        )

    # Delete row to prevent response replay
    query_db("DELETE FROM oauth_auth_request WHERE state = ?;", [state])

    # Verify query param "iss" against earlier oauth request "iss"
    assert row["authserver_iss"] == authserver_iss
    # This is redundant with the above SQL query, but also double-checking that the "state" param matches the original request
    assert row["state"] == state

    # Complete the auth flow by requesting auth tokens from the authorization server.
    app_url = (
        str(request.url).replace("http://", "https://").split("/oauth/callback")[0]
    )
    tokens, dpop_authserver_nonce = initial_token_request(
        row,
        authorization_code,
        app_url,
        settings.client_secret_jwk_obj,
    )

    # Now we verify the account authentication against the original request
    if row["did"]:
        # If we started with an account identifier, this is simple
        did, handle, pds_url = row["did"], row["handle"], row["pds_url"]
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
    assert row["scope"] == tokens["scope"]

    # Save session (including auth tokens) in database
    print(f"saving oauth_session to DB  {did}")
    query_db(
        "INSERT OR REPLACE INTO oauth_session (did, handle, pds_url, authserver_iss, access_token, refresh_token, dpop_authserver_nonce, dpop_private_jwk) VALUES(?, ?, ?, ?, ?, ?, ?, ?);",
        [
            did,
            handle,
            pds_url,
            authserver_iss,
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_authserver_nonce,
            row["dpop_private_jwk"],
        ],
    )

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
def oauth_logout(request: Request, user=Depends(get_logged_in_user)):
    query_db("DELETE FROM oauth_session WHERE did = ?;", [user["did"]])
    request.session.clear()
    return JSONResponse(
        {"message": "LOGOUT_SUCCESS"},
        status_code=200,
    )
