#!/usr/bin/env python3
"""
Bulk user creation script.

Reads a text file with one user per line in the format:
username;password

Example:
    alice;securepass123
    bob;anotherpass456
    charlie;pass789

Usage:
    python scripts/add_users.py users.txt
    python scripts/add_users.py users.txt --admin  # Make all users admins
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.utils.auth import get_password_hash


async def create_user(
    session,
    username: str,
    password: str,
    is_admin: bool = False,
) -> tuple[bool, str]:
    """
    Create a single user.

    Args:
        session: Database session
        username: Username
        password: Plain text password
        is_admin: Whether user should be admin

    Returns:
        Tuple of (success, message)
    """
    try:
        # Check if username already exists
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return False, f"User '{username}' already exists"

        # Create email from username (you can modify this logic)
        email = f"{username}@localhost"

        # Check if email already exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            # Try alternative email
            email = f"{username}@example.com"

        # Hash password
        password_hash = get_password_hash(password)

        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=is_admin,
            is_active=True,
        )

        session.add(user)
        await session.flush()

        return True, f"Created user '{username}' (ID: {user.id})"

    except IntegrityError as e:
        await session.rollback()
        return False, f"Failed to create user '{username}': {str(e)}"
    except Exception as e:
        await session.rollback()
        return False, f"Error creating user '{username}': {str(e)}"


async def bulk_add_users(file_path: str, is_admin: bool = False):
    """
    Add users from a text file.

    Args:
        file_path: Path to text file with username;password per line
        is_admin: Whether to make all users admins
    """
    # Check file exists
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Error: File '{file_path}' not found")
        sys.exit(1)

    # Read file
    print(f"📖 Reading users from: {file_path}")
    users_to_add = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse line
                if ";" not in line:
                    print(f"⚠️  Warning: Skipping line {line_num} (invalid format): {line}")
                    continue

                parts = line.split(";", 1)
                if len(parts) != 2:
                    print(f"⚠️  Warning: Skipping line {line_num} (invalid format): {line}")
                    continue

                username, password = parts[0].strip(), parts[1].strip()

                if not username or not password:
                    print(f"⚠️  Warning: Skipping line {line_num} (empty username or password)")
                    continue

                users_to_add.append((username, password))

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)

    if not users_to_add:
        print("❌ No valid users found in file")
        sys.exit(1)

    print(f"✅ Found {len(users_to_add)} users to add")
    print()

    # Add users to database
    async with AsyncSessionLocal() as session:
        success_count = 0
        error_count = 0

        for username, password in users_to_add:
            success, message = await create_user(
                session,
                username,
                password,
                is_admin=is_admin,
            )

            if success:
                print(f"✅ {message}")
                success_count += 1
            else:
                print(f"❌ {message}")
                error_count += 1

        # Commit all changes
        try:
            await session.commit()
            print()
            print(f"🎉 Successfully added {success_count} user(s)")
            if error_count > 0:
                print(f"⚠️  {error_count} user(s) failed")
        except Exception as e:
            await session.rollback()
            print()
            print(f"❌ Failed to commit changes: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_users.py <users_file> [--admin]")
        print()
        print("File format: username;password per line")
        print("Example:")
        print("  alice;securepass123")
        print("  bob;anotherpass456")
        print()
        print("Options:")
        print("  --admin    Make all users administrators")
        sys.exit(1)

    file_path = sys.argv[1]
    is_admin = "--admin" in sys.argv

    if is_admin:
        print("⚠️  Creating users with admin privileges")
        print()

    asyncio.run(bulk_add_users(file_path, is_admin))


if __name__ == "__main__":
    main()
