from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.user_profile import UserProfile
from app.schemas.user_profile import UserProfileCreate, UserProfileRead, UserProfileUpdate
router = APIRouter()

async def get_profile(db: AsyncSession) -> UserProfile | None:
    return await db.scalar(select(UserProfile).limit(1))

@router.get('/user-profile', response_model=UserProfileRead | None)
async def read_user_profile(db: AsyncSession=Depends(get_db)) -> UserProfile | None:
    return await get_profile(db)

@router.post('/user-profile', response_model=UserProfileRead, status_code=status.HTTP_201_CREATED)
async def create_user_profile(payload: UserProfileCreate, db: AsyncSession=Depends(get_db)) -> UserProfile:
    if await get_profile(db) is not None:
        raise HTTPException(status_code=409, detail='User profile already exists')
    profile = UserProfile(**payload.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile

@router.put('/user-profile', response_model=UserProfileRead)
async def update_user_profile(payload: UserProfileUpdate, db: AsyncSession=Depends(get_db)) -> UserProfile:
    profile = await get_profile(db)
    if profile is None:
        profile = UserProfile(**payload.model_dump())
        db.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile

@router.delete('/user-profile', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_profile(db: AsyncSession=Depends(get_db)) -> Response:
    profile = await get_profile(db)
    if profile is not None:
        await db.delete(profile)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
