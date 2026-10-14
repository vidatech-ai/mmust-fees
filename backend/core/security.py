import time
import bcrypt
import jwt
from fastapi import Header, HTTPException
from core.config import JWT_SECRET
from core.db import supabase


def hash_password(password: str) -> str:
    if len(password.encode()) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(subject: str, role: str, hours: int = 8) -> str:
    payload = {"sub": subject, "role": role, "exp": int(time.time()) + hours * 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode(authorization: str | None, role: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, sign in again")
    if data.get("role") != role:
        raise HTTPException(403, "Not allowed")
    return data["sub"]


def current_student(authorization: str | None = Header(None)) -> str:
    sid = _decode(authorization, "student")
    rows = supabase.table("students").select("active").eq("id", sid).limit(1).execute().data
    if not rows or not rows[0]["active"]:
        raise HTTPException(401, "Account disabled")  # 401 makes the student pages sign out
    return sid


def current_admin(authorization: str | None = Header(None)) -> str:
    return _decode(authorization, "admin")
