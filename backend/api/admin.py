"""Admin API endpoints for user management."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth import UserCreate, UserResponse, UserUpdate
from backend.utils.auth import get_password_hash
from backend.utils.dependencies import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: AdminUser,
) -> UserResponse:
    """
    Create a new user (admin only).

    Args:
        user_data: User creation data
        db: Database session
        admin_user: Current admin user

    Returns:
        UserResponse: Created user information

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        is_admin=user_data.is_admin,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: AdminUser,
    skip: int = 0,
    limit: int = 100,
) -> list[UserResponse]:
    """
    Get all users (admin only).

    Args:
        db: Database session
        admin_user: Current admin user
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        list[UserResponse]: List of users
    """
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return [UserResponse.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: AdminUser,
) -> UserResponse:
    """
    Get a specific user (admin only).

    Args:
        user_id: User ID
        db: Database session
        admin_user: Current admin user

    Returns:
        UserResponse: User information

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: AdminUser,
) -> UserResponse:
    """
    Update a user (admin only).

    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        admin_user: Current admin user

    Returns:
        UserResponse: Updated user information

    Raises:
        HTTPException: If user not found or email already exists
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if email is being updated and already exists
    if user_data.email is not None and user_data.email != user.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        user.email = user_data.email

    # Update password if provided
    if user_data.password is not None:
        user.password_hash = get_password_hash(user_data.password)

    # Update is_active if provided
    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin_user: AdminUser,
) -> None:
    """
    Delete a user and all their data (admin only).

    Args:
        user_id: User ID
        db: Database session
        admin_user: Current admin user

    Raises:
        HTTPException: If user not found or trying to delete self
    """
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.commit()
