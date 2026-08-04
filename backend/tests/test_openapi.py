from fastapi.testclient import TestClient


def test_openapi_uses_api_prefix_for_product_routes(
    client: TestClient,
) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/health" in paths
    assert "/api/repositories" in paths
    assert "/api/repositories/{repository_id}/ingestion" in paths
    assert "/api/repository-versions" in paths
    assert "/api/ingestion-jobs/{ingestion_job_id}" in paths
    assert "/api/repositories/{repository_id}/versions/{repository_version_id}/graph" in paths
    assert (
        "/api/repositories/{repository_id}/versions/{repository_version_id}/graph/"
        "nodes/{node_id}/neighbors" in paths
    )

    assert "/repositories" not in paths
    assert "/repository-versions" not in paths
    assert "/ingestion-jobs/{ingestion_job_id}" not in paths


def test_legacy_unprefixed_product_route_is_not_available(
    client: TestClient,
) -> None:
    response = client.get("/repositories")

    assert response.status_code == 404
    assert response.json() == {
        "message": "Not Found",
    }
