"""Tests for API versioning (v0.3.4, updated for v0.3.9).

These tests ensure:
- API routes are under /v1 prefix
- CP routes are under /cp prefix (unversioned - v0.3.9)
- X-Dictacode-API-Version header is present on API responses
- Old unversioned paths return 404
"""

import pytest


class TestAPIVersioning:
    """Tests for API versioning."""

    def test_api_routes_versioned(self):
        """API routes must be under /v1 prefix (v0.3.9).

        Note: CP routes at /cp are intentionally unversioned per v0.3.9.
        This test validates only the API app routes.
        """
        from dictacode_stt.api import create_api_app

        app = create_api_app()

        unversioned_routes = []
        for route in app.routes:
            if hasattr(route, "path"):
                path = route.path
                # Allow: /v1/*, /static/*, /docs/* (oauth2-redirect), / (root)
                if (
                    path.startswith("/v1")
                    or path.startswith("/static")
                    or path.startswith("/docs")  # FastAPI oauth2-redirect
                    or path == "/"
                ):
                    continue
                unversioned_routes.append(path)

        assert not unversioned_routes, f"Unversioned API routes found: {unversioned_routes}"

    def test_version_header_on_v1_health(self):
        """v1/health should return X-Dictacode-API-Version header."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/health")

        assert response.status_code == 200
        assert response.headers.get("X-Dictacode-API-Version") == "v1"

    def test_version_header_on_v1_ready(self):
        """v1/ready should return X-Dictacode-API-Version header."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/ready")

        assert response.status_code == 200
        assert response.headers.get("X-Dictacode-API-Version") == "v1"

    def test_openapi_at_v1_path(self):
        """OpenAPI JSON should be available at /v1/openapi.json."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_docs_at_v1_path(self):
        """Swagger docs should be available at /v1/docs."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestOldPathsReturn404:
    """Tests that old unversioned paths return 404."""

    def test_old_health_returns_404(self):
        """Old /health path should return 404."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/health")

        assert response.status_code == 404

    def test_old_ready_returns_404(self):
        """Old /ready path should return 404."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/ready")

        assert response.status_code == 404

    def test_old_api_audio_ports_returns_404(self):
        """Old /api/audio/ports path should return 404."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/api/audio/ports")

        assert response.status_code == 404

    def test_old_api_diagnostics_returns_404(self):
        """Old /api/diagnostics/status path should return 404."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/api/diagnostics/status")

        assert response.status_code == 404


class TestVersionedEndpointsWork:
    """Tests that versioned endpoints return expected responses."""

    def test_v1_health_returns_ok(self):
        """/v1/health should return healthy status."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_v1_api_audio_ports_returns_list(self):
        """/v1/api/audio/ports should return ports list."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/api/audio/ports")

        assert response.status_code == 200
        data = response.json()
        assert "ports" in data

    def test_v1_api_license_returns_state(self):
        """/v1/api/license should return badge state."""
        from starlette.testclient import TestClient

        from dictacode_stt.api import create_combined_app

        client = TestClient(create_combined_app())
        response = client.get("/v1/api/license")

        assert response.status_code == 200
        data = response.json()
        assert "tier" in data
