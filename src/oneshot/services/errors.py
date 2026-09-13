"""Domain-level exception types shared across services."""


class NotFoundError(ValueError):
    """Raised when a requested resource does not exist."""