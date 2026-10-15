from api_client import ApiClient
from busstopdata import BusStopService
from crime_stats import CrimeStatsService
from app_features import AppFeatures
from message_board import MessageBoardService
from web_app import run_server
import threading
import time

REFRESH_INTERVAL_SEC = 3600
RETRY_INTERVAL_SEC = 60


def refresh_loop(bus_stop_service, crime_stats_service,
                 interval_sec=REFRESH_INTERVAL_SEC,
                 retry_sec=RETRY_INTERVAL_SEC,
                 first_delay=None):
    # Sleep first: main() has already done the initial load, so reloading
    # immediately would just download everything twice.
    delay = interval_sec if first_delay is None else first_delay
    while True:
        time.sleep(delay)
        try:
            bus_stop_service.load_route_82()
            crime_stats_service.load_recent()
            delay = interval_sec
        except Exception as e:
            print("Refresh error:", e)
            delay = retry_sec


def main():
    api_client = ApiClient()
    bus_stop_service = BusStopService(api_client)
    # Fixed window (2025 onward) by default. For a rolling window use
    # CrimeStatsService(recent_days=270), but only once the source file has recent data.
    crime_stats_service = CrimeStatsService()
    message_board = MessageBoardService()

    # Load data BEFORE starting the server. A failure here is reported but not
    # fatal; the background thread retries after RETRY_INTERVAL_SEC.
    print("=== LOADING DATA ===")
    initial_ok = True
    try:
        bus_stop_service.load_route_82()
    except Exception as e:
        initial_ok = False
        print("Bus stop load failed:", e)
    try:
        crime_stats_service.load_recent()
    except Exception as e:
        initial_ok = False
        print("Crime load failed:", e)
    print(f"Loaded {len(bus_stop_service.get_stops())} stops, "
          f"{len(crime_stats_service.get_crimes())} crimes")

    t = threading.Thread(
        target=refresh_loop,
        args=(bus_stop_service, crime_stats_service),
        kwargs={"first_delay": REFRESH_INTERVAL_SEC if initial_ok else RETRY_INTERVAL_SEC},
        daemon=True,
    )
    t.start()

    app_features = AppFeatures(bus_stop_service, crime_stats_service)
    run_server(app_features, message_board)


if __name__ == "__main__":
    main()
