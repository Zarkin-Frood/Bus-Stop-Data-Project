from api_client import ApiClient
from busstopdata import BusStopService
from crime_stats import CrimeStatsService
from app_features import AppFeatures
from message_board import MessageBoardService
from web_app import run_server
import threading
import time

def refresh_loop(bus_stop_service, crime_stats_service, interval_sec=3600):
    while True:
        try:
            bus_stop_service.load_route_82()
            crime_stats_service.load_recent()
        except Exception as e:
            print("Refresh error:", e)
        time.sleep(interval_sec)

def main():
    api_client = ApiClient()
    bus_stop_service = BusStopService(api_client)
    crime_stats_service = CrimeStatsService()
    message_board = MessageBoardService()

    # Initial load
    # bus_stop_service.load_route_82()
    # crime_stats_service.load_recent()
    
     # CRITICAL: Load data BEFORE starting server
    print("=== LOADING DATA ===")
    bus_stop_service.load_route_82()
    print(f"Loaded {len(bus_stop_service.get_stops())} stops")
    
    crime_stats_service.load_recent()
    print(f"Loaded {len(crime_stats_service.get_crimes())} crimes")

    # Background refresh
    t = threading.Thread(
        target=refresh_loop,
        args=(bus_stop_service, crime_stats_service),
        daemon=True
    )
    t.start()

    app_features = AppFeatures(bus_stop_service, crime_stats_service)
    run_server(app_features, message_board)

if __name__ == "__main__":
    main()
