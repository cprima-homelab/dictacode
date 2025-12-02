"""Tests for API vs Web CP split (v0.3.9).

These tests verify:
- OpenAPI only includes API routes (no CP routes)
- CP routes are served at /cp (unversioned)
- API routes are served at /v1 (versioned)
- Static files accessible at /static
- API-only mode excludes CP routes
"""

import pytest
from starlette.testclient import TestClient


class TestOpenApiExclusion:
    """Verify OpenAPI only includes API routes."""

    def test_openapi_excludes_cp_routes(self):
        """CP routes should not appear in OpenAPI spec."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        paths = spec.get("paths", {})

        for path in paths:
            assert "/cp" not in path, f"CP route leaked into OpenAPI: {path}"

    def test_openapi_includes_api_routes(self):
        """API routes should appear in OpenAPI spec."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/openapi.json")
        spec = response.json()
        paths = spec.get("paths", {})

        assert any("/api/audio" in p for p in paths), "Audio API missing from OpenAPI"
        assert any("/health" in p for p in paths), "Health endpoint missing from OpenAPI"


class TestRouteSeparation:
    """Verify routes are served by correct app."""

    def test_cp_routes_return_html(self):
        """CP routes should return HTML (unversioned at /cp/).

        Note: Starlette Mount requires trailing slash for root path.
        /cp/ works, /cp returns 404 (this is standard Starlette behavior).
        """
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/cp/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_api_routes_return_json(self):
        """API routes should return JSON (versioned at /v1)."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    def test_old_v1_cp_url_returns_404(self):
        """Old /v1/cp URLs should not work (breaking change from v0.3.9)."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/cp")
        assert response.status_code == 404

    def test_cp_config_at_new_url(self):
        """CP config should be at /cp/config (not /v1/cp/config)."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/cp/config")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_cp_diagnostics_at_new_url(self):
        """CP diagnostics should be at /cp/diagnostics (not /v1/cp/diagnostics)."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/cp/diagnostics")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestStaticFiles:
    """Verify static files served at root level."""

    def test_static_css_accessible(self):
        """Static CSS files should be at /static/*."""
        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/static/css/base.css")
        # Should succeed if file exists, or 404 if not - not 500
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert "text/css" in response.headers.get("content-type", "")


class TestApiOnlyMode:
    """Verify API-only mode excludes web routes."""

    def test_cp_not_available_in_api_only(self):
        """CP routes should 404 in API-only mode."""
        from dictacode_stt.api import create_api_app

        client = TestClient(create_api_app())
        response = client.get("/cp")
        assert response.status_code == 404

    def test_api_works_in_api_only(self):
        """API routes should work in API-only mode."""
        from dictacode_stt.api import create_api_app

        client = TestClient(create_api_app())
        response = client.get("/v1/health")
        assert response.status_code == 200

    def test_openapi_works_in_api_only(self):
        """OpenAPI should work in API-only mode."""
        from dictacode_stt.api import create_api_app

        client = TestClient(create_api_app())
        response = client.get("/v1/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert "openapi" in spec


class TestWebOnlyMode:
    """Verify Web-only mode excludes API routes."""

    def test_api_not_available_in_web_only(self):
        """API routes should 404 in Web-only mode."""
        from dictacode_stt.api import create_web_app

        client = TestClient(create_web_app())
        response = client.get("/v1/health")
        assert response.status_code == 404

    def test_cp_works_in_web_only(self):
        """CP routes should work in Web-only mode."""
        from dictacode_stt.api import create_web_app

        client = TestClient(create_web_app())
        # In web-only mode, CP routes are at root (not /cp mount)
        response = client.get("/")
        assert response.status_code == 200

    def test_no_openapi_in_web_only(self):
        """OpenAPI should not exist in Web-only mode."""
        from dictacode_stt.api import create_web_app

        client = TestClient(create_web_app())
        response = client.get("/openapi.json")
        assert response.status_code == 404

        response = client.get("/docs")
        assert response.status_code == 404
