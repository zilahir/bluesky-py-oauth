import json
from urllib.parse import urlencode, quote


def abs_path(s: str, origin: str) -> str:
    return f"{origin}/{s}"


class OauthMetadata:
    def __init__(self, env):
        print(f"Initializing OauthMetadata with environment: {env}")
        self.APP_URL = "https://app.example.com"
        self.is_dev = env == "development"
        self.ORIGIN = "http://127.0.0.1:5000" if self.is_dev else self.APP_URL
        self.REDIRECT_URI = abs_path("oauth/callback", self.ORIGIN)
        self.SCOPE = "atproto transition:generic"

        self.config = {
            "client_name": "Project Name",
            "client_id": (
                f"http://localhost?"
                f"redirect_uri={quote(self.REDIRECT_URI)}"
                f"&scope={quote(self.SCOPE)}"
                if self.is_dev
                else f"{self.ORIGIN}/client-metadata.json"
            ),
            "client_uri": self.ORIGIN,
            "redirect_uris": [self.REDIRECT_URI],
            "policy_uri": f"{self.APP_URL}/policy",
            "tos_uri": f"{self.APP_URL}/tos",
            "scope": self.SCOPE,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "application_type": "web",
            # "token_endpoint_auth_method": "private_key_jwt",
            "token_endpoint_auth_method": "none",
            "dpop_bound_access_tokens": True,
            "jwks_uri": f"{self.APP_URL}/jwks.json",
            # "token_endpoint_auth_signing_alg": "ES256",  # if auth_method is None
        }

    def to_json(self) -> str:
        return json.dumps(self.config, indent=2)

    def get_config(self):
        return self.config
