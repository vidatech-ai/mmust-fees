import getpass
from core.db import supabase
from core.security import hash_password

reg = input("Reg number: ").strip().upper()
name = input("Name: ").strip()
pw = getpass.getpass("Password: ")

if not reg or not name or not pw:
    raise SystemExit("Reg number, name and password are all required.")

supabase.table("students").insert(
    {"reg_number": reg, "name": name, "password_hash": hash_password(pw)}
).execute()
print("Student created:", reg)
