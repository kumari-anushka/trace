import httpx


def create_github_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://api.github.com",
        timeout=20.0,
    )
