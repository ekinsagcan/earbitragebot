from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database.connection import get_database
from app.database.models import User
from app.database.schemas import UserLogin, UserRegister, Token, APIResponse
from app.utils.security import create_user_token

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_database)
):
    """Login user and return JWT token"""
    try:
        # Check if user exists
        result = await db.execute(
            select(User).where(User.user_id == user_data.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Create new user if doesn't exist
            new_user = User(
                user_id=user_data.user_id,
                username=user_data.username,
                is_premium=False
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user = new_user
        
        # Create and return token
        token_data = create_user_token(user.user_id, user.username)
        return Token(**token_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/register", response_model=Token)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_database)
):
    """Register new user and return JWT token"""
    try:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.user_id == user_data.user_id)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # User exists, just return token
            token_data = create_user_token(existing_user.user_id, existing_user.username)
            return Token(**token_data)
        
        # Create new user
        new_user = User(
            user_id=user_data.user_id,
            username=user_data.username,
            is_premium=False
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        # Create and return token
        token_data = create_user_token(new_user.user_id, new_user.username)
        return Token(**token_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/refresh")
async def refresh_token(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_database)
):
    """Refresh user token"""
    try:
        # Verify user exists
        result = await db.execute(
            select(User).where(User.user_id == user_data.user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create new token
        token_data = create_user_token(user.user_id, user.username)
        return Token(**token_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )