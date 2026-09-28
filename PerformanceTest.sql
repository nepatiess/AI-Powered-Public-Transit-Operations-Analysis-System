SET STATISTICS IO ON;
SET STATISTICS TIME ON;

CREATE NONCLUSTERED INDEX IX_VehicleLocations_LicensePlate_RecordedAt
ON VehicleLocations (LicensePlate, RecordedAt)
INCLUDE (Latitude, Longitude, SpeedKmh);

SELECT
    ID,
    LicensePlate,
    RecordedAt,
    Latitude,
    Longitude,
    SpeedKmh
FROM VehicleLocations
WHERE LicensePlate = '34 JKL 654'
ORDER BY RecordedAt;

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;

DROP INDEX IX_VehicleLocations_LicensePlate_RecordedAt
ON VehicleLocations;