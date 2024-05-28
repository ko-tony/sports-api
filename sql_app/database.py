from typing import Annotated
from fastapi import Depends

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# 連接到的URL，這裡用postgresql舉例
# postgresql://user:password@postgresserver/db
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:5yamzoOAlVlURyF8@34.80.59.7:5432/postgres"

# 用create_engine對這個URL_DATABASE建立一個引擎
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 使用sessionmaker來與資料庫建立一個對話，記得要bind=engine，這才會讓專案和資料庫連結
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 創建SQLAlchemy的一個class，然後在其它地方使用
Base = declarative_base()

# 每次操作get_db時，db使用SessionLocal中提供的資料與資料庫連線，產生db存儲，完事後關閉
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 一個db的dependency，可以看做是要操作的db，這裡的Depends對應get_db，get_db對應SessionLocal
db_dependency = Annotated[Session, Depends(get_db)]