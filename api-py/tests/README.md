# Tests

This directory contains test suites for the atproto OAuth application.

## Setup

Install test dependencies:

```bash
# Using pip
pip install pytest pytest-mock

# Or using uv (if you're using uv)
uv pip install pytest pytest-mock
```

## Running Tests

Run all tests:
```bash
pytest
```

Run tests with verbose output:
```bash
pytest -v
```

Run a specific test file:
```bash
pytest tests/test_token_refresh.py
```

Run a specific test:
```bash
pytest tests/test_token_refresh.py::TestTokenRefresh::test_token_refresh_on_expired_token
```

Run tests with coverage (requires pytest-cov):
```bash
pytest --cov=. --cov-report=html
```

## Test Structure

### `test_token_refresh.py`

Tests for the automatic token refresh functionality in `pds_authed_req`:

- **`test_token_refresh_on_expired_token`**: Validates that when a token expires (HTTP 400 with "invalid_token" error), `pds_authed_req` automatically:
  1. Detects the expired token error
  2. Calls `refresh_token_request` to get new tokens
  3. Updates the OAuth session in the database
  4. Retries the original request with the new token
  5. Returns a successful response

- **`test_no_refresh_on_success`**: Ensures that successful requests don't trigger unnecessary token refresh attempts.

- **`test_refresh_failure_returns_original_error`**: Verifies that if token refresh fails, the original error response is returned without retrying the request.

- **`test_dpop_nonce_refresh`**: Tests that DPoP nonce errors are handled correctly by retrying with the new nonce from the server response.

## Test Design

The tests use mocking to avoid making real network calls or database operations:

- **Mock Database**: Database sessions and queries are mocked to simulate OAuth session retrieval and updates
- **Mock HTTP**: Network requests are mocked to simulate server responses (expired token, success, errors)
- **Mock JWK**: Cryptographic keys are mocked to avoid key generation overhead

## Adding New Tests

When adding new tests:

1. Create a new test file named `test_*.py` in the `tests/` directory
2. Use pytest fixtures for common setup (see existing fixtures in `test_token_refresh.py`)
3. Follow the naming convention: `test_<functionality_being_tested>`
4. Add descriptive docstrings explaining what each test validates
5. Use appropriate markers (`@pytest.mark.unit`, `@pytest.mark.integration`, etc.)

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -e .
    pytest -v
```
