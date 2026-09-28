import pytest
from nl_sql import sql_dogrula

def test_valid_select():
    sql = sql_dogrula(
        "SELECT TripID, RouteCode, LicensePlate FROM ValidatorTrips"
    )

    assert "SELECT TOP 100" in sql
    assert "ValidatorTrips" in sql

def test_select_star_blocked():
    with pytest.raises(
        ValueError,
        match=r"SELECT \* kullanimina izin verilmez",
    ):
        sql_dogrula(
            "SELECT * FROM ValidatorTrips"
        )

def test_invalid_column_blocked():
    with pytest.raises(
        ValueError,
        match="İzin verilmeyen kolon kullanimi",
    ):
        sql_dogrula(
            "SELECT TripID, Salary FROM ValidatorTrips"
        )

def test_invalid_table_blocked():
    with pytest.raises(
        ValueError,
        match="İzin verilmeyen tablo kullanimi",
    ):
        sql_dogrula(
            "SELECT UserName FROM Users"
        )

def test_delete_blocked():
    with pytest.raises(ValueError):
        sql_dogrula(
            "DELETE FROM ValidatorTrips"
        )

def test_update_blocked():
    with pytest.raises(ValueError):
        sql_dogrula(
            "UPDATE ValidatorTrips "
            "SET RouteCode = 'TEST'"
        )

def test_multiple_statements_blocked():
    with pytest.raises(
        ValueError,
        match="Birden fazla SQL komutuna izin verilmez",
    ):
        sql_dogrula(
            "SELECT TripID FROM ValidatorTrips; "
            "SELECT RouteCode FROM Routes_;"
        )

def test_allowed_join():
    sql = sql_dogrula(
        """
        SELECT
            r.RouteName,
            COUNT(t.TripID) AS TotalTrips
        FROM Routes_ r
        LEFT JOIN ValidatorTrips t
            ON r.RouteCode = t.RouteCode
        GROUP BY r.RouteName
        """
    )

    assert "Routes_" in sql
    assert "ValidatorTrips" in sql

def test_existing_top_preserved():
    sql = sql_dogrula(
        """
        SELECT TOP 5
            LicensePlate,
            COUNT(TripID) AS TotalTrips
        FROM ValidatorTrips
        GROUP BY LicensePlate
        ORDER BY TotalTrips DESC
        """
    )

    assert "TOP 5" in sql
    assert "TOP 100" not in sql

def test_top_over_limit_is_reduced():
    sql = sql_dogrula(
        "SELECT TOP 1000 TripID FROM ValidatorTrips"
    )

    assert "TOP 100" in sql
    assert "TOP 1000" not in sql

def test_top_5_is_preserved():
    sql = sql_dogrula(
        "SELECT TOP 5 TripID FROM ValidatorTrips"
    )

    assert "TOP 5" in sql