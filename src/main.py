from api_client import ApiClient
from busstopdata import BusStopService
from crime_stats import CrimeStatsService
from app_features import AppFeatures
from message_board import MessageBoardService
from web_app import run_server
from app_logger import AppLogger
import threading
import time

REFRESH_INTERVAL_SEC = 3600
RETRY_INTERVAL_SEC = 60


def refresh_loop(bus_stop_service, crime_stats_service,
                 interval_sec=REFRESH_INTERVAL_SEC,
                 retry_sec=RETRY_INTERVAL_SEC,
                 first_delay=None,
                 logger=None):
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
            logger.exception("Refresh error:", e)
            delay = retry_sec


def main():
    app_log = AppLogger()
    app_log.install_exception_hooks()
    api_client = ApiClient()
    bus_stop_service = BusStopService(api_client, logger=app_log.get("busstop"))
    # Fixed window (2025 onward) by default. For a rolling window use
    # CrimeStatsService(recent_days=270), but only once the source file has recent data.
    crime_stats_service = CrimeStatsService(logger=app_log.get("crime"))
    message_board = MessageBoardService()

    # Load data BEFORE starting the server. A failure here is reported but not
    # fatal; the background thread retries after RETRY_INTERVAL_SEC.
    app_log.info("=== LOADING DATA ===")
    initial_ok = True
    try:
        bus_stop_service.load_route_82()
    except Exception as e:
        initial_ok = False
        app_log.exception(f"Bus stop load failed: {e}")
    try:
        crime_stats_service.load_recent()
    except Exception as e:
        initial_ok = False
        app_log.exception("Crime load failed:", e)
    app_log.info(f"Loaded {len(bus_stop_service.get_stops())} stops, "
          f"{len(crime_stats_service.get_crimes())} crimes")

    t = threading.Thread(
        target=refresh_loop,
        args=(bus_stop_service, crime_stats_service),
        kwargs={"logger": app_log.get("refresh"),
            "first_delay": REFRESH_INTERVAL_SEC if initial_ok else RETRY_INTERVAL_SEC},
        daemon=True,
    )
    t.start()

    app_features = AppFeatures(bus_stop_service, crime_stats_service)
    run_server(app_features, message_board, logger=app_log.get("webapp"))


if __name__ == "__main__":
    main()
