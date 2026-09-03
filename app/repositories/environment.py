from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models


def list_cwa_uv_live(db: Session) -> list[models.CwaUvLive]:
    return list(db.scalars(select(models.CwaUvLive)).all())


def list_air_quality(db: Session) -> list[models.MoenvLive]:
    return list(db.scalars(select(models.MoenvLive)).all())


def list_environment(db: Session) -> list[object]:
    statement = select(
        models.MoenvLive.cityName,
        models.MoenvLive.aqi,
        models.MoenvLive.pm25,
        models.MoenvLive.date,
        models.CwaUvLive.humidity,
        models.CwaUvLive.airTemperature,
    ).join(
        models.CwaUvLive,
        func.replace(models.MoenvLive.cityName, "市", "")
        == models.CwaUvLive.cityName,
    )
    return list(db.execute(statement).all())
