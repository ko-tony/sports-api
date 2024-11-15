# 從SQLAlchemy引入相應的參數，來設定models
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Date

# 從database.py引入剛剛設定好的Base，並用它來建立要存入資料庫的資料形態
from .database import Base

# 建立class並繼承Base，設定存入的tablename，並設定PK，還有各個column存入的資料形態
class Weather(Base):
    __tablename__ = "weather"

    city = Column(String, primary_key=True)
    temp_lo = Column(Integer)
    temp_hi = Column(Integer)
    prcp = Column(Integer)
    date = Column(Date)

class CwaUvLive(Base):
    __tablename__ = "cwa_uv_live"

    cityName = Column(String, primary_key=True)
    uvIndex = Column(Integer)
    date = Column(Date)
    weather = Column(String)
    humidity = Column(Integer)

class MoenvLive(Base):
    __tablename__ = "moenv_live"

    cityName = Column(String, primary_key=True)
    aqi = Column(Integer)
    date = Column(Date)

# class User(Base):
#     __tablename__ = "users"

#     user_id = Column(Integer, primary_key=True, index=True)
#     username = Column(String, unique=True, index=True)
#     full_name = Column(String)
#     email = Column(String, unique=True, index=True)
#     hashed_password = Column(String)
#     disabled = Column(Boolean, default=False)
