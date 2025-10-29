from typing import Union, Annotated

from fastapi import FastAPI, HTTPException, Path, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from routers import users
from routers import sheets

from pydantic import BaseModel
from enum import Enum

from fastapi.security import OAuth2PasswordBearer

from sql_app import models
from sql_app.database import db_dependency

class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.include_router(users.router)
app.include_router(sheets.router)

@app.get("/")
def read_root():
    return {"Hello": "World"}

# 限制權限
@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}

@app.get("/weather", tags=["openAPI"])
async def get_weather(db: db_dependency):
    try:
        result = db.query(models.Weather).all()
    except Exception as e:
        raise HTTPException(status_code=405, detail='Error...')
    if not result:
        raise HTTPException(status_code=404, detail='This weather is not found...')
    return result

@app.get("/cwa_uv_live", tags=["openAPI"])
async def get_cwa_uv_live(db: db_dependency):
    try:
        result = db.query(models.CwaUvLive).all()
    except Exception as e:
        raise HTTPException(status_code=405, detail='Error...')
    if not result:
        raise HTTPException(status_code=404, detail='This CwaUvLive is not found...')
    return result

@app.get("/moenv_live", tags=["openAPI"])
async def get_moenv_uv_live(db: db_dependency):
    try:
        result = db.query(models.MoenvLive).all()
    except Exception as e:
        raise HTTPException(status_code=405, detail='Error...')
    if not result:
        raise HTTPException(status_code=404, detail='This MoenvLive is not found...')
    return result

@app.get("/env_live_1", tags=["openAPI"])
async def get_environmental_data(db: db_dependency):
    try:
        # 聯合查詢兩個表的資料
        result = db.query(
            models.MoenvLive.cityName,
            models.MoenvLive.aqi,
            models.MoenvLive.pm25,
            models.MoenvLive.date,
            models.CwaUvLive.humidity
        ).join(
            models.CwaUvLive, 
            models.MoenvLive.cityName == models.CwaUvLive.cityName
        ).all()
        
        # 將查詢結果轉換為字典格式
        environmental_data = []
        for row in result:
            environmental_data.append({
                "cityName": row.cityName,
                "aqi": row.aqi,
                "pm25": row.pm25,
                "date": row.date,
                "humidity": row.humidity
            })
        
        if not result:
            raise HTTPException(status_code=404, detail='No environmental data found...')
        
        return environmental_data
    except Exception as e:
        raise HTTPException(status_code=405, detail='Error...')