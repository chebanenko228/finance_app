from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum

class RecordType(enum.Enum):
    income = "income"
    expense = "expense"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), unique=True, nullable=False)  # обмеження 100 символів
    password_hash = Column(String(255), nullable=False)
    records = relationship("FinanceRecord", back_populates="user")

class FinanceRecord(Base):
    __tablename__ = "records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date)
    category = Column(String(50), nullable=False)
    name = Column(String(100), nullable=True)
    amount = Column(Float)
    rating = Column(Integer)
    type = Column(Enum(RecordType), nullable=False)
    is_monthly = Column(Boolean, default=False)   # щомісячний чи ні
    user = relationship("User", back_populates="records")
