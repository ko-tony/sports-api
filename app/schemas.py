from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnvironmentResponse(BaseModel):
    """單一縣市的空氣品質與天氣即時值。"""

    model_config = ConfigDict(from_attributes=True)

    cityName: str
    aqi: int | None
    pm25: int | float | None
    o3: int | float | None
    aqiDate: datetime | None
    airTemperature: float | None
    humidity: int | None
    uvIndex: int | None
    weather: str | None
    weatherDate: datetime | None
