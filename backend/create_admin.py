import getpass
from core.db import supabase
from core.security import hash_password

username = input("Admin username: ").strip().lower()
password = getpass.getpass("Admin password (min 10 characters): ")
if len(password) < 10:
    raise SystemExit("Password too short.")
if password != getpass.getpass("Repeat password: "):
    raise SystemExit("Passwords do not match.")

supabase.table("admins").insert(
    {"username": username, "password_hash": hash_password(password)}
).execute()
print("Admin created.")
