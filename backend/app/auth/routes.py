from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.models.user import User
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        User.username == user.username
    ).first()

    if existing:
        raise HTTPException(400, "User exists")

    new_user = User(
        username=user.username,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()

    return {"message": "registered"}


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    db_user = db.query(User).filter(
        User.username == form_data.username
    ).first()

    if not db_user:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(
        form_data.password,
        db_user.password
    ):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(
        {"sub": db_user.username}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }