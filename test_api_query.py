from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

def test_query_success(monkeypatch):
    monkeypatch.setattr(
        main,
        "sql_uret",
        lambda soru: (
            "SELECT TOP 5 LicensePlate, COUNT(TripID) AS TotalTrips "
            "FROM ValidatorTrips "
            "GROUP BY LicensePlate "
            "ORDER BY TotalTrips DESC"
        ),
    )

    monkeypatch.setattr(
        main,
        "guvenli_sql_calistir",
        lambda sql: [
            {
                "LicensePlate": "34 EEE 005",
                "TotalTrips": 44,
            },
            {
                "LicensePlate": "34 DDD 004",
                "TotalTrips": 25,
            },
        ],
    )

    monkeypatch.setattr(
        main,
        "sql_sonucunu_ozetle",
        lambda soru, sql, sonuc: (
            "En fazla sefer yapan arac 34 EEE 005 plakali aractir."
        ),
    )

    response = client.post(
        "/api/query",
        json={
            "soru": "En fazla sefer yapan 5 araci goster."
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["soru"] == (
        "En fazla sefer yapan 5 araci goster."
    )
    assert data["kayitSayisi"] == 2
    assert len(data["sonuc"]) == 2
    assert "ValidatorTrips" in data["sql"]
    assert data["ozet"]

def test_query_validation_error(monkeypatch):
    def fake_sql_calistir(sql):
        raise ValueError(
            "İzin verilmeyen kolon kullanimi: Salary"
        )

    monkeypatch.setattr(
        main,
        "sql_uret",
        lambda soru: (
            "SELECT TripID, Salary FROM ValidatorTrips"
        ),
    )

    monkeypatch.setattr(
        main,
        "guvenli_sql_calistir",
        fake_sql_calistir,
    )

    response = client.post(
        "/api/query",
        json={
            "soru": "Salary kolonunu göster."
        },
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "İzin verilmeyen kolon kullanimi: Salary"
    )

def test_query_too_short():
    response = client.post(
        "/api/query",
        json={
            "soru": "a"
        },
    )

    assert response.status_code == 422

def test_query_empty():
    response = client.post(
        "/api/query",
        json={
            "soru": ""
        },
    )

    assert response.status_code == 422

def test_query_internal_error(monkeypatch):
    def fake_sql_uret(soru):
        raise RuntimeError(
            "Gemini servisine ulasilamadi."
        )

    monkeypatch.setattr(
        main,
        "sql_uret",
        fake_sql_uret,
    )

    response = client.post(
        "/api/query",
        json={
            "soru": "En fazla sefer yapan araci goster."
        },
    )

    assert response.status_code == 500

    assert (
        "Sorgu çaliştirilamadi"
        in response.json()["detail"]
    )