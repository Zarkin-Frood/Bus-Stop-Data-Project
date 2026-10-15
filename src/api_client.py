import json
import csv
import urllib.request
import urllib.parse
from io import StringIO
import ssl

class ApiClient:
    def __init__(self, timeout=10):
        self.timeout = timeout

    def get_json(self, url, params=None):
        if params:
            qs = urllib.parse.urlencode(params)
            url = f"{url}?{qs}"
        ssl._create_default_https_context = ssl._create_unverified_context
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            data = resp.read().decode("utf-8")
        return json.loads(data)

    def get_csv_rows(self, url):
        ssl._create_default_https_context = ssl._create_unverified_context
        with urllib.request.urlopen(url, timeout=self.timeout) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
        reader = csv.DictReader(StringIO(data))
        return list(reader)
