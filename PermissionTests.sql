CREATE LOGIN PublicTransportReader
WITH PASSWORD = '<PASSWORD>';

CREATE USER PublicTransportReader
FOR LOGIN PublicTransportReader;

ALTER ROLE db_datareader
ADD MEMBER PublicTransportReader;

SELECT TOP 5 *
FROM ValidatorTrips;

DELETE FROM ValidatorTrips
WHERE TripID = -999;

USE PublicTransportDB;

EXECUTE AS USER = 'PublicTransportReader';

SELECT
    USER_NAME() AS CurrentDatabaseUser;

DELETE FROM ValidatorTrips
WHERE TripID = -999;

REVERT;

DENY INSERT TO PublicTransportReader;
DENY UPDATE TO PublicTransportReader;
DENY DELETE TO PublicTransportReader;
DENY EXECUTE TO PublicTransportReader;

EXECUTE AS USER = 'PublicTransportReader';

SELECT
    HAS_PERMS_BY_NAME(
        'dbo.ValidatorTrips',
        'OBJECT',
        'SELECT'
    ) AS SelectPermission,

    HAS_PERMS_BY_NAME(
        'dbo.ValidatorTrips',
        'OBJECT',
        'DELETE'
    ) AS DeletePermission;

REVERT;

EXECUTE AS USER = 'PublicTransportReader';

SELECT TOP 5 *
FROM ValidatorTrips;

DELETE FROM ValidatorTrips
WHERE TripID = -999;

REVERT;

SELECT
    name,
    type_desc,
    is_disabled
FROM sys.server_principals
WHERE name = 'PublicTransportReader';

SELECT SERVERPROPERTY('IsIntegratedSecurityOnly') AS WindowsOnly;