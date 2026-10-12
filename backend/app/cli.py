import argparse
from getpass import getpass
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .core.security import hash_password
from .db.session import SessionLocal
from .models import User
from .models.entities import UserRole


def create_admin_user(
    db: Session, full_name: str, email: str, password: str
) -> User:
    full_name = full_name.strip()
    email = email.strip().lower()
    if not 2 <= len(full_name) <= 160:
        raise ValueError("Name must be between 2 and 160 characters")
    if not 5 <= len(email) <= 320 or "@" not in email:
        raise ValueError("Enter a valid email address")
    if not 8 <= len(password) <= 128:
        raise ValueError("Password must be between 8 and 128 characters")
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ValueError("An account with that email already exists")

    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise ValueError("An account with that email already exists") from None
        raise
    db.refresh(user)
    return user


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "create-admin",
        help="interactively create an administrator in the configured database",
    )
    args = parser.parse_args()

    if args.command == "create-admin":
        full_name = input("Administrator name: ")
        email = input("Administrator email: ")
        password = getpass("Administrator password (8-128 characters): ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 1

        with SessionLocal() as db:
            try:
                admin = create_admin_user(db, full_name, email, password)
            except ValueError as error:
                print(str(error), file=sys.stderr)
                return 1
        print(f"Administrator account created for {admin.email}.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
