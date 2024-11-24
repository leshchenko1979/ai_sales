from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Dialog(Base):
    __tablename__ = 'dialogs'

    id = Column(BigInteger, primary_key=True)
    target_username = Column(String, nullable=False)
    status = Column(String, nullable=False)  # active/stopped
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="dialog")

class Message(Base):
    __tablename__ = 'messages'

    id = Column(BigInteger, primary_key=True)
    dialog_id = Column(BigInteger, ForeignKey('dialogs.id'))
    direction = Column(String, nullable=False)  # in/out
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    dialog = relationship("Dialog", back_populates="messages")
