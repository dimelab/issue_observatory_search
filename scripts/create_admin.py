#!/usr/bin/env python3
"""Script to create an admin user."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from backend.database import AsyncSessionLocal, engine, Base
from backend.models.user import User
from backend.utils.auth import get_password_hash


async def create_admin_user():
    """Create an admin user interactively."""
    print("=" * 50)
    print("Create Admin User")
    print("=" * 50)
    print()

    # Get user input
    username = input("Enter admin username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        return

    email = input("Enter admin email: ").strip()
    if not email:
        print("❌ Email cannot be empty")
        return

    password = input("Enter admin password: ").strip()
    if not password:
        print("❌ Password cannot be empty")
        return

    confirm_password = input("Confirm password: ").strip()
    if password != confirm_password:
        print("❌ Passwords do not match")
        return

    print()
    print("Creating admin user...")

    # Create database session
    async with AsyncSessionLocal() as session:
        try:
            # Check if username exists
            result = await session.execute(
                select(User).where(User.username == username)
            )
            if result.scalar_one_or_none() is not None:
                print(f"❌ Username '{username}' already exists")
                return

            # Check if email exists
            result = await session.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none() is not None:
                print(f"❌ Email '{email}' already exists")
                return

            # Create admin user
            admin_user = User(
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                is_admin=True,
                is_active=True,
            )

            session.add(admin_user)
            await session.commit()
            await session.refresh(admin_user)

            print()
            print("=" * 50)
            print("✅ Admin user created successfully!")
            print("=" * 50)
            print(f"Username: {admin_user.username}")
            print(f"Email:    {admin_user.email}")
            print(f"ID:       {admin_user.id}")
            print(f"Admin:    {admin_user.is_admin}")
            print()
            print("You can now login with these credentials at:")
            print(f"  http://localhost:8080/api/auth/login")
            print()

        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            await session.rollback()
            raise


async def list_users():
    """List all existing users."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()

        if not users:
            print("No users found in database")
            return

        print()
        print("=" * 80)
        print("Existing Users")
        print("=" * 80)
        print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Admin':<6} {'Active':<6}")
        print("-" * 80)
        for user in users:
            print(f"{user.id:<5} {user.username:<20} {user.email:<30} "
                  f"{'Yes' if user.is_admin else 'No':<6} "
                  f"{'Yes' if user.is_active else 'No':<6}")
        print("=" * 80)
        print()


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--list", action="store_true", help="List existing users")
    args = parser.parse_args()

    if args.list:
        await list_users()
    else:
        await create_admin_user()


if __name__ == "__main__":
    asyncio.run(main())
