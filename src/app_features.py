from geometry import haversine_m

class AppFeatures:
    def __init__(self, bus_stop_service, crime_stats_service):
        self.bus_stop_service = bus_stop_service
        self.crime_stats_service = crime_stats_service

    def compute_stop_scores(self, radius_m=250):
        stops = self.bus_stop_service.get_stops()
        crimes = self.crime_stats_service.get_crimes()
        results = []
        for stop in stops:
            score, count = self._score_stop(stop, crimes, radius_m)
            results.append({
                "stop_id": stop.stop_id,
                "name": stop.name,
                "lat": stop.lat,
                "lon": stop.lon,
                "score": score,
                "crime_count": count,
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        for idx, r in enumerate(results, start=1):
            r["rank"] = idx
        return results

    def _score_stop(self, stop, crimes, radius_m):
        score = 0.0
        count = 0
        for c in crimes:
            d = haversine_m(stop.lat, stop.lon, c.lat, c.lon)
            if d <= radius_m:
                count += 1
                score += 1.0 + (radius_m - d) / radius_m
        return score, count

    def heatmap_points(self):
        # Minimal version: each crime = one heat point
        points = []
        for c in self.crime_stats_service.get_crimes():
            points.append({
                "lat": c.lat,
                "lon": c.lon,
                "weight": 1
            })
        return points

    def crimes_near_point(self, lat, lon, radius_m):
        near = []
        for c in self.crime_stats_service.get_crimes():
            d = haversine_m(lat, lon, c.lat, c.lon)
            if d <= radius_m:
                near.append(c)
        return near
