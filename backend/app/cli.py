import argparse
from getpass import getpass
from pathlib import Path
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .core.security import hash_password
from .db.migrate_sqlite_to_postgresql import migrate_sqlite_to_postgresql
from .db.session import SessionLocal
from .models import AuditLog, AuthSession, Branch, Organization, Queue, Service, User
from .models.entities import UserRole
from .services.database_backup import create_database_backup, restore_database


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


def bootstrap_super_admin(db: Session) -> User:
    email = settings.super_admin_email
    if email is None:
        raise ValueError(
            "Set SUPER_ADMIN_EMAIL to the verified account email before bootstrapping."
        )
    email = email.strip().lower()

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        raise ValueError(
            "No existing account matches SUPER_ADMIN_EMAIL. Register and verify "
            "the account first, then rerun this command."
        )
    if not user.email_verified:
        raise ValueError(
            "The configured account has not verified its email. No role was changed."
        )
    if not user.is_active:
        raise ValueError(
            "The configured account is inactive. No role was changed."
        )

    existing_super_admin = db.scalar(
        select(User).where(User.role == UserRole.SUPER_ADMIN)
    )
    if existing_super_admin is not None:
        if existing_super_admin.id != user.id:
            raise ValueError(
                "A Super Admin is already configured. Contact the existing "
                "Super Admin for recovery."
            )
        return user

    now = datetime.now(timezone.utc)
    user.role = UserRole.SUPER_ADMIN
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.add(
        AuditLog(
            actor_user_id=None,
            action="super_admin.bootstrap",
            target_type="user",
            target_id=str(user.id),
            details={"email": email, "proof": "verified_account"},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_super_admin = db.scalar(
            select(User).where(User.role == UserRole.SUPER_ADMIN)
        )
        if existing_super_admin is not None:
            raise ValueError(
                "A Super Admin is already configured. No account was changed."
            ) from None
        raise
    db.refresh(user)
    return user


def seed_demo_catalog(db: Session) -> tuple[Organization, Branch]:
    organization_name = "QueueLess Demo Center"
    organization_slug = "queueless-demo-center"
    branch_name = "Central Demo Branch"
    service_specs = (
        (
            "Passport services",
            "PASS",
            "Apply for or renew a passport. Demo service for exploring QueueLess.",
            12,
            "P",
        ),
        (
            "Healthcare check-in",
            "CARE",
            "Check in for a clinic visit and follow your place in line.",
            8,
            "H",
        ),
        (
            "City permits",
            "PERM",
            "Get help with local permits and public services.",
            15,
            "C",
        ),
    )

    organization = db.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        organization = Organization(
            name=organization_name,
            slug=organization_slug,
            description=(
                "A sample organization for exploring the QueueLess live queue experience."
            ),
            is_active=True,
            is_approved=True,
        )
        db.add(organization)
        db.flush()
    elif organization.name != organization_name:
        raise ValueError(
            f"The demo organization slug {organization_slug!r} is already in use."
        )
    elif not organization.is_active or not organization.is_approved:
        raise ValueError(
            "The existing demo organization is inactive or unapproved; no data was changed."
        )

    branch = db.scalar(
        select(Branch).where(
            Branch.organization_id == organization.id,
            Branch.name == branch_name,
        )
    )
    if branch is None:
        branch = Branch(
            organization_id=organization.id,
            name=branch_name,
            address="100 Market Street, Demo City",
            timezone="UTC",
            is_active=True,
        )
        db.add(branch)
        db.flush()
    elif not branch.is_active:
        raise ValueError(
            "The existing demo branch is inactive; no data was changed."
        )

    for name, code, description, minutes, prefix in service_specs:
        service = db.scalar(
            select(Service).where(
                Service.branch_id == branch.id,
                Service.code == code,
            )
        )
        if service is None:
            service = Service(
                branch_id=branch.id,
                name=name,
                code=code,
                description=description,
                average_service_minutes=minutes,
                is_active=True,
            )
            db.add(service)
            db.flush()
        elif service.name != name or not service.is_active:
            raise ValueError(
                f"The demo service code {code!r} is already in use or inactive."
            )

        queue = db.scalar(
            select(Queue).where(
                Queue.service_id == service.id,
                Queue.name == "Main queue",
            )
        )
        if queue is None:
            db.add(Queue(service_id=service.id, name="Main queue", prefix=prefix))
        elif queue.prefix != prefix:
            raise ValueError(
                f"The demo queue for {code!r} already has a different prefix."
            )

    db.commit()
    db.refresh(organization)
    db.refresh(branch)
    return organization, branch


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "create-admin",
        help="interactively create an administrator in the configured database",
    )
    subparsers.add_parser(
        "bootstrap-super-admin",
        help="promote the configured, existing, email-verified account once",
    )
    subparsers.add_parser(
        "seed-demo",
        help="create an idempotent local demo catalog (development only)",
    )
    backup_parser = subparsers.add_parser(
        "database-backup", help="create and verify an online SQLite backup"
    )
    backup_parser.add_argument(
        "--directory",
        type=Path,
        help="backup directory (defaults to DATABASE_BACKUP_DIR)",
    )
    restore_parser = subparsers.add_parser(
        "database-restore", help="restore a verified backup while the API is offline"
    )
    restore_parser.add_argument("backup_path", type=Path)
    restore_parser.add_argument(
        "--confirm-offline",
        action="store_true",
        help="confirm all QueueLess API processes are stopped",
    )
    migration_parser = subparsers.add_parser(
        "migrate-sqlite-to-postgresql",
        help="copy a stopped, current SQLite database into an empty PostgreSQL database",
    )
    migration_parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="path to the SQLite database file",
    )
    migration_parser.add_argument(
        "--confirm-source-offline",
        action="store_true",
        help="confirm all QueueLess processes using the source are stopped",
    )
    migration_parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="number of records per insert batch (default: 1000)",
    )
    args = parser.parse_args()

    if args.command == "migrate-sqlite-to-postgresql":
        try:
            row_counts = migrate_sqlite_to_postgresql(
                args.source,
                confirm_source_offline=args.confirm_source_offline,
                batch_size=args.batch_size,
            )
        except (OSError, ValueError, RuntimeError) as error:
            print(f"Database migration failed: {error}", file=sys.stderr)
            return 1
        print("SQLite records copied and verified:")
        for table, count in row_counts.items():
            print(f"  {table}: {count}")
        print("The SQLite source was not modified.")
        return 0

    if args.command == "database-backup":
        try:
            path = create_database_backup(
                settings.database_url,
                args.directory or Path(settings.database_backup_dir),
            )
        except (OSError, ValueError) as error:
            print(f"Database backup failed: {error}", file=sys.stderr)
            return 1
        print(f"Verified database backup created: {path}")
        return 0

    if args.command == "database-restore":
        try:
            database_path, safety_backup = restore_database(
                args.backup_path,
                settings.database_url,
                settings.database_backup_dir,
                confirm_offline=args.confirm_offline,
            )
        except (OSError, ValueError) as error:
            print(f"Database restore failed: {error}", file=sys.stderr)
            return 1
        print(f"Database restored to {database_path}.")
        print(f"Pre-restore safety backup: {safety_backup}")
        print("Run `alembic upgrade head` before restarting QueueLess.")
        return 0

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

    if args.command == "bootstrap-super-admin":
        with SessionLocal() as db:
            try:
                admin = bootstrap_super_admin(db)
            except ValueError as error:
                print(str(error), file=sys.stderr)
                return 1
        print(f"Super Admin is configured for {admin.email}.")
        return 0

    if args.command == "seed-demo":
        if settings.environment != "development":
            print(
                "The demo catalog can only be seeded when ENVIRONMENT=development.",
                file=sys.stderr,
            )
            return 1
        with SessionLocal() as db:
            try:
                organization, branch = seed_demo_catalog(db)
            except ValueError as error:
                print(f"Demo catalog was not seeded: {error}", file=sys.stderr)
                return 1
        print(
            f"Development demo catalog ready: {organization.name} / {branch.name}."
        )
        print("No users or queue entries were created.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
