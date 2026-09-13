"""Exception-to-HTTP mapping for route handlers touching the LLM layer."""

import httpx
from fastapi import HTTPException

from oneshot.services.errors import NotFoundError


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        detail = f"LLM provider error ({exc.response.status_code}): {exc.response.text[:300]}"
        return HTTPException(status_code=502, detail=detail)
    if isinstance(exc, httpx.RequestError):
        return HTTPException(status_code=502, detail=f"LLM provider unreachable: {exc}")
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))