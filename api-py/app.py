import json
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Depends, HTTPException, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from starlette.exceptions import HTTPException as StarletteHTTPException
from authlib.jose import JsonWebKey

from oauth_metadata import OauthMetadata
from routes import api, auth, campaign, me, posts
from routes.utils.postgres_connection import get_db
from settings import get_settings
from metrics import metrics_middleware, get_metrics

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

# Add Prometheus metrics middleware
app.middleware("http")(metrics_middleware)


# This is a "confidential" OAuth client, meaning it has access to a persistent secret signing key. parse that key as a global.
CLIENT_SECRET_JWK = JsonWebKey.import_key(json.loads(config("CLIENT_SECRET_JWK")))
CLIENT_PUB_JWK = json.loads(CLIENT_SECRET_JWK.as_json(is_private=False))

# Defensively check that the public JWK is really public and didn't somehow end up with secret cryptographic key info
assert "d" not in CLIENT_PUB_JWK


@app.get("/", response_class=JSONResponse)
def homepage(request: Request):
    return JSONResponse(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.get("/health")
def health_check(
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
):
    settings = settings.dict()

    try:
        db_conn = db.execute(text("SELECT 1")).fetchone()
        db_ok = db_conn is not None
    except Exception as e:
        db_ok = False

    return JSONResponse(
        {
            "env": config("ENV", default="unknown"),
            "settings": settings,
            "db_ok": db_ok,
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


# In this example of a "confidential" OAuth client, we have only a single app key being used. In a production-grade client, it best practice to periodically rotate keys. Including both a "new key" and "old key" at the same time can make this process smoother.
@app.get("/oauth/jwks.json")
def oauth_jwks():
    return JSONResponse(
        {
            "keys": [CLIENT_PUB_JWK],
        }
    )


# Prometheus metrics endpoint
@app.get("/metrics")
def metrics_endpoint():
    """Endpoint for Prometheus to scrape metrics"""
    return get_metrics()


app.include_router(auth.router)
app.include_router(me.router)
app.include_router(api.router)
app.include_router(campaign.router)
app.include_router(posts.router)
