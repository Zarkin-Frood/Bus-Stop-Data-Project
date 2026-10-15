import re

STOP_ENDPOINT = ("https://gis.h-gac.com/arcgis/rest/services/"
                 "Open_Data/Transportation/MapServer/17/query")


class BusStop:
    def __init__(self, stop_id, name, lat, lon, routes=None):
        self.stop_id = stop_id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.routes = routes or []


class BusStopService:
    PAGE_SIZE = 1000   # ArcGIS caps results per request, so we page through them
    MAX_PAGES = 50     # safety stop so a misbehaving server can't loop us forever

    def __init__(self, api_client, endpoint=STOP_ENDPOINT):
        self.api_client = api_client
        self.endpoint = endpoint
        self.stops = []
        self.last_load_stats = {}

    def load_route_82(self):
        self.load_route("82")

    def load_route(self, route):
        route = str(route)
        if not re.fullmatch(r"[A-Za-z0-9]+", route):
            raise ValueError(f"Unexpected route value: {route!r}")
        features = self._fetch_all_features(route)
        self.stops = self._parse_geojson(features, route)

    # ---------- fetching ----------

    def _fetch_all_features(self, route):
        features = []
        offset = 0
        for _ in range(self.MAX_PAGES):
            params = {
                # Loose match on the server; _serves_route() does the exact match.
                "where": f"SRVD_RTS LIKE '%{route}%'",
                "outFields": "*",
                "outSR": 4326,
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": self.PAGE_SIZE,
                "f": "geojson",
            }
            data = self.api_client.get_json(self.endpoint, params=params)
            # ArcGIS reports query errors inside a normal HTTP 200 response.
            if "error" in data:
                raise RuntimeError(f"ArcGIS error: {data['error']}")
            page = data.get("features", [])
            if not page:
                break
            features.extend(page)
            offset += len(page)
        else:
            print(f"WARNING: stopped after {self.MAX_PAGES} pages; results may be incomplete")
        return features

    # ---------- parsing ----------

    @staticmethod
    def _serves_route(props, route):
        """True if `route` appears as its own number in SRVD_RTS (82 matches 82, not 182 or 820)."""
        text = str(props.get("SRVD_RTS") or "")
        pattern = r"(?<![0-9A-Za-z])" + re.escape(route) + r"(?![0-9])"
        return re.search(pattern, text) is not None

    def _parse_geojson(self, features, route="82"):
        stats = {"total": 0, "kept": 0, "wrong_route": 0, "no_coords": 0}
        stops = []

        if features:
            # Handy for checking that the field names below match the real layer.
            first_props = features[0].get("properties") or {}
            print("Stop fields:", sorted(first_props.keys()))

        for feature in features:
            stats["total"] += 1
            props = feature.get("properties") or {}
            geom = feature.get("geometry") or {}

            if not self._serves_route(props, route):
                stats["wrong_route"] += 1
                continue

            coords = geom.get("coordinates") or []
            try:
                lon, lat = float(coords[0]), float(coords[1])
            except (IndexError, TypeError, ValueError):
                stats["no_coords"] += 1
                continue

            raw_id = props.get("STOPID") or props.get("OBJECTID") or feature.get("id")
            stops.append(BusStop(
                stop_id=str(raw_id) if raw_id is not None else None,
                name=props.get("STOPNAME", "Unknown"),
                lat=lat,
                lon=lon,
                routes=[props.get("ROUTE")] if props.get("ROUTE") else [],
            ))
            stats["kept"] += 1

        self.last_load_stats = stats
        print(f"Stops: kept {stats['kept']} of {stats['total']} features "
              f"(wrong route: {stats['wrong_route']}, no coordinates: {stats['no_coords']})")
        return stops

    def get_stops(self):
        return list(self.stops)
