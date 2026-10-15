import csv
from io import StringIO
import urllib.request
from datetime import datetime, timedelta

NIBRS_2025_URL = "https://www.houstontx.gov/police/cs/xls/NIBRSPublicView2025.csv"

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
    def __init__(self, recent_days=270):
        self.recent_days = recent_days
        self.crimes = []

    def load_recent(self):
        rows = self._fetch_rows()
        self.crimes = self._parse_rows(rows)

    def _fetch_rows(self):
        with urllib.request.urlopen(NIBRS_2025_URL, timeout=20) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(StringIO(data))
        return list(reader)

    def _parse_rows(self, rows):
        cutoff = datetime.utcnow() - timedelta(days=self.recent_days)
        crimes = []
        for row in rows:
            try:
                incident_id = row["Incident"]
                date_str = row["Occurrence Date"]     # e.g. "1/1/2025"
                hour_str = row["Occurrence Hour"]    # e.g. "0"
                # Build datetime
                base_date = datetime.strptime(date_str, "%m/%d/%Y")
                hour = int(hour_str)
                occurred_at = base_date.replace(hour=hour)

                lon = float(row["Map Longitude"])
                lat = float(row["Map Latitude"])

                if occurred_at < cutoff:
                    continue

                rec = CrimeRecord(
                    incident_id=incident_id,
                    occurred_at=occurred_at,
                    nibrs_class=row["NIBRS Class"],
                    nibrs_description=row["NIBRS Description"],
                    offense_count=int(row["Offense Count"]),
                    beat=row["Beat"],
                    premise=row["Premise"],
                    street=" ".join([
                        row["Street Number"],
                        row["Street Name"],
                        row["Street Type"],
                        row["Street Suffix"],
                    ]).strip(),
                    city=row["City"],
                    zip_code=row["ZIP Code"],
                    lon=lon,
                    lat=lat,
                )
                crimes.append(rec)
            except Exception:
                # Skip malformed rows
                continue
        return crimes

    def get_crimes(self):
        return list(self.crimes)
