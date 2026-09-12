"""Shared FastAPI dependency type aliases."""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from oneshot.db import get_session

DbSession = Annotated[Session, Depends(get_session)]