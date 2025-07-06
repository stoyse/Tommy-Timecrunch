import requests
import os
from datetime import datetime

def get_flight_info(flight_number, departure_day=None):
    """
    Query AeroDataBox API for flight info. Returns dict with route and airport info, or None if not found.
    Loads API credentials from credentials.json if available, else from environment variable AERODATABOX_API_KEY.
    """
    import json
    api_key = None
    api_host = 'aerodatabox.p.rapidapi.com'
    credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
                # Prefer RapidAPI key if present, else use clientId/clientSecret for OAuth (not implemented here)
                api_key = creds.get('apiKey')
                if not api_key and creds.get('clientId') and creds.get('clientSecret'):
                    # If you want to implement OAuth, do it here. For now, just print a warning.
                    print("AeroDataBox clientId/clientSecret found, but only RapidAPI key supported in this function.")
        except Exception as e:
            print(f"Error loading AeroDataBox credentials: {e}")
    if not api_key:
        api_key = os.environ.get('AERODATABOX_API_KEY')
    if not api_key:
        print("AeroDataBox API key missing. Add 'apiKey' to credentials.json or set AERODATABOX_API_KEY.")
        return None
    headers = {
        'X-RapidAPI-Key': api_key,
        'X-RapidAPI-Host': api_host
    }
    # Format date as YYYY-MM-DD
    if departure_day:
        try:
            date = datetime.strptime(departure_day, "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            date = departure_day  # fallback, let API handle
    else:
        date = datetime.now().strftime("%Y-%m-%d")
    # Remove spaces from flight number
    flight_number = flight_number.replace(' ', '')
    url = f"https://aerodatabox.p.rapidapi.com/flights/number/{flight_number}/{date}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"AeroDataBox API error: {resp.status_code} {resp.text}")
            return None
        data = resp.json()
        # Try both 'departures' and 'arrivals' keys
        if 'departures' in data and data['departures']:
            return data['departures'][0]
        if 'arrivals' in data and data['arrivals']:
            return data['arrivals'][0]
        # fallback for other formats
        return data if data else None
    except Exception as e:
        print(f"AeroDataBox API exception: {e}")
        return None
