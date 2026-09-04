"""共用的 Cloud SQL 寫入工具。

新增資料源時，準備好 table 名稱與欄位順序就能直接呼叫 upsert_rows。
"""

import logging
from collections.abc import Sequence
from typing import Any

import psycopg2
from psycopg2 import sql

from config import db_connection_kwargs

logger = logging.getLogger(__name__)


def upsert_rows(
    table: str,
    columns: Sequence[str],
    conflict_column: str,
    rows: Sequence[Sequence[Any]],
) -> int:
    """依 conflict_column 做 upsert，回傳寫入筆數。

    with 區塊會在例外時自動 rollback，正常結束時 commit。
    """
    if not rows:
        logger.warning("沒有可寫入的資料：%s", table)
        return 0

    updates = [column for column in columns if column != conflict_column]
    statement = sql.SQL(
        "INSERT INTO public.{table} ({columns}) VALUES ({placeholders}) "
        "ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
    ).format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        placeholders=sql.SQL(", ").join(sql.Placeholder() * len(columns)),
        conflict=sql.Identifier(conflict_column),
        updates=sql.SQL(", ").join(
            sql.SQL("{column} = EXCLUDED.{column}").format(column=sql.Identifier(c))
            for c in updates
        ),
    )

    with psycopg2.connect(**db_connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(statement, rows)

    logger.info("已寫入 %s 筆資料到 %s", len(rows), table)
    return len(rows)
