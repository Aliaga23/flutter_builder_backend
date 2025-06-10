from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

from uuid import UUID
from core.database import SessionLocal
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from schemas.user_schema import UserCreate, UserOut
from schemas.user_schema import UserLogin

router = APIRouter()


# Dependency para obtener la sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email ya registrado")

    new_user = User(
        username=user.username,
        email=user.email,
        password=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login")
def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")

    token = create_access_token(data={"sub": str(user.id)})
    return JSONResponse({"access_token": token, "token_type": "bearer"})



@router.get("/", response_model=list[UserOut])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()
