from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from config import DATABASE_URL

Base = declarative_base()

class Dialog(Base):
    __tablename__ = 'dialogs'

    id = Column(BigInteger, primary_key=True)
    target_username = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = 'messages'

    id = Column(BigInteger, primary_key=True)
    dialog_id = Column(BigInteger, ForeignKey('dialogs.id'))
    direction = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# Create tables
def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
