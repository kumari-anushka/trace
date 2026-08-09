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


class PrivateGitHubRepositoryError(TraceError):
    default_message = "Private repositories are not supported. Use a public GitHub repository."


class GitHubAPIError(TraceError):
    default_message = "GitHub API request failed"


class RetryableProviderError(TraceError):
    default_message = "External provider request failed temporarily"


class RetryableGitHubAPIError(GitHubAPIError, RetryableProviderError):
    default_message = "GitHub API request failed temporarily"


class GitHubRateLimitError(RetryableGitHubAPIError):
    default_message = "GitHub API rate limit exceeded"

    def __init__(
        self,
        message: str | None = None,
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class OpenAIAPIError(TraceError):
    default_message = "OpenAI API request failed"


class RetryableOpenAIAPIError(OpenAIAPIError, RetryableProviderError):
    default_message = "OpenAI API request failed temporarily"


class RepositoryAlreadyExistsError(TraceError):
    default_message = "Repository already exists"


class RepositoryNotFoundError(TraceError):
    default_message = "Repository not found"


class RepositoryVersionAlreadyExistsError(TraceError):
    default_message = "Repository version already exists"


class RepositoryVersionNotFoundError(TraceError):
    default_message = "Repository version not found"


class GraphNodeNotFoundError(TraceError):
    default_message = "Graph node not found"


class IngestionJobNotFoundError(TraceError):
    default_message = "Ingestion job not found"


class ActiveIngestionJobAlreadyExistsError(TraceError):
    default_message = "An ingestion job is already active for this repository version"


class IngestionStageNotFoundError(TraceError):
    default_message = "Ingestion stage not found"


class InvalidIngestionJobTransitionError(TraceError):
    default_message = "Invalid ingestion job status transition"


class InvalidIngestionProgressError(TraceError):
    default_message = "Ingestion progress must be between 0 and 100"


class InvalidIngestionStageTransitionError(TraceError):
    default_message = "Invalid ingestion stage status transition"


class InvalidIngestionStageProgressError(TraceError):
    default_message = "Ingestion stage progress must be between 0 and 100"


class IngestionDispatchError(TraceError):
    default_message = "Failed to dispatch ingestion job"
