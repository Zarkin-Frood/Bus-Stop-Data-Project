class BusStop:
    def __init__(self, stop_id, name, lat, lon, routes=None):
        self.stop_id = stop_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.routes = routes or []

class BusStopService:
    def __init__(self, api_client):
        self.api_client = api_client
        self.stops = []
        self.bus_stop_api= "https://gis.h-gac.com/arcgis/rest/services/Open_Data/Transportation/MapServer/17/query"

    def load_route_82(self):
        # TODO: plug in the real ArcGIS endpoint + params for route 82
        params = {
            "where": "SRVD_RTS LIKE '%82%'",
            "outFields": "*",
            "f": "geojson",
        }
        data = self.api_client.get_json(self.bus_stop_api, params=params)
        self.stops = self._parse_geojson(data)

    def _parse_geojson(self, data):
        stops = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates") or [None, None]
            lon, lat = coords[0], coords[1]
            stop = BusStop(
                stop_id=props.get("STOPID") or props.get("OBJECTID"),
                name=props.get("STOPNAME", "Unknown"),
                lat=lat,
                lon=lon,
                routes=[props.get("ROUTE")] if props.get("ROUTE") else [],
            )
            stops.append(stop)
        return stops

    def _parse_features(self, data):
        stops = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            geom = feature.get("geometry", {})
            lat = geom.get("y")
            lon = geom.get("x")
            stop = BusStop(
                stop_id=attrs.get("STOPID") or attrs.get("OBJECTID"),
                name=attrs.get("STOPNAME", "Unknown"),
                lat=lat,
                lon=lon,
                routes=[attrs.get("ROUTE")] if attrs.get("ROUTE") else [],
            )
            stops.append(stop)
        return stops

    def get_stops(self):
        return list(self.stops)
