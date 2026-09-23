import requests
import pytz
from datetime import datetime, timezone, timedelta


class WeatherService:
    USER_AGENT = "Madiphs-Frontend"
    LOCAL_TZ = pytz.timezone("Africa/Blantyre")

    @staticmethod
    def reverse_geocode(lat, lon):
        """Convert latitude/longitude into a location name."""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat": lat, "lon": lon, "format": "json"}

        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": WeatherService.USER_AGENT},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                address = data.get("address", {})
                return (
                    address.get("city")
                    or address.get("town")
                    or address.get("village")
                    or address.get("state")
                    or data.get("display_name")
                )
        except Exception:
            pass

        return "Unknown location"

    @staticmethod
    def fetch_weather(lat, lon):
        """Fetch current temperature & rainfall."""
        url = "https://irh.nibio.no/weather/weatheradapter/dccmslocationforecast/"
        params = {"longitude": lon, "latitude": lat}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return None

            data = response.json()
            location_data_list = data.get("locationWeatherData", [])
            if not location_data_list:
                return None

            records = location_data_list[0].get("data", [])
            time_start_str = data.get("timeStart")
            interval = data.get("interval", 3600)

            if not records or not time_start_str:
                return None

            time_start = datetime.strptime(
                time_start_str, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)

            now_local = datetime.now(WeatherService.LOCAL_TZ)
            now_utc = now_local.astimezone(timezone.utc)

            adjusted_time = now_utc + timedelta(hours=2)
            index = int((adjusted_time - time_start).total_seconds() / interval)
            index = max(0, min(index, len(records) - 1))

            temp = records[index][0] if records[index] else None
            rain = records[index][1] if records[index] else None

            return {
                "current_temperature": temp,
                "current_rainfall": rain,
            }

        except Exception:
            return None
