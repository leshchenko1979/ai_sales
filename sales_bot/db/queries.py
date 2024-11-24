from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from .models import Base, Dialog, Message

# Создаем движок базы данных
engine = create_engine(DATABASE_URL)

# Создаем фабрику сессий
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)

async def get_db():
    """Получение сессии базы данных"""
    db = SessionLocal()
    try:
        return db
    except:
        db.close()
        raise

async def create_dialog(username: str):
    """Создание нового диалога"""
    db = SessionLocal()
    try:
        dialog = Dialog(target_username=username, status='active')
        db.add(dialog)
        db.commit()
        return dialog.id
    finally:
        db.close()

async def save_message(dialog_id: int, direction: str, content: str):
    """Сохранение сообщения"""
    db = SessionLocal()
    try:
        message = Message(dialog_id=dialog_id, direction=direction, content=content)
        db.add(message)
        db.commit()
    finally:
        db.close()
