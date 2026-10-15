import csv
import os
import time
import urllib.request
from datetime import date, datetime, timedelta
from io import StringIO

NIBRS_2025_URL = "https://www.houstontx.gov/police/cs/xls/NIBRSPublicView2025.csv"

# Loose bounding box around Houston. Anything outside it (including 0,0) is bad data.
LAT_RANGE = (29.0, 30.6)
LON_RANGE = (-96.2, -94.6)


class CrimeRecord:
    def __init__(self, incident_id, occurred_at, nibrs_class,
                 nibrs_description, offense_count, beat,
                 premise, street, city, zip_code, lon, lat):
        self.incident_id = incident_id
        self.occurred_at = occurred_at
        self.nibrs_class = nibrs_class
        self.nibrs_description = nibrs_description
        self.offense_count = offense_count
        self.beat = beat
        self.premise = premise
        self.street = street
        self.city = city
        self.zip_code = zip_code
        self.lon = lon
        self.lat = lat


class CrimeStatsService:
    def __init__(self, start_date=date(2025, 1, 1), end_date=None,
                 recent_days=None, url=NIBRS_2025_URL,
                 cache_path="data/nibrs_cache.csv", cache_max_age_hours=24, 
                 logger=None):
        """
        By default the window is fixed: start_date through end_date (inclusive,
        or open-ended if end_date is None).

        Pass recent_days=N for a rolling window instead (overrides start_date).
        Only use that if the file at `url` actually contains recent data, or
        every row will fall outside the window.
        """
        self.start_date = start_date
        self.end_date = end_date
        self.recent_days = recent_days
        self.url = url
        self.cache_path = cache_path
        self.cache_max_age_hours = cache_max_age_hours
        self.crimes = []
        self.last_load_stats = {}
        self.logger = logger

    # ---------- loading ----------

    def load_recent(self):
        text = self._fetch_text()
        reader = csv.DictReader(StringIO(text))
        self.crimes = self._parse_rows(reader)

        s = self.last_load_stats
        self.logger.info(f"Crimes: kept {s['kept']} of {s['total']} rows "
              f"(outside window: {s['outside_window']}, bad date: {s['bad_date']}, "
              f"bad coords: {s['bad_coords']}, other: {s['other']})")
        if s["kept"] == 0 and s["total"] > 0:
            self.logger.warning("WARNING: no crimes kept. CSV columns were:", reader.fieldnames)

    def _fetch_text(self):
        """Return the CSV text, using a disk cache so we don't re-download every run."""
        if self._cache_is_fresh():
            self.logger.info("Using cached crime data:", self.cache_path)
            return self._read_cache()
        try:
            with urllib.request.urlopen(self.url, timeout=60) as resp:
                raw = resp.read()
        except Exception as e:
            if os.path.exists(self.cache_path):
                self.logger.exception(f"Crime download failed ({e}); using stale cache {self.cache_path}")
                return self._read_cache()
            raise
        self._write_cache(raw)
        return raw.decode("utf-8-sig", errors="ignore")

    def _cache_is_fresh(self):
        if not os.path.exists(self.cache_path):
            return False
        age_hours = (time.time() - os.path.getmtime(self.cache_path)) / 3600
        return age_hours < self.cache_max_age_hours

    def _read_cache(self):
        with open(self.cache_path, "rb") as f:
            return f.read().decode("utf-8-sig", errors="ignore")

    def _write_cache(self, raw):
        folder = os.path.dirname(self.cache_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp_path = self.cache_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(raw)
        os.replace(tmp_path, self.cache_path)  # atomic, so no half-written cache

    # ---------- parsing ----------

    def _window(self):
        if self.recent_days is not None:
            start = datetime.now() - timedelta(days=self.recent_days)
        else:
            start = datetime(self.start_date.year, self.start_date.month, self.start_date.day)
        end = None
        if self.end_date is not None:
            end = datetime(self.end_date.year, self.end_date.month, self.end_date.day) + timedelta(days=1)
        return start, end

    def _parse_rows(self, rows):
        start, end = self._window()
        stats = {"total": 0, "kept": 0, "outside_window": 0,
                 "bad_date": 0, "bad_coords": 0, "other": 0}
        crimes = []

        for row in rows:
            stats["total"] += 1

            try:
                occurred_at = self._parse_datetime(row)
            except (KeyError, ValueError, TypeError, AttributeError):
                stats["bad_date"] += 1
                continue

            if occurred_at < start or (end is not None and occurred_at >= end):
                stats["outside_window"] += 1
                continue

            try:
                lat = float(row["Map Latitude"])
                lon = float(row["Map Longitude"])
            except (KeyError, ValueError, TypeError):
                stats["bad_coords"] += 1
                continue
            if not self._coords_ok(lat, lon):
                stats["bad_coords"] += 1
                continue

            try:
                crimes.append(self._build_record(row, occurred_at, lat, lon))
            except (KeyError, ValueError, TypeError, AttributeError):
                stats["other"] += 1
                continue
            stats["kept"] += 1

        self.last_load_stats = stats
        return crimes

    @staticmethod
    def _parse_datetime(row):
        # Date looks like "1/1/2025"; hour like "0". A blank hour counts as midnight.
        base = datetime.strptime(row["Occurrence Date"].strip(), "%m/%d/%Y")
        hour_raw = (row.get("Occurrence Hour") or "").strip()
        hour = int(hour_raw) if hour_raw else 0
        return base.replace(hour=min(max(hour, 0), 23))

    @staticmethod
    def _coords_ok(lat, lon):
        return (LAT_RANGE[0] <= lat <= LAT_RANGE[1]
                and LON_RANGE[0] <= lon <= LON_RANGE[1])

    @staticmethod
    def _build_record(row, occurred_at, lat, lon):
        street_parts = (
            (row.get(key) or "").strip()
            for key in ("Street Number", "Street Name", "Street Type", "Street Suffix")
        )
        return CrimeRecord(
            incident_id=row["Incident"],
            occurred_at=occurred_at,
            nibrs_class=row["NIBRS Class"],
            nibrs_description=row["NIBRS Description"],
            offense_count=int(row.get("Offense Count") or 1),
            beat=row["Beat"],
            premise=row["Premise"],
            street=" ".join(p for p in street_parts if p),
            city=row["City"],
            zip_code=row["ZIP Code"],
            lon=lon,
            lat=lat,
        )

    def get_crimes(self):
        return list(self.crimes)
