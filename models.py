from sqlalchemy import Column, Integer, String, Boolean, Date 
from sqlalchemy.sql import func 
from database import Base

class TodoDB(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(Date, server_default=func.current_date())
    priority = Column(String, default="Low Priority")
