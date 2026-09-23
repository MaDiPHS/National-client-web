from django.shortcuts import render
from django.views.generic import TemplateView
from datetime import datetime, timedelta, timezone
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor
import requests
import random

# Create your views here.



class ForecastingTemperatureView(TemplateView):
    template_name = 'forecasts/temperature.html'

    def fetch_weather(self, city, coords):
        """Fetch weather data for a single city using DCCMS API."""
        url = (
            f"https://irh.nibio.no/weather/weatheradapter/dccmslocationforecast?"
            f"latitude={coords['latitude']}&longitude={coords['longitude']}"
        )
        
        cache_key = f"weather_{city}_{datetime.now().strftime('%Y%m%d')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            response = requests.get(url, headers={'accept': 'application/json'}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Parse the DCCMS response
                from datetime import timezone, timedelta

                utc_time = datetime.strptime(
                    data["timeStart"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

                time_start = utc_time + timedelta(hours=2)
                interval_seconds = data.get("interval", 3600)
                
                location_data = data.get("locationWeatherData", [])[0]
                records = location_data.get("data", [])
                
                # Format dates
                formatted_dates = [
                    (time_start + timedelta(seconds=i * interval_seconds)).strftime("%Y-%m-%d %H:%M")
                    for i in range(len(records))
                ]
                
                # Extract temperature (index 0) and precipitation (index 1) based on DCCMS sample
                # Index 0 = temperature, Index 1 = precipitation
                temperatures = [record[0] for record in records]
                precipitations = [record[1] for record in records]
                
                result = {
                    "dates": formatted_dates,
                    "temperatures": temperatures,
                    "precipitations": precipitations,
                    "city": city,
                    "current_temp": round(temperatures[0], 1) if temperatures else "N/A",
                    "max_temp": round(max(temperatures), 1) if temperatures else "N/A",
                    "min_temp": round(min(temperatures), 1) if temperatures else "N/A",
                    "weather_condition": self.get_weather_condition(precipitations, temperatures)
                }
                
                # Cache for 1 hour
                cache.set(cache_key, result, 3600)
                return result
                
        except requests.RequestException as e:
            return {"error": str(e), "city": city}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "city": city}



    from datetime import datetime, timedelta

    def get_current_index(self, dates):
        now = datetime.utcnow() + timedelta(hours=2)  # Convert to Malawi time

        for i, d in enumerate(dates):
            dt = datetime.strptime(d, "%Y-%m-%d %H:%M")
            if dt >= now:
                return i

        return 0
    
    def get_today_start_index(self, dates):

        today = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d")

        for i, d in enumerate(dates):
            if d.startswith(today + " 00:00"):
                return i

        return 0
    def get_weather_condition(self, precipitations, temperatures):
        """Determine weather condition based on precipitation and temperature."""
        avg_precip = sum(precipitations[:6]) / len(precipitations[:6]) if precipitations else 0
        avg_temp = sum(temperatures[:6]) / len(temperatures[:6]) if temperatures else 20
        
        if avg_precip > 5:
            return "heavy_rain"
        elif avg_precip > 1:
            return "light_rain"
        elif avg_precip > 0.1:
            return "drizzle"
        elif avg_temp > 25:
            return "sunny"
        elif avg_temp > 20:
            return "partly_cloudy"
        else:
            return "cloudy"

    def get_weather_data(self):
        """Fetch weather data for multiple cities concurrently."""
        cities = {
            "Lilongwe": {"longitude": 33.774, "latitude": -13.963},
            "Blantyre": {"longitude": 35.005833, "latitude": -15.786111},
            "Zomba": {"longitude": 35.5, "latitude": -15.1667},
            "Mzuzu": {"longitude": 34.02071, "latitude": -11.46556}
        }

        weather_data = {}

        with ThreadPoolExecutor(max_workers=len(cities)) as executor:
            future_to_city = {
                executor.submit(self.fetch_weather, city, coords): city
                for city, coords in cities.items()
            }
            for future in future_to_city:
                city = future_to_city[future]
                result = future.result()
                if result:
                    weather_data[city] = result

        return weather_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch all weather data
        weather_data = self.get_weather_data()
        
        # Split into current and forecast data
        current_date_weather = {}
        forecast_weather = {}

  
        
        for city, data in weather_data.items():
            if data and "error" not in data:

                today_start_index = self.get_today_start_index(data["dates"])
                current_index = self.get_current_index(data["dates"])

                current_date_weather[city] = {
                    "dates": data["dates"][today_start_index:today_start_index+24],
                    "temperatures": data["temperatures"][today_start_index:today_start_index+24],
                    "current_temp": data["temperatures"][current_index],
                    "max_temp": max(data["temperatures"][today_start_index:today_start_index+24]),
                    "min_temp": min(data["temperatures"][today_start_index:today_start_index+24]),
                    "weather_condition": data["weather_condition"]
                }

                forecast_weather[city] = {
                    "dates": data["dates"][today_start_index+24:today_start_index+72],
                    "temperatures": data["temperatures"][today_start_index+24:today_start_index+72],
                }
            else:
                current_date_weather[city] = {"error": "Data unavailable"}
                forecast_weather[city] = {"error": "Data unavailable"}

        context["current_date_weather"] = current_date_weather
        context["forecast_weather"] = forecast_weather
        context["current_date"] = datetime.now().strftime("%B %d, %Y")

        return context


class ForecastingRainfallView(TemplateView):
    template_name = 'forecasts/rainfall.html'

    from datetime import datetime, timezone

    def get_current_index(self, dates):
        now = datetime.utcnow()

        for i, d in enumerate(dates):
            dt = datetime.strptime(d, "%Y-%m-%d %H:%M")
            if dt >= now:
                return i

        return 0
    

    def fetch_weather(self, city, coords):
        """Fetch weather data for a single city using DCCMS API."""
        url = (
            f"https://irh.nibio.no/weather/weatheradapter/dccmslocationforecast?"
            f"latitude={coords['latitude']}&longitude={coords['longitude']}"
        )
        
        cache_key = f"rainfall_{city}_{datetime.now().strftime('%Y%m%d')}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            response = requests.get(url, headers={'accept': 'application/json'}, timeout=10)
            if response.status_code == 200:
                data = response.json()

                from datetime import timezone, timedelta

                # Convert API UTC time to Malawi time
                utc_time = datetime.strptime(
                    data["timeStart"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

                time_start = utc_time + timedelta(hours=2)

                interval_seconds = data.get("interval", 3600)

                location_data = data.get("locationWeatherData", [])[0]
                records = location_data.get("data", [])

                # Generate timestamps for each record
                formatted_dates = [
                    (time_start + timedelta(seconds=i * interval_seconds)).strftime("%Y-%m-%d %H:%M")
                    for i in range(len(records))
                ]

                # Extract precipitation and temperature
                precipitations = [record[1] for record in records]
                temperatures = [record[0] for record in records]

                # Calculate daily totals
                daily_totals = {}
                for date_str, precip in zip(formatted_dates, precipitations):
                    day = date_str.split()[0]
                    if day not in daily_totals:
                        daily_totals[day] = 0
                    daily_totals[day] += precip

                result = {
                    "dates": formatted_dates,
                    "precipitations": precipitations,
                    "temperatures": temperatures,
                    "city": city,
                    "total_precip_today": round(sum(precipitations[:24]), 1) if precipitations else 0,
                    "max_precip_intensity": round(max(precipitations[:24]), 1) if precipitations else 0,
                    "daily_totals": daily_totals,
                    "weather_condition": self.get_weather_condition(precipitations)
                }

                cache.set(cache_key, result, 3600)
                return result

        except requests.RequestException as e:
            return {"error": str(e), "city": city}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}", "city": city}
        
    def get_weather_condition(self, precipitations):
        """Determine weather condition based on precipitation."""
        total_precip = sum(precipitations[:24]) if precipitations else 0
        
        if total_precip > 20:
            return "heavy_rain"
        elif total_precip > 10:
            return "moderate_rain"
        elif total_precip > 2:
            return "light_rain"
        elif total_precip > 0.1:
            return "drizzle"
        else:
            return "dry"

    def get_weather_data(self):
        """Fetch weather data for multiple cities concurrently."""
        cities = {
            "Lilongwe": {"longitude": 33.774, "latitude": -13.963},
            "Blantyre": {"longitude": 35.005833, "latitude": -15.786111},
            "Zomba": {"longitude": 35.5, "latitude": -15.1667},
            "Mzuzu": {"longitude": 34.02071, "latitude": -11.46556}
        }

        weather_data = {}

        with ThreadPoolExecutor(max_workers=len(cities)) as executor:
            future_to_city = {
                executor.submit(self.fetch_weather, city, coords): city
                for city, coords in cities.items()
            }
            for future in future_to_city:
                city = future_to_city[future]
                result = future.result()
                if result:
                    weather_data[city] = result

        return weather_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        weather_data = self.get_weather_data()
        
        current_date_weather = {}
        forecast_weather = {}
        
        for city, data in weather_data.items():
            if data and "error" not in data:
                start_index = self.get_current_index(data["dates"])

                current_date_weather[city] = {
                    "dates": data["dates"][start_index:start_index+24],
                    "precipitations": data["precipitations"][start_index:start_index+24],
                    "total_precip_today": sum(data["precipitations"][start_index:start_index+24]),
                    "max_precip_intensity": max(data["precipitations"][start_index:start_index+24]),
                    "weather_condition": data["weather_condition"]
                }

                forecast_weather[city] = {
                    "dates": data["dates"][start_index+24:start_index+72],
                    "precipitations": data["precipitations"][start_index+24:start_index+72],
                    "daily_totals": data.get("daily_totals", {})
                }
            else:
                current_date_weather[city] = {"error": "Data unavailable"}
                forecast_weather[city] = {"error": "Data unavailable"}

        context["current_date_weather"] = current_date_weather
        context["forecast_weather"] = forecast_weather
        context["current_date"] = datetime.now().strftime("%B %d, %Y")

        return context