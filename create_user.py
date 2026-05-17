"""
create_user.py  —  Add or update users for RiskGuard login.

Usage:
    python create_user.py

Run this ONCE to create your admin account before starting the app.
You can run it again anytime to add more users or change passwords.
"""
import json, os, getpass
from werkzeug.security import generate_password_hash

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"
B = "\033[1m";  R = "\033[91m"; X = "\033[0m"

print(f"\n{B}{C}╔══════════════════════════════════════════╗")
print(     "║    RiskGuard  —  User  Manager          ║")
print(    f"╚══════════════════════════════════════════╝{X}\n")

users = load_users()

if users:
    print(f"  {Y}Existing users:{X}")
    for u in users:
        print(f"    • {u}")
    print()

print(f"  {C}Create a new user (or update existing){X}\n")

username = input("  Username : ").strip()
if not username:
    print(f"\n  {R}✗ Username cannot be empty.{X}\n")
    exit(1)

while True:
    password = getpass.getpass("  Password : ")
    confirm  = getpass.getpass("  Confirm  : ")
    if password != confirm:
        print(f"  {R}✗ Passwords do not match. Try again.{X}")
    elif len(password) < 6:
        print(f"  {R}✗ Password must be at least 6 characters.{X}")
    else:
        break

role = input("  Role (admin/viewer) [admin]: ").strip() or "admin"

users[username] = {
    "password_hash": generate_password_hash(password),
    "role": role
}
save_users(users)

print(f"\n  {G}✓ User '{username}' saved successfully!{X}")
print(f"  {G}✓ Password stored as secure hash (never plain text){X}")