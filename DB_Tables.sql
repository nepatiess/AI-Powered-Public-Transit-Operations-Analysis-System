CREATE DATABASE PublicTransportDB;

USE PublicTransportDB;

CREATE TABLE Routes_(
    RouteCode VARCHAR(10) NOT NULL PRIMARY KEY,
    RouteName VARCHAR(100) NOT NULL,
    NormalDuration INT NOT NULL
);

CREATE TABLE RouteStops(
    RouteCode VARCHAR(10) NOT NULL,
    StopCode VARCHAR(10) NOT NULL,
    StopName VARCHAR(100) NOT NULL,
    StopSequence INT NOT NULL,

    CONSTRAINT PK_RouteStops PRIMARY KEY (RouteCode, StopCode),

    CONSTRAINT FK_RouteStops_Routes FOREIGN KEY (RouteCode) REFERENCES Routes_(RouteCode)
);

CREATE TABLE ValidatorTrips(
    TripID INT IDENTITY(1,1) PRIMARY KEY,
    RouteCode VARCHAR(10) NOT NULL,
    LicensePlate VARCHAR(15) NOT NULL,
    TripDate DATE NOT NULL,
    StartTime DATETIME NOT NULL,
    EndTime DATETIME NULL,

    CONSTRAINT FK_ValidatorTrips_Routes FOREIGN KEY (RouteCode) REFERENCES Routes_(RouteCode)
);

CREATE TABLE StopPassages(
    ID INT IDENTITY(1,1) PRIMARY KEY,
    TripID INT NOT NULL,
    StopCode VARCHAR(10) NOT NULL,
    PassageTime DATETIME NOT NULL,

    CONSTRAINT FK_StopPassages_ValidatorTrips FOREIGN KEY (TripID) REFERENCES ValidatorTrips(TripID)
);

CREATE TABLE VehicleLocations(
    ID INT IDENTITY(1,1) PRIMARY KEY,
    LicensePlate VARCHAR(15) NOT NULL,
    RecordedAt DATETIME NOT NULL,
    Latitude DECIMAL(9,6) NOT NULL,
    Longitude DECIMAL(9,6) NOT NULL,
    SpeedKmh INT NULL
);