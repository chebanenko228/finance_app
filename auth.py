from passlib.context import CryptContext
from sqlalchemy.orm import Session
from models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
def get_user_by_fullname(db: Session, full_name: str):
    return db.query(User).filter(User.full_name == full_name).first()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
