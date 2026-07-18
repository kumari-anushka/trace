from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
)
from src.models.repository import Repository
from src.stores.repository_store import RepositoryStore


class RepositoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository_store = RepositoryStore(session)

    async def create_repository(
        self,
        *,
        github_url: str,
        default_branch: str,
    ) -> Repository:
        normalized_url, owner, name = self._parse_github_url(github_url)

        existing_repository = await self.repository_store.get_by_github_url(
            normalized_url,
        )

        if existing_repository is not None:
            raise RepositoryAlreadyExistsError

        try:
            return await self.repository_store.create(
                github_url=normalized_url,
                owner=owner,
                name=name,
                default_branch=default_branch.strip(),
            )
        except IntegrityError:
            await self.session.rollback()
            raise RepositoryAlreadyExistsError from None

    @staticmethod
    def _parse_github_url(
        github_url: str,
    ) -> tuple[str, str, str]:
        parsed_url = urlparse(github_url)

        if parsed_url.hostname not in {"github.com", "www.github.com"}:
            raise InvalidGitHubRepositoryURLError

        path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

        if len(path_parts) != 2:
            raise InvalidGitHubRepositoryURLError

        owner, name = path_parts
        name = name.removesuffix(".git")

        if not owner or not name:
            raise InvalidGitHubRepositoryURLError

        normalized_url = f"https://github.com/{owner}/{name}"

        return normalized_url, owner, name
