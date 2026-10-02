"""Exception-to-HTTP mapping for route handlers touching the LLM layer."""

import httpx
from fastapi import HTTPException

from oneshot.config import settings
from oneshot.services.errors import ConflictError, NotFoundError


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        detail = f"LLM provider error ({exc.response.status_code}): {exc.response.text[:300]}"
        return HTTPException(status_code=502, detail=detail)
    # TimeoutException subclasses RequestError, so it must be checked first.
    if isinstance(exc, httpx.TimeoutException):
        return HTTPException(
            status_code=504,
            detail=(
                f"LLM generation timed out after {settings.LLM_TIMEOUT_SECONDS}s — "
                "raise LLM_TIMEOUT_SECONDS or use a faster provider"
            ),
        )
    if isinstance(exc, httpx.RequestError):
        return HTTPException(status_code=502, detail=f"LLM provider unreachable: {exc}")
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))