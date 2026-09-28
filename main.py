from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel, Field

from database import get_connection, rows_to_dicts
from ai_summary import ozet_uret, soru_yanitla

from nl_sql import (
    sql_uret,
    guvenli_sql_calistir,
    sql_sonucunu_ozetle,
)

app = FastAPI(title="Ulasim Operasyon Analiz API")

class NaturalLanguageQuery(BaseModel):
    soru: str = Field(
        min_length=3,
        max_length=500,
    )

def atlanan_duraklari_getir(route_code: Optional[str] = None, plate: Optional[str] = None):
    sql = """
        SELECT v.TripID, v.RouteCode, v.LicensePlate, v.TripDate,
               hd.StopCode AS StopCode, hd.StopName
        FROM ValidatorTrips v
        JOIN RouteStops hd ON hd.RouteCode = v.RouteCode
        WHERE NOT EXISTS (
            SELECT 1 FROM StopPassages t
            WHERE t.TripID = v.TripID AND t.StopCode = hd.StopCode
        )
    """
    params = []
    if route_code:
        sql += " AND v.RouteCode = ?"
        params.append(route_code)
    if plate:
        sql += " AND v.LicensePlate = ?"
        params.append(plate)
    sql += " ORDER BY v.TripDate, v.TripID"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        satirlar = rows_to_dicts(cur)

    return [
        {
            "seferId": s["TripID"], "hatKodu": s["RouteCode"], "plaka": s["LicensePlate"],
            "tarih": s["TripDate"], "tur": "DURAK_ATLAMA",
            "detay": f"{s['StopCode']} duragi ({s['StopName']}) atlandi",
        }
        for s in satirlar
    ]

def anormal_sureleri_getir(route_code: Optional[str] = None, plate: Optional[str] = None):
    sql = """
        SELECT v.TripID, v.RouteCode, v.LicensePlate, v.TripDate,
               DATEDIFF(MINUTE, v.StartTime, v.EndTime) AS DurationMinutes,
               h.NormalDuration
        FROM ValidatorTrips v
        JOIN Routes_ h ON h.RouteCode = v.RouteCode
        WHERE DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2
    """
    params = []
    if route_code:
        sql += " AND v.RouteCode = ?"
        params.append(route_code)
    if plate:
        sql += " AND v.LicensePlate = ?"
        params.append(plate)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        satirlar = rows_to_dicts(cur)

    return [
        {
            "seferId": s["TripID"], "hatKodu": s["RouteCode"], "plaka": s["LicensePlate"],
            "tarih": s["TripDate"], "tur": "ANORMAL_SURE",
            "detay": f"{s['DurationMinutes']} dk sürdü (normal: {s['NormalDuration']} dk)",
        }
        for s in satirlar
    ]

def gps_bosluklarini_getir(plate: Optional[str] = None):
    sql = """
        WITH Sirali AS (
            SELECT LicensePlate, RecordedAt,
                   LAG(RecordedAt) OVER (PARTITION BY LicensePlate ORDER BY RecordedAt) AS OncekiKayit
            FROM VehicleLocations
        )
        SELECT LicensePlate, OncekiKayit, RecordedAt,
               DATEDIFF(MINUTE, OncekiKayit, RecordedAt) AS GapMinutes
        FROM Sirali
        WHERE OncekiKayit IS NOT NULL
          AND DATEDIFF(MINUTE, OncekiKayit, RecordedAt) > 20
    """
    params = []
    if plate:
        sql += " AND LicensePlate = ?"
        params.append(plate)

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        satirlar = rows_to_dicts(cur)

    return [
        {
            "seferId": None, "hatKodu": None, "plaka": s["LicensePlate"],
            "tarih": s["RecordedAt"][:10] if s["RecordedAt"] else None, "tur": "GPS_PROBLEMI",
            "detay": f"{s['OncekiKayit']} - {s['RecordedAt']} arasi {s['GapMinutes']} dk konum gelmedi",
        }
        for s in satirlar
    ]

def son_gps_gondermeyen_araclari_getir(plate: Optional[str] = None):
    sql = """
        WITH LastLocations AS (
            SELECT
                LicensePlate,
                MAX(RecordedAt) AS LastRecordedAt
            FROM VehicleLocations
            GROUP BY LicensePlate
        ),
        ReferenceTime AS (
            SELECT
                MAX(RecordedAt) AS CurrentDataTime
            FROM VehicleLocations
        )
        SELECT
            l.LicensePlate,
            l.LastRecordedAt,
            DATEDIFF(
                MINUTE,
                l.LastRecordedAt,
                r.CurrentDataTime
            ) AS MinutesSinceLastLocation
        FROM LastLocations l
        CROSS JOIN ReferenceTime r
        WHERE DATEDIFF(
            MINUTE,
            l.LastRecordedAt,
            r.CurrentDataTime
        ) > 20
    """

    params = []

    if plate:
        sql += " AND l.LicensePlate = ?"
        params.append(plate)

    sql += " ORDER BY MinutesSinceLastLocation DESC"

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        satirlar = rows_to_dicts(cur)

    return [
        {
            "seferId": None,
            "hatKodu": None,
            "plaka": s["LicensePlate"],
            "tarih": s["LastRecordedAt"],
            "tur": "GPS_SESSIZLIK",
            "detay": (
                f"Son GPS kaydi "
                f"{s['MinutesSinceLastLocation']} dakika once alindi"
            ),
        }
        for s in satirlar
    ]

def tum_anomalileri_getir(
    route_code: Optional[str] = None,
    plate: Optional[str] = None
):
    return (
        atlanan_duraklari_getir(route_code, plate)
        + anormal_sureleri_getir(route_code, plate)
        + gps_bosluklarini_getir(plate)
        + son_gps_gondermeyen_araclari_getir(plate)
    )

def hat_ozet_verisi_olustur(route_code: str) -> dict:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ValidatorTrips WHERE RouteCode = ?", [route_code])
        toplam_sefer = cur.fetchone()[0]

    anomaliler = tum_anomalileri_getir(route_code=route_code)
    problemli_sefer_id = {a["seferId"] for a in anomaliler if a["seferId"] is not None}
    gps_sayisi = sum(1 for a in anomaliler if a["tur"] == "GPS_PROBLEMI")

    durak_sayaci = {}
    for a in anomaliler:
        if a["tur"] == "DURAK_ATLAMA":
            durak_kodu = a["detay"].split()[0]
            durak_sayaci[durak_kodu] = durak_sayaci.get(durak_kodu, 0) + 1
    en_cok_atlanan = max(durak_sayaci, key=durak_sayaci.get) if durak_sayaci else None

    return {
        "route": route_code,
        "totalTrips": toplam_sefer,
        "problemTrips": len(problemli_sefer_id),
        "mostSkippedStop": en_cok_atlanan,
        "gpsProblems": gps_sayisi,
    }

# --------------- ENDPOINT'LER ---------------
@app.get("/")
def root():
    return {"mesaj": "Ulasim Operasyon Analiz API calisiyor (gercek DB). /docs adresine bak."}

@app.get("/api/anomalies")
def anomalileri_listele(tur: Optional[str] = None):
    try:
        anomaliler = tum_anomalileri_getir()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")
    if tur:
        anomaliler = [a for a in anomaliler if a["tur"] == tur]
    return {"toplam": len(anomaliler), "anomaliler": anomaliler}

@app.get("/api/routes/{routeCode}/problems")
def hat_problemleri(routeCode: str):
    try:
        sonuc = tum_anomalileri_getir(route_code=routeCode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")
    if not sonuc:
        raise HTTPException(status_code=404, detail=f"{routeCode} hattinda kayitli problem yok")
    return {"hatKodu": routeCode, "toplamProblem": len(sonuc), "problemler": sonuc}

@app.get("/api/vehicles/{plate}")
def arac_bilgisi(plate: str):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) AS ToplamSefer FROM ValidatorTrips WHERE LicensePlate = ?",
                [plate],
            )
            toplam_sefer = cur.fetchone()[0]

            cur.execute(
                "SELECT TOP 1 RouteCode, TripID FROM ValidatorTrips "
                "WHERE LicensePlate = ? ORDER BY TripDate DESC, StartTime DESC",
                [plate],
            )
            son = cur.fetchone()

        anomaliler = tum_anomalileri_getir(plate=plate)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")

    if toplam_sefer == 0:
        raise HTTPException(status_code=404, detail="Plaka bulunamadı")

    return {
        "plaka": plate,
        "sonHat": son.RouteCode if son else None,
        "sonSeferId": son.TripID if son else None,
        "toplamSefer": toplam_sefer,
        "anomaliler": anomaliler,
    }

@app.get("/api/routes/{routeCode}/summary")
def hat_ai_ozeti(routeCode: str):
    try:
        veri = hat_ozet_verisi_olustur(routeCode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")

    if veri["totalTrips"] == 0:
        raise HTTPException(status_code=404, detail=f"{routeCode} hattinda için sefer kaydi yok")

    try:
        ozet_metni = ozet_uret(veri)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI özet hatasi: {e}")

    return {"veri": veri, "ozet": ozet_metni}

@app.get("/api/routes")
def hatlari_listele():
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT RouteCode, RouteName FROM Routes_ ORDER BY RouteCode")
            return rows_to_dicts(cur)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")

@app.get("/api/routes/{routeCode}/ask")
def hat_hakkinda_soru_sor(routeCode: str, soru: str):
    try:
        veri = hat_ozet_verisi_olustur(routeCode)
        anomaliler = tum_anomalileri_getir(route_code=routeCode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")

    veri_ve_detay = {**veri, "anomaliler": anomaliler}

    try:
        cevap = soru_yanitla(veri_ve_detay, soru)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI hatasi: {e}")

    return {"soru": soru, "cevap": cevap}

@app.post("/api/query")
def natural_language_query(request: NaturalLanguageQuery):
    try:
        sql = sql_uret(request.soru)

        sonuc = guvenli_sql_calistir(sql)

        ozet = sql_sonucunu_ozetle(
            request.soru,
            sql,
            sonuc,
        )

        return {
            "soru": request.soru,
            "sql": sql,
            "kayitSayisi": len(sonuc),
            "sonuc": sonuc,
            "ozet": ozet,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sorgu calistirilamadi: {e}",
        )

@app.post("/api/query")
def natural_language_query(
    request: NaturalLanguageQuery
):
    try:
        sql = sql_uret(request.soru)

        sonuc = guvenli_sql_calistir(sql)

        ozet = sql_sonucunu_ozetle(
            request.soru,
            sql,
            sonuc,
        )

        return {
            "soru": request.soru,
            "sql": sql,
            "kayitSayisi": len(sonuc),
            "sonuc": sonuc,
            "ozet": ozet,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sorgu calistirilamadi: {e}",
        )
    
@app.get("/api/stops/{stopId}")
def durak_bilgisi(stopId: str):
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT hd.RouteCode, hd.StopName
                FROM RouteStops hd WHERE hd.StopCode = ?
                """,
                [stopId],
            )
            durak = cur.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabani hatasi: {e}")

    if not durak:
        raise HTTPException(status_code=404, detail="Durak bulunamadi")

    atlanan = [a for a in atlanan_duraklari_getir() if a["detay"].startswith(stopId)]

    return {
        "durakKodu": stopId,
        "durakAdi": durak.StopName,
        "hatKodu": durak.RouteCode,
        "atlanmaSayisi": len(atlanan),
    }