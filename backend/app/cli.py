"""Admin CLI.  python -m app.cli create-user EMAIL PASSWORD officer|business "Full Name" """
import sys

from sqlalchemy import select

from .auth import hash_password
from .models import Session, User, init_db


def create_user(email, password, role, name):
    if role not in ("officer", "business"):
        sys.exit("role must be officer or business")
    init_db()
    with Session() as db:
        if db.scalar(select(User).where(User.email == email.lower())):
            sys.exit(f"{email} already exists")
        db.add(User(email=email.lower(), password_hash=hash_password(password), role=role, name=name))
        db.commit()
    print(f"created {role} {email}")


if __name__ == "__main__":
    if len(sys.argv) != 6 or sys.argv[1] != "create-user":
        sys.exit(__doc__)
    create_user(*sys.argv[2:])
