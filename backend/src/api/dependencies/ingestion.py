from src.api.dependencies.github import GithubSession
from src.db.dependencies import DatabaseSession
from src.services.ingestion_runner import IngestionRunner


def get_ingestion_runner(
    session: DatabaseSession,
    github_client: GithubSession,
) -> IngestionRunner:
    return IngestionRunner(
        session,
        github_client=github_client,
    )
