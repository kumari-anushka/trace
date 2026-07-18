class RepositoryAlreadyExistsError(Exception):
    pass


class InvalidGitHubRepositoryURLError(Exception):
    pass


class RepositoryNotFoundError(Exception):
    pass


class SnapshotAlreadyExistsError(Exception):
    pass


class IngestionJobNotFoundError(Exception):
    pass


class InvalidIngestionTransitionError(Exception):
    pass


class InvalidIngestionProgressError(Exception):
    pass


class RepositorySnapshotNotFoundError(Exception):
    pass
