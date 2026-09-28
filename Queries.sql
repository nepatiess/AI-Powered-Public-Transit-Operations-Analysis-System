-- Hat bazinda toplam sefer sayisi
SELECT r.RouteCode, r.RouteName, COUNT(*) AS TotalTrips
FROM ValidatorTrips v
JOIN Routes_ r ON r.RouteCode = v.RouteCode
GROUP BY r.RouteCode, r.RouteName
ORDER BY TotalTrips DESC;

-- arac bazinda sefer sayisi
SELECT LicensePlate, COUNT(*) AS TripCount
FROM ValidatorTrips
GROUP BY LicensePlate
ORDER BY TripCount DESC;

--gecilmeyen ve atlanan duraklarin tespiti
SELECT v.TripID, v.RouteCode, v.LicensePlate, v.TripDate, hd.StopCode AS MissedStop, hd.StopName
FROM ValidatorTrips v
JOIN RouteStops hd ON hd.RouteCode = v.RouteCode
WHERE NOT EXISTS (
SELECT 1 FROM StopPassages t
WHERE t.TripID = v.TripID AND t.StopCode = hd.StopCode
)
ORDER BY v.TripDate, v.TripID, hd.StopSequence;

-- Konumu gelmeyen araclarin tespiti
WITH OrderedRecords AS (
    SELECT
        LicensePlate,
        RecordedAt,
        LAG(RecordedAt) OVER (PARTITION BY LicensePlate ORDER BY RecordedAt) AS PreviousRecordTime
    FROM VehicleLocations
)
SELECT
    LicensePlate,
    PreviousRecordTime,
    RecordedAt,
    DATEDIFF(MINUTE, PreviousRecordTime, RecordedAt) AS GapMinutes
FROM OrderedRecords
WHERE PreviousRecordTime IS NOT NULL
  AND DATEDIFF(MINUTE, PreviousRecordTime, RecordedAt) > 20   -- threshold: 20 minutes (consistent with the PDF example)
ORDER BY GapMinutes DESC;

-- geciken veya normalden uzun suren seferlerin bulunmasi
SELECT
    v.TripID, v.RouteCode, v.LicensePlate,
    DATEDIFF(MINUTE, v.StartTime, v.EndTime) AS ActualDurationMin,
    h.NormalDuration,
    CASE
        WHEN DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2
            THEN 'ABNORMAL'
        ELSE 'NORMAL'
    END AS Status
FROM ValidatorTrips v
JOIN Routes_ h ON h.RouteCode = v.RouteCode
ORDER BY ActualDurationMin DESC;

-- hat ve durak bazinda yogunlu analzi
SELECT
    hd.RouteCode, t.StopCode, hd.StopName,
    COUNT(*) AS PassageCount
FROM StopPassages t
JOIN ValidatorTrips v ON v.TripID = t.TripID
JOIN RouteStops hd ON hd.RouteCode = v.RouteCode AND hd.StopCode = t.StopCode
GROUP BY hd.RouteCode, t.StopCode, hd.StopName
ORDER BY hd.RouteCode, PassageCount DESC;

-- saatlik ve gunluk problem dagilimlari
SELECT
    DATEPART(HOUR, v.StartTime) AS TimeSlot,
    COUNT(*) AS ProblematicTripCount
FROM ValidatorTrips v
JOIN Routes_ h ON h.RouteCode = v.RouteCode
WHERE DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2
GROUP BY DATEPART(HOUR, v.StartTime)
ORDER BY TimeSlot;

-- en fazla problem ureten arac ve hatlarin siralanmasi
WITH ProblematicTrips AS (
    SELECT
        v.LicensePlate,
        COUNT(*) AS ProblemCount
    FROM ValidatorTrips v
    JOIN Routes_ h ON h.RouteCode = v.RouteCode
    WHERE DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2
    GROUP BY v.LicensePlate
)
SELECT
    LicensePlate,
    ProblemCount,
    RANK() OVER (ORDER BY ProblemCount DESC) AS Rank
FROM ProblematicTrips;

-- once problemli seferleri gecici tabloya sonra uzerinde brden fazla rapor uretmek icin
IF OBJECT_ID('tempdb..#ProblematicTrips') IS NOT NULL
    DROP TABLE #ProblematicTrips;

SELECT
    v.TripID,
    v.RouteCode,
    v.LicensePlate,
    v.TripDate,
    DATEDIFF(MINUTE, v.StartTime, v.EndTime) AS ActualDurationMin,
    h.NormalDuration
INTO #ProblematicTrips
FROM ValidatorTrips v
JOIN Routes_ h ON h.RouteCode = v.RouteCode
WHERE DATEDIFF(MINUTE, v.StartTime, v.EndTime) > h.NormalDuration * 1.2;

-- Report A: Summary by route
SELECT
    RouteCode,
    COUNT(*) AS ProblemCount,
    AVG(ActualDurationMin) AS AverageDuration
FROM #ProblematicTrips
GROUP BY RouteCode;

-- Report B: Summary by date
SELECT
    TripDate,
    COUNT(*) AS ProblemCount
FROM #ProblematicTrips
GROUP BY TripDate;

DROP TABLE #ProblematicTrips;