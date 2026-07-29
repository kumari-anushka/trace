class TraceError(Exception):
    default_message = "Unexpected application error"

    def __init__(
        self,
        message: str | None = None,
    ) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidGitHubRepositoryURLError(TraceError):
    default_message = "Invalid GitHub repository URL"


class GitHubRepositoryNotFoundError(TraceError):
    default_message = "GitHub repository not found"


class GitHubAPIError(TraceError):
    default_message = "GitHub API request failed"


class RepositoryAlreadyExistsError(TraceError):
    default_message = "Repository already exists"


class RepositoryNotFoundError(TraceError):
    default_message = "Repository not found"


class RepositoryVersionAlreadyExistsError(TraceError):
    default_message = "Repository version already exists"


class RepositoryVersionNotFoundError(TraceError):
    default_message = "Repository version not found"


class IngestionJobNotFoundError(TraceError):
    default_message = "Ingestion job not found"


class InvalidIngestionJobTransitionError(TraceError):
    default_message = "Invalid ingestion job status transition"


class InvalidIngestionProgressError(TraceError):
    default_message = "Ingestion progress must be between 0 and 100"


class IngestionDispatchError(TraceError):
    default_message = "Failed to dispatch ingestion job"
