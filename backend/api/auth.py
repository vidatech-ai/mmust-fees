import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.db import supabase
from core.security import verify_password, create_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple brute-force protection: 5 failed attempts per 10 minutes
_fails: dict[str, list[float]] = {}


def _blocked(key: str) -> bool:
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < 600]
    return len(_fails[key]) >= 5


def _fail(key: str):
    _fails.setdefault(key, []).append(time.time())


class StudentLogin(BaseModel):
    reg_number: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


@router.post("/student/login")
def student_login(body: StudentLogin, request: Request):
    reg = body.reg_number.strip().upper()
    key = f"s:{reg}:{request.client.host}"
    if _blocked(key):
        raise HTTPException(429, "Too many attempts. Try again in 10 minutes.")
    res = supabase.table("students").select("*").eq("reg_number", reg).eq("active", True).execute()
    student = res.data[0] if res.data else None
    if not student or not verify_password(body.password, student["password_hash"]):
        _fail(key)
        raise HTTPException(401, "Wrong registration number or password")
    return {
        "token": create_token(student["id"], "student"),
        "student": {"name": student["name"], "reg_number": student["reg_number"]},
    }


@router.post("/admin/login")
def admin_login(body: AdminLogin, request: Request):
    username = body.username.strip().lower()
    key = f"a:{username}:{request.client.host}"
    if _blocked(key):
        raise HTTPException(429, "Too many attempts. Try again in 10 minutes.")
    res = supabase.table("admins").select("*").eq("username", username).execute()
    admin = res.data[0] if res.data else None
    if not admin or not verify_password(body.password, admin["password_hash"]):
        _fail(key)
        raise HTTPException(401, "Wrong username or password")
    return {"token": create_token(admin["id"], "admin", hours=4)}
