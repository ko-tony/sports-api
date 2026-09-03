from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CwaUvLiveResponse(OrmResponse):
    cityName: str
    airTemperature: float | None
    uvIndex: int | None
    date: datetime | None
    weather: str | None
    humidity: int | None


class AirQualityResponse(OrmResponse):
    cityName: str
    aqi: int | None
    pm25: int | float | None
    o3: int | float | None
    date: date | None


class EnvironmentResponse(OrmResponse):
    cityName: str
    aqi: int | None
    pm25: int | float | None
    date: date | None
    humidity: int | None
    airTemperature: float | None
