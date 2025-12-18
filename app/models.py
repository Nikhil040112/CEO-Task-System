from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    planned_datetime = Column(DateTime, nullable=False)
    actual_datetime = Column(DateTime)
    priority = Column(String, default="Medium")
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # plain for now
    role = Column(String, nullable=False)      # "ceo" or "assistant"