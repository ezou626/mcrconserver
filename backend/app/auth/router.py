from fastapi import APIRouter, Form
from .helpers import get_db_connection, check_password

router = APIRouter()


@router.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = get_db_connection()

    if check_password(db, username, password):
        return {"success": True, "message": "Login successful"}
    else:
        return {"success": False, "message": "Invalid username or password"}
