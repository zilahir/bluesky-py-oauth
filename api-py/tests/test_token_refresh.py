"""
Test suite for OAuth token refresh functionality.

This test validates that pds_authed_req automatically handles expired tokens
by refreshing them and retrying the request.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from authlib.jose import JsonWebKey


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_oauth_session():
    """Mock OAuth session with test data."""
    session = Mock()
    session.did = "did:plc:test123"
    session.access_token = "expired_token"
    session.refresh_token = "valid_refresh_token"
    session.authserver_iss = "https://bsky.social"
    session.dpop_private_jwk = json.dumps({
        "kty": "EC",
        "crv": "P-256",
        "x": "test_x",
        "y": "test_y",
        "d": "test_d"
    })
    session.dpop_authserver_nonce = "test_nonce"
    session.dpop_pds_nonce = ""
    session.pds_url = "https://test.pds.host"
    session.updated_at = datetime.utcnow()
    return session


@pytest.fixture
def mock_jwk():
    """Mock JWK for DPoP signing."""
    # Create a real JWK for testing
    jwk = JsonWebKey.generate_key('EC', 'P-256', is_private=True)
    return jwk


@pytest.fixture
def mock_http_context():
    """Mock HTTP session context manager."""
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_session)
    mock_context.__exit__ = MagicMock(return_value=False)
    return mock_context, mock_session


class TestTokenRefresh:
    """Test cases for automatic token refresh in pds_authed_req."""

    @patch('atproto_oauth.hardened_http')
    @patch('atproto_oauth.refresh_token_request')
    @patch('atproto_oauth.JsonWebKey.import_key')
    def test_token_refresh_on_expired_token(
        self,
        mock_jwk_import,
        mock_refresh_token_request,
        mock_hardened_http,
        mock_db,
        mock_oauth_session,
        mock_jwk,
        mock_http_context
    ):
        """
        Test that pds_authed_req automatically refreshes an expired token
        and retries the request.
        """
        from atproto_oauth import pds_authed_req

        # Setup mock JWK
        mock_jwk_import.return_value = mock_jwk

        # Setup mock HTTP session
        mock_context, mock_session = mock_http_context
        mock_hardened_http.get_session.return_value = mock_context

        # First response: Token expired error
        expired_response = Mock()
        expired_response.status_code = 400
        expired_response.text = '{"error": "invalid_token", "message": "Token expired: exp claim"}'
        expired_response.json.return_value = {
            "error": "invalid_token",
            "message": "Token expired: exp claim"
        }

        # Second response: Success after token refresh
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"result": "success"}

        # Configure mock session to return expired response first, then success
        mock_session.request.side_effect = [expired_response, success_response]

        # Setup token refresh mock
        new_tokens = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token"
        }
        new_dpop_nonce = "new_dpop_nonce"
        mock_refresh_token_request.return_value = (new_tokens, new_dpop_nonce)

        # Setup database query mock
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_oauth_session

        # Execute the request
        result = pds_authed_req(
            method="POST",
            url="https://test.pds.host/xrpc/com.atproto.repo.createRecord",
            access_token=mock_oauth_session.access_token,
            dpop_private_jwk_json=mock_oauth_session.dpop_private_jwk,
            user_did=mock_oauth_session.did,
            db=mock_db,
            dpop_pds_nonce="",
            body={"test": "data"}
        )

        # Assertions
        assert result.status_code == 200
        assert result.json()["result"] == "success"

        # Verify token refresh was called
        mock_refresh_token_request.assert_called_once()

        # Verify the OAuth session was updated with new tokens
        assert mock_oauth_session.access_token == new_tokens["access_token"]
        assert mock_oauth_session.refresh_token == new_tokens["refresh_token"]
        assert mock_oauth_session.dpop_authserver_nonce == new_dpop_nonce

        # Verify database commit was called
        mock_db.commit.assert_called()

        # Verify the request was made twice (initial + retry after refresh)
        assert mock_session.request.call_count == 2


    @patch('atproto_oauth.hardened_http')
    @patch('atproto_oauth.JsonWebKey.import_key')
    def test_no_refresh_on_success(
        self,
        mock_jwk_import,
        mock_hardened_http,
        mock_db,
        mock_oauth_session,
        mock_jwk,
        mock_http_context
    ):
        """
        Test that pds_authed_req does not attempt token refresh
        when the request succeeds on first try.
        """
        from atproto_oauth import pds_authed_req

        # Setup mock JWK
        mock_jwk_import.return_value = mock_jwk

        # Setup mock HTTP session
        mock_context, mock_session = mock_http_context
        mock_hardened_http.get_session.return_value = mock_context

        # Success response on first try
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"result": "success"}
        mock_session.request.return_value = success_response

        # Execute the request
        result = pds_authed_req(
            method="GET",
            url="https://test.pds.host/xrpc/app.bsky.actor.getProfile",
            access_token=mock_oauth_session.access_token,
            dpop_private_jwk_json=mock_oauth_session.dpop_private_jwk,
            user_did=mock_oauth_session.did,
            db=mock_db,
            dpop_pds_nonce=""
        )

        # Assertions
        assert result.status_code == 200
        assert result.json()["result"] == "success"

        # Verify the request was made only once (no retry)
        assert mock_session.request.call_count == 1

        # Verify no database commit (no token update)
        mock_db.commit.assert_not_called()


    @patch('atproto_oauth.hardened_http')
    @patch('atproto_oauth.refresh_token_request')
    @patch('atproto_oauth.JsonWebKey.import_key')
    def test_refresh_failure_returns_original_error(
        self,
        mock_jwk_import,
        mock_refresh_token_request,
        mock_hardened_http,
        mock_db,
        mock_oauth_session,
        mock_jwk,
        mock_http_context
    ):
        """
        Test that when token refresh fails, the original error response
        is returned without retrying the request.
        """
        from atproto_oauth import pds_authed_req

        # Setup mock JWK
        mock_jwk_import.return_value = mock_jwk

        # Setup mock HTTP session
        mock_context, mock_session = mock_http_context
        mock_hardened_http.get_session.return_value = mock_context

        # Token expired error response
        expired_response = Mock()
        expired_response.status_code = 400
        expired_response.text = '{"error": "invalid_token", "message": "Token expired: exp claim"}'
        expired_response.json.return_value = {
            "error": "invalid_token",
            "message": "Token expired: exp claim"
        }
        mock_session.request.return_value = expired_response

        # Setup token refresh to fail
        mock_refresh_token_request.side_effect = Exception("Refresh token invalid")

        # Setup database query mock
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_oauth_session

        # Execute the request
        result = pds_authed_req(
            method="POST",
            url="https://test.pds.host/xrpc/com.atproto.repo.createRecord",
            access_token=mock_oauth_session.access_token,
            dpop_private_jwk_json=mock_oauth_session.dpop_private_jwk,
            user_did=mock_oauth_session.did,
            db=mock_db,
            dpop_pds_nonce="",
            body={"test": "data"}
        )

        # Assertions
        # Should return the original expired token error
        assert result.status_code == 400
        assert result.json()["error"] == "invalid_token"

        # Verify token refresh was attempted
        mock_refresh_token_request.assert_called_once()

        # Verify the request was made only once (no retry after failed refresh)
        assert mock_session.request.call_count == 1


    @patch('atproto_oauth.hardened_http')
    @patch('atproto_oauth.JsonWebKey.import_key')
    def test_dpop_nonce_refresh(
        self,
        mock_jwk_import,
        mock_hardened_http,
        mock_db,
        mock_oauth_session,
        mock_jwk,
        mock_http_context
    ):
        """
        Test that pds_authed_req handles DPoP nonce errors by retrying
        with the new nonce from the server.
        """
        from atproto_oauth import pds_authed_req

        # Setup mock JWK
        mock_jwk_import.return_value = mock_jwk

        # Setup mock HTTP session
        mock_context, mock_session = mock_http_context
        mock_hardened_http.get_session.return_value = mock_context

        # First response: DPoP nonce error
        nonce_error_response = Mock()
        nonce_error_response.status_code = 400
        nonce_error_response.headers = {"DPoP-Nonce": "new_nonce_value"}
        nonce_error_response.text = '{"error": "use_dpop_nonce"}'
        nonce_error_response.json.return_value = {
            "error": "use_dpop_nonce"
        }

        # Second response: Success with new nonce
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"result": "success"}

        mock_session.request.side_effect = [nonce_error_response, success_response]

        # Setup database query mock
        mock_query = mock_db.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.first.return_value = mock_oauth_session

        # Execute the request
        result = pds_authed_req(
            method="POST",
            url="https://test.pds.host/xrpc/com.atproto.repo.createRecord",
            access_token=mock_oauth_session.access_token,
            dpop_private_jwk_json=mock_oauth_session.dpop_private_jwk,
            user_did=mock_oauth_session.did,
            db=mock_db,
            dpop_pds_nonce="",
            body={"test": "data"}
        )

        # Assertions
        assert result.status_code == 200
        assert result.json()["result"] == "success"

        # Verify the DPoP nonce was updated in database
        assert mock_oauth_session.dpop_pds_nonce == "new_nonce_value"
        mock_db.commit.assert_called()

        # Verify the request was made twice (initial + retry with new nonce)
        assert mock_session.request.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
