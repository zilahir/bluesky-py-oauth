import json
import pathlib
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlencode
from fastapi import FastAPI, Request, Depends, HTTPException, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from starlette.exceptions import HTTPException as StarletteHTTPException
from authlib.jose import JsonWebKey

from atproto_identity import (
    is_valid_did,
    is_valid_handle,
    resolve_identity,
    pds_endpoint,
)
from atproto_oauth import (
    refresh_token_request,
    pds_authed_req,
    resolve_pds_authserver,
    initial_token_request,
    send_par_auth_request,
    fetch_authserver_meta,
)
from atproto_security import is_safe_url
from oauth_metadata import OauthMetadata
from routes import api, auth, me, test

app = FastAPI()

origins = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

config = Config(".env")

app.add_middleware(
    SessionMiddleware,
    secret_key=config("SECRET_KEY", default="dev-secret-key"),
    https_only=False,
    same_site="lax",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd = pathlib.Path(__file__).parent
app.mount("/static", StaticFiles(directory=pwd / "static"), name="static")


templates = Jinja2Templates(directory="templates")


# This is a "confidential" OAuth client, meaning it has access to a persistent secret signing key. parse that key as a global.
CLIENT_SECRET_JWK = JsonWebKey.import_key(json.loads(config("CLIENT_SECRET_JWK")))
CLIENT_PUB_JWK = json.loads(CLIENT_SECRET_JWK.as_json(is_private=False))

# Defensively check that the public JWK is really public and didn't somehow end up with secret cryptographic key info
assert "d" not in CLIENT_PUB_JWK


# Helpers for managing database connection.
# Note that you could use a sqlite ":memory:" database instead. In that case you would want to have a global sqlite connection, instead of re-connecting per connection.
def get_db():
    db_path = config("DATABASE_URL", default="demo.sqlite")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def query_db(query, args=(), one=False, db=None):
    if db is None:
        db_path = config("DATABASE_URL", default="demo.sqlite")
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


def init_db():
    print("initializing database...")
    db_path = config("DATABASE_URL", default="demo.sqlite")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        with open("schema.sql", "r") as f:
            db.cursor().executescript(f.read())
        db.commit()
    finally:
        db.close()


init_db()


# Load back-end account auth metadata when there is a valid front-end session cookie
def get_current_user(request: Request):
    user_did = request.session.get("user_did")

    if user_did is None:
        return None
    else:
        return query_db(
            "SELECT * FROM oauth_session WHERE did = ?", (user_did,), one=True
        )


def get_logged_in_user(request: Request):
    user = get_current_user(request)
    print(f"get_logged_in_user: {user}")
    if user:
        return user
    else:
        print("No user session found, redirecting to login")
        raise HTTPException(status_code=401, detail="Authentication required")


# Actual web routes start here!
@app.get("/", response_class=HTMLResponse)
def homepage(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/health")
def health_check():
    return JSONResponse(
        {
            "env": config("ENV", default="unknown"),
        }
    )


# Every atproto OAuth client must have a public client metadata JSON document. It does not need to be at this specific path. The full URL to this file is the "client_id" of the app.
# This implementation dynamically uses the HTTP request Host name to infer the "client_id".
@app.get("/oauth/client-metadata.json")
def oauth_client_metadata():
    env = config("ENV", default="unknown")

    oauth_metadata = OauthMetadata(env)
    ouath_config = oauth_metadata.get_config()

    return JSONResponse(ouath_config)

    # return jsonify(
    #     {
    #         # simply using the full request URL for the client_id
    #         "client_id": client_id,
    #         "dpop_bound_access_tokens": True,
    #         "application_type": "web",
    #         "redirect_uris": [f"{app_url}oauth/callback"],
    #         "grant_types": ["authorization_code", "refresh_token"],
    #         "response_types": ["code"],
    #         "scope": "atproto transition:generic",
    #         "token_endpoint_auth_method": "private_key_jwt",
    #         "token_endpoint_auth_signing_alg": "ES256",
    #         # NOTE: in theory we can return the public key (in JWK format) inline
    #         # "jwks": { #    "keys": [CLIENT_PUB_JWK], #},
    #         "jwks_uri": f"{app_url}oauth/jwks.json",
    #         # the following are optional fields, which might not be displayed by auth server
    #         "client_name": "atproto OAuth Flask Backend Demo",
    #         "client_uri": app_url,
    #     }
    # )


# In this example of a "confidential" OAuth client, we have only a single app key being used. In a production-grade client, it best practice to periodically rotate keys. Including both a "new key" and "old key" at the same time can make this process smoother.
@app.get("/oauth/jwks.json")
def oauth_jwks():
    return JSONResponse(
        {
            "keys": [CLIENT_PUB_JWK],
        }
    )


# Displays the login form (GET), or starts the OAuth authorization flow (POST).
@app.get("/oauth/login", response_class=HTMLResponse, name="oauth_login")
def oauth_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/oauth/login")
def oauth_login_submit(request: Request, username: str = Form(...)):
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
        return templates.TemplateResponse(
            "login.html", {"request": request}, status_code=400
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
        return templates.TemplateResponse(
            "login.html", {"request": request}, status_code=400
        )

    # Generate DPoP private signing key for this account session. In theory this could be defered until the token request at the end of the athentication flow, but doing it now allows early binding during the PAR request.
    dpop_private_jwk = JsonWebKey.generate_key("EC", "P-256", is_private=True)

    oauth_config = OauthMetadata(config("ENV", default="unknown"))
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
        CLIENT_SECRET_JWK,
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
    return RedirectResponse(url=f"{auth_url}?{qparam}", status_code=303)


# Endpoint for receiving "callback" responses from the Authorization Server, to complete the auth flow.
@app.get("/oauth/callback")
def oauth_callback(request: Request, state: str, iss: str, code: str):
    authserver_iss = iss
    authorization_code = code

    # Lookup auth request by the "state" token (which we randomly generated earlier)
    row = query_db(
        "SELECT * FROM oauth_auth_request WHERE state = ?;",
        [state],
        one=True,
    )
    if row is None:
        raise HTTPException(status_code=400, detail="OAuth request not found")

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
        CLIENT_SECRET_JWK,
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

    return RedirectResponse(url="/bsky/post")


# Example endpoint demonstrating manual refreshing of auth token.
# This isn't something you would do in a real application, it is just to trigger this codepath.
@app.get("/oauth/refresh")
def oauth_refresh(request: Request, user=Depends(get_logged_in_user)):
    app_url = str(request.url).replace("http://", "https://").split("/oauth/refresh")[0]

    tokens, dpop_authserver_nonce = refresh_token_request(
        user, app_url, CLIENT_SECRET_JWK
    )

    # persist updated tokens (and DPoP nonce) to database
    query_db(
        "UPDATE oauth_session SET access_token = ?, refresh_token = ?, dpop_authserver_nonce = ? WHERE did = ?;",
        [
            tokens["access_token"],
            tokens["refresh_token"],
            dpop_authserver_nonce,
            user["did"],
        ],
    )

    request.session["flash_message"] = "Token refreshed!"
    return RedirectResponse(url="/")


@app.get("/oauth/logout")
def oauth_logout(request: Request, user=Depends(get_logged_in_user)):
    # TODO: check for user.did
    query_db("DELETE FROM oauth_session WHERE did = ?;", [user["did"]])
    request.session.clear()
    return RedirectResponse(url="/")


# Example form endpoint demonstrating making an authenticated request to the logged-in user's PDS to create a repository record.
@app.get("/bsky/post", response_class=HTMLResponse, name="bsky_post")
def bsky_post_form(request: Request, user=Depends(get_logged_in_user)):
    return templates.TemplateResponse(
        "bsky_post.html",
        {
            "request": request,
            "user": user,
        },
    )


@app.post("/bsky/post")
def bsky_post_submit(
    request: Request, post_text: str = Form(...), user=Depends(get_logged_in_user)
):
    pds_url = user["pds_url"]
    req_url = f"{pds_url}/xrpc/com.atproto.repo.createRecord"

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "repo": user["did"],
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": post_text,
            "createdAt": now,
        },
    }

    # We need to get a database connection for pds_authed_req
    db_path = config("DATABASE_URL", default="demo.sqlite")
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        resp = pds_authed_req("POST", req_url, body=body, user=user, db=db)
        if resp.status_code not in [200, 201]:
            print(f"PDS HTTP Error: {resp.json()}")
        resp.raise_for_status()

        request.session["flash_message"] = "Post record created in PDS!"
        return templates.TemplateResponse("bsky_post.html", {"request": request})
    finally:
        db.close()


# @app.exception_handler(HTTPException)
# async def fastapi_http_exception_handler(request: Request, exc: HTTPException):
#     if exc.status_code == 401:
#         return RedirectResponse(url=request.url_for("oauth_login"), status_code=303)
#     else:
#         return templates.TemplateResponse(
#             "error.html",
#             {"request": request, "status_code": exc.status_code, "err": exc},
#             status_code=exc.status_code,
#         )
#
#
# @app.exception_handler(StarletteHTTPException)
# async def http_exception_handler(request: Request, exc: StarletteHTTPException):
#     if exc.status_code == 401:
#         return RedirectResponse(url=request.url_for("oauth_login"), status_code=303)
#     elif exc.status_code == 500:
#         return templates.TemplateResponse(
#             "error.html",
#             {"request": request, "status_code": 500, "err": exc},
#             status_code=500,
#         )
#     elif exc.status_code == 400:
#         return templates.TemplateResponse(
#             "error.html",
#             {"request": request, "status_code": 400, "err": exc},
#             status_code=400,
#         )
#     else:
#         return templates.TemplateResponse(
#             "error.html",
#             {"request": request, "status_code": exc.status_code, "err": exc},
#             status_code=exc.status_code,
#         )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 400, "err": exc},
        status_code=400,
    )


app.include_router(auth.router)
app.include_router(test.router)
app.include_router(me.router)
app.include_router(api.router)
