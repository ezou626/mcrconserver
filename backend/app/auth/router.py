import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status

from .helpers import (
    check_password,
)

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
LOG.info("Auth router is being imported")

router = APIRouter()


def is_token_expired(unix_timestamp: int) -> bool:
    if unix_timestamp:
        datetime_from_unix = datetime.fromtimestamp(unix_timestamp)
        current_time = datetime.now()
        difference_in_minutes = (datetime_from_unix - current_time).total_seconds() / 60
        return difference_in_minutes <= 0

    return True


def validate_session(request: Request) -> dict:
    session = request.session

    # Ensure session exists and has a username
    username = session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {"username": username}


@router.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
):
    if request.session and request.session.get("username"):
        return {"success": True, "message": "Already logged in"}

    if not check_password(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    request.session["username"] = username
    return {"success": True, "message": "Login successful"}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"success": True, "message": "Logout successful"}
