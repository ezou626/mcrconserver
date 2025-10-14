import logging
import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import Response

from .helpers import check_password, get_db_connection

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


def validate_session(request: Request) -> bool:
    session_authorization = request.cookies.get("Authorization")
    session_id = request.session.get("session_id")
    session_access_token = request.session.get("access_token")
    token_exp = request.session.get("token_expiry")

    if not session_authorization and not session_access_token:
        logging.info(
            "No Authorization and access_token in session, redirecting to login"
        )
        return False

    if session_authorization != session_id:
        logging.info("Authorization does not match Session Id, redirecting to login")
        return False

    if is_token_expired(token_exp):
        logging.info("Access_token is expired, redirecting to login")
        return False

    logging.info("Valid Session, Access granted.")
    return True


@router.post("/login")
def login(
    request: Request,
    response: Response,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    user=Depends(validate_session),
):
    db = get_db_connection()

    if not check_password(db, username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    request.session.update({"username": username})

    response.set_cookie(key="Authorization", value=session_id)
    return {"success": True, "message": "Login successful"}
