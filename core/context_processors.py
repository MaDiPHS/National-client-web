from .services.weather_service import WeatherService


def weather_context(request):
    lat = request.GET.get("lat")
    lon = request.GET.get("lon")

    if lat and lon:
        return {
            "user_weather": WeatherService.fetch_weather(lat, lon),
            "user_location_name": WeatherService.reverse_geocode(lat, lon),
        }

    return {
        "user_weather": None,
        "user_location_name": None,
    }
