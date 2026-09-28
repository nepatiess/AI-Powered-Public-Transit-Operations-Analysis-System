CREATE INDEX IX_ValidatorTrips_RouteCode 
	ON ValidatorTrips(RouteCode);

CREATE INDEX IX_ValidatorTrips_LicensePlate 
	ON ValidatorTrips(LicensePlate);

CREATE INDEX IX_StopPassages_TripID 
	ON StopPassages(TripID);

CREATE INDEX IX_VehicleLocations_LicensePlate_RecordedAt 
	ON VehicleLocations(LicensePlate, RecordedAt);