-- Bu sp belirli bir tarih icin tum anomali turlerini tek seferde dondurur. 
CREATE OR ALTER PROCEDURE sp_DailyAnomalyReport
    @TripDate DATE
AS
BEGIN
    SET NOCOUNT ON;

    -- gecilen(missed) duraklar
    SELECT
        'STOP_SKIPPED' AS AnomalyType,
        v.TripID,
        v.RouteCode,
        v.LicensePlate,
        hd.StopCode AS Detail
    FROM ValidatorTrips v
    JOIN RouteStops hd ON hd.RouteCode = v.RouteCode
    WHERE v.TripDate = @TripDate
      AND NOT EXISTS (
          SELECT 1
          FROM StopPassages t
          WHERE t.TripID = v.TripID
            AND t.StopCode = hd.StopCode
      );

    -- normalden uzun sureli seferler
    SELECT
        'ABNORMAL_DURATION' AS AnomalyType,
        v.TripID,
        v.RouteCode,
        v.LicensePlate,
        CAST(DATEDIFF(MINUTE, v.StartTime, v.EndTime) AS VARCHAR(10)) AS Detail
    FROM ValidatorTrips v
    JOIN Routes_ h ON h.RouteCode = v.RouteCode
    WHERE v.TripDate = @TripDate
      AND DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2;
END

EXEC sp_DailyAnomalyReport @TripDate = '2026-08-20';