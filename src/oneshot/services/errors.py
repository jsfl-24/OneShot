"""Domain-level exception types shared across services."""


class NotFoundError(ValueError):
    """Raised when a requested resource does not exist."""


class ConflictError(ValueError):
    """Raised when an operation conflicts with the current state of a resource."""


class InvalidDataError(ValueError):
    """Raised when caller-supplied data is structurally invalid (bad request)."""