import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Any

from google import genai
from sqlglot import parse_one, exp

from database import get_readonly_connection, rows_to_dicts

# --------------- Logging ---------------
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "nl_sql.log")

os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("nl_sql")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

# --------------- Allow-list ---------------
ALLOWED_TABLES = {
    "Routes_",
    "RouteStops",
    "ValidatorTrips",
    "StopPassages",
    "VehicleLocations",
}

ALLOWED_COLUMNS = {
    "Routes_": {
        "RouteCode",
        "RouteName",
        "NormalDuration",
    },
    "RouteStops": {
        "RouteCode",
        "StopCode",
        "StopName",
        "StopSequence",
    },
    "ValidatorTrips": {
        "TripID",
        "RouteCode",
        "LicensePlate",
        "TripDate",
        "StartTime",
        "EndTime",
    },
    "StopPassages": {
        "ID",
        "TripID",
        "StopCode",
        "PassageTime",
    },
    "VehicleLocations": {
        "ID",
        "LicensePlate",
        "RecordedAt",
        "Latitude",
        "Longitude",
        "SpeedKmh",
    },
}

FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "MERGE",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
    "DENY",
}

MAX_ROWS = 100
QUERY_TIMEOUT_SECONDS = 5

# --------------- AI system prompt ---------------
SQL_SYSTEM_PROMPT = """
Sen SQL Server için yalnizca güvenli SELECT sorgulari ureten bir asistansin.

Kullanilabilecek tablolar:

Routes_(
    RouteCode,
    RouteName,
    NormalDuration
)

RouteStops(
    RouteCode,
    StopCode,
    StopName,
    StopSequence
)

ValidatorTrips(
    TripID,
    RouteCode,
    LicensePlate,
    TripDate,
    StartTime,
    EndTime
)

StopPassages(
    ID,
    TripID,
    StopCode,
    PassageTime
)

VehicleLocations(
    ID,
    LicensePlate,
    RecordedAt,
    Latitude,
    Longitude,
    SpeedKmh
)

Kurallar:

- Sadece SELECT sorgusu üret.
- INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, EXEC veya MERGE kullanma.
- Sadece yukaridaki tablo ve kolonlari kullan.
- SQL Server syntax kullan.
- Sonuç sayisini en fazla TOP 100 ile sinirla.
- SELECT * kullanma.
- Markdown kullanma.
- Aciklama yazma.
- Yalnizca SQL sorgusunu döndür.
"""

# --------------- AI ile SQL üretimi ---------------
def sql_uret(soru: str) -> str:
    client = genai.Client()

    prompt = f"""
{SQL_SYSTEM_PROMPT}

Kullanici sorusu:

{soru}
"""

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )

    if not response.text:
        raise ValueError("AI SQL üretemedi.")

    return response.text.strip()

# --------------- SQL doğrulama ---------------
def sql_dogrula(sql: str) -> str:
    temiz_sql = sql.strip()

    if temiz_sql.startswith("```"):
        temiz_sql = re.sub(
            r"^```(?:sql)?\s*|\s*```$",
            "",
            temiz_sql,
            flags=re.IGNORECASE,
        ).strip()

    # Birden fazla statement engellenir.
    if ";" in temiz_sql.rstrip(";"):
        raise ValueError(
            "Birden fazla SQL komutuna izin verilmez."
        )

    upper_sql = temiz_sql.upper()

    # DML / DDL kontrolleri
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(
            rf"\b{keyword}\b",
            upper_sql,
        ):
            raise ValueError(
                f"İzin verilmeyen SQL komutu tespit edildi: {keyword}"
            )

    # SQL parse edilir.
    try:
        tree = parse_one(
            temiz_sql,
            read="tsql",
        )
    except Exception as e:
        raise ValueError(
            f"SQL parse edilemedi: {e}"
        )

    # Sadece SELECT
    if not isinstance(tree, exp.Select):
        raise ValueError(
            "Sadece SELECT sorgularina izin verilir."
        )

    # SELECT * engellenir.
    if any(
        isinstance(expression, exp.Star)
        for expression in tree.find_all(exp.Star)
    ):
        raise ValueError(
            "SELECT * kullanimina izin verilmez."
        )

    # --------------- Table allow-list ve alias çözümleme ---------------
    table_aliases = {}
    kullanilan_tablolar = set()

    for table in tree.find_all(exp.Table):
        table_name = table.name

        if table_name not in ALLOWED_TABLES:
            raise ValueError(
                f"İzin verilmeyen tablo kullanimi: {table_name}"
            )

        kullanilan_tablolar.add(table_name)

        alias = table.alias

        if alias:
            table_aliases[alias] = table_name

        table_aliases[table_name] = table_name

    if not kullanilan_tablolar:
        raise ValueError(
            "Sorguda izin verilen bir tablo bulunamadi."
        )

    # --------------- SELECT aliasları ---------------

    select_aliases = {
        expression.alias
        for expression in tree.expressions
        if expression.alias
    }

    # --------------- Column allow-list ---------------

    for column in tree.find_all(exp.Column):
        column_name = column.name
        table_reference = column.table

        # ORDER BY TotalTrips gibi SELECT aliaslarına izin ver.
        if (
            not table_reference
            and column_name in select_aliases
        ):
            continue

        if table_reference:
            real_table = table_aliases.get(
                table_reference
            )

            if not real_table:
                raise ValueError(
                    "Tanimsiz tablo veya alias kullanimi: "
                    f"{table_reference}"
                )

            if column_name not in ALLOWED_COLUMNS[real_table]:
                raise ValueError(
                    "İzin verilmeyen kolon kullanimi: "
                    f"{real_table}.{column_name}"
                )

        else:
            matching_tables = [
                table
                for table in kullanilan_tablolar
                if column_name in ALLOWED_COLUMNS[table]
            ]

            if not matching_tables:
                raise ValueError(
                    "İzin verilmeyen kolon kullanimi: "
                    f"{column_name}"
                )

    # --------------- TOP kontrolü ---------------
    # TOP yoksa      -> TOP 100 ekle
    # TOP <= 100     -> olduğu gibi bırak
    # TOP > 100      -> TOP 100 yap

    top_exists = re.search(
        r"\bTOP\b",
        temiz_sql,
        flags=re.IGNORECASE,
    )

    top_match = re.search(
        r"\bTOP\s*\(?\s*(\d+)\s*\)?",
        temiz_sql,
        flags=re.IGNORECASE,
    )

    if top_exists and not top_match:
        raise ValueError(
            "TOP değeri sayisal olmalidir."
        )

    if top_match:
        top_value = int(
            top_match.group(1)
        )

        if top_value > MAX_ROWS:
            temiz_sql = re.sub(
                r"\bTOP\s*\(?\s*\d+\s*\)?",
                f"TOP {MAX_ROWS}",
                temiz_sql,
                count=1,
                flags=re.IGNORECASE,
            )

    else:
        temiz_sql = re.sub(
            r"^\s*SELECT\s+",
            f"SELECT TOP {MAX_ROWS} ",
            temiz_sql,
            count=1,
            flags=re.IGNORECASE,
        )

    return temiz_sql

# --------------- Güvenli SQL çalıştırma ---------------
def guvenli_sql_calistir(
    sql: str,
) -> list[dict[str, Any]]:
    guvenli_sql = sql_dogrula(sql)

    logger.info(
        "SQL validated | sql=%s",
        guvenli_sql,
    )

    try:
        with get_readonly_connection() as conn:
            conn.timeout = QUERY_TIMEOUT_SECONDS

            cur = conn.cursor()
            cur.execute(guvenli_sql)

            sonuc = rows_to_dicts(cur)

        logger.info(
            "SQL executed successfully | rows=%s | sql=%s",
            len(sonuc),
            guvenli_sql,
        )

        return sonuc[:MAX_ROWS]

    except Exception:
        logger.exception(
            "SQL execution failed | sql=%s",
            guvenli_sql,
        )
        raise

# --------------- SQL sonucunu AI ile özetleme ---------------
def sql_sonucunu_ozetle(
    soru: str,
    sql: str,
    sonuc: list[dict],
) -> str:
    client = genai.Client()

    prompt = f"""
Sen bir toplu taşima operasyon analiz asistanisin.

Kullanici sorusu:

{soru}

Çaliştirilan SQL:

{sql}

SQL sonucu:

{json.dumps(
    sonuc,
    ensure_ascii=False,
    default=str,
)}

Sonucu 2-4 cümleyle Türkçe özetle.

Yalnizca verilen verilere dayan.
"""

    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )

    return response.text or "Sonuç ozetlenemedi."