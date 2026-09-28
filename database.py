import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

SERVER = r"DESKTOP-KKSU8DQ\SQLEXPRESS"
DATABASE = "PublicTransportDB"
DRIVER = "{ODBC Driver 17 for SQL Server}"

CONNECTION_STRING = (
    f"DRIVER={DRIVER};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def get_connection():
    return pyodbc.connect(CONNECTION_STRING)

def get_readonly_connection():
    user = os.getenv("NL_SQL_DB_USER")
    password = os.getenv("NL_SQL_DB_PASSWORD")

    if not user or not password:
        raise RuntimeError(
            "Read-only veritabanı kullanıcı bilgileri tanımlı değil."
        )

    readonly_connection_string = (
        f"DRIVER={DRIVER};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    return pyodbc.connect(
        readonly_connection_string,
        timeout=10,
    )

def rows_to_dicts(cursor):
    columns = [col[0] for col in cursor.description]
    sonuc = []

    for row in cursor.fetchall():
        satir = {}
        for col, deger in zip(columns, row):
            if hasattr(deger, "isoformat"):
                deger = deger.isoformat()
            satir[col] = deger
        sonuc.append(satir)
    return sonuc