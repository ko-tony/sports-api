from datetime import datetime, timedelta, timezone
from typing import Annotated, Union

import jwt
from fastapi import Depends, FastAPI, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# from jwt.exceptions import InvalidTokenError
import bcrypt
# passlib 不維護了，如果用了會讓bcrypt報錯，所以直接改用bcrypt
from pydantic import BaseModel


from sql_app import models
from sql_app.database import db_dependency

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "a2d0d9b3cb079b5cddb0e3c51a958cd93dc00f8318ff843574777ebf31ca7717"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    disabled: bool

class User(BaseModel):
    user_id: int
    username: str
    full_name: str
    email: str
    disabled: bool

class UserOut(BaseModel):
    username: str
    email: str

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()

def verify_password(plain_password, hashed_password):
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password = password_byte_enc , hashed_password = hashed_password_enc)

def get_password_hash(password):
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password

def get_user(db: db_dependency, username: str):
    """
    Get a user from the database by username

    Args:
        db (DBSession): The database session
        username (str): The username to search for

    Returns:
        User: The user if found, otherwise None
    """
    try:
        user_in_db = db.query(models.User).filter(models.User.username == username).first()
        if user_in_db is None:
            return None
        user_dict = user_in_db
        if user_dict is None:
            return None
        return user_dict
    except Exception as e:
        raise RuntimeError(f"An error occurred while getting the user by username '{username}' from the database: {e}") from e
    
def authenticate_user(db: db_dependency, username: str, password: str) -> Union[User, None]:
    """Authenticate a user by username and password

    Args:
        db: The database session
        username: The username to authenticate
        password: The password to authenticate

    Returns:
        The user if authenticated, otherwise None
    """
    user = get_user(db, username)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise credentials_exception
#         token_data = TokenData(username=username)
#     except InvalidTokenError:
#         raise credentials_exception
#     user = get_user(fake_users_db, username=token_data.username)
#     if user is None:
#         raise credentials_exception
#     return user


# async def get_current_active_user(
#     current_user: Annotated[models.User, Depends(get_current_user)],
# ):
#     if current_user.disabled:
#         raise HTTPException(status_code=400, detail="Inactive user")
#     return current_user

@router.post("/register", response_model=UserOut, tags=["users"])
def register(user: UserCreate, db: db_dependency):
    user_in_db = db.query(models.User).filter((models.User.email == user.email) | (models.User.username == user.username)).first()
    if user_in_db:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or username already in use")
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        full_name='',
        email=user.email,
        hashed_password=hashed_password,
        disabled=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return UserOut(username=db_user.username, email=db_user.email)

@router.post("/token", tags=["users"])
async def login_for_access_token(
    db: db_dependency,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

# @router.get("/users/me/", response_model=models.User, tags=["users"])
# async def read_users_me(
#     current_user: Annotated[models.User, Depends(get_current_active_user)],
# ):
#     return current_user