import requests

# API keys
OWM_API_KEY = "9641311a3d5f779f45996323afa3460c"
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjlhYWE0NDQ2NzQxNjQyODliMTBiZWNhYWIyNDAyOTA3IiwiaCI6Im11cm11cjY0In0="


# Step 1: Get coordinates
# Use OpenWeatherMap geocoding to turn city names into latitude/longitude.
def get_coordinates(city: str):
    url = (
        f"http://api.openweathermap.org/geo/1.0/direct"
        f"?q={city}&limit=1&appid={OWM_API_KEY}"
    )
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"No coordinates found for city: {city}")
    return data[0]["lat"], data[0]["lon"]


# Step 2: Weather + AQI
# Fetch weather and AQI for a location from OpenWeather.
def get_weather_and_aqi(lat: float, lon: float):
    weather_url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}&appid={OWM_API_KEY}&units=metric"
    )
    aqi_url = (
        f"http://api.openweathermap.org/data/2.5/air_pollution"
        f"?lat={lat}&lon={lon}&appid={OWM_API_KEY}"
    )

    weather_resp = requests.get(weather_url)
    weather_resp.raise_for_status()
    weather = weather_resp.json()

    aqi_resp = requests.get(aqi_url)
    aqi_resp.raise_for_status()
    aqi = aqi_resp.json()

    rain_mm = weather.get("rain", {}).get("1h", 0)
    aqi_value = aqi["list"][0]["main"]["aqi"] if aqi.get("list") else None

    return {
        "temperature_c": weather["main"]["temp"],
        "wind_kmph": weather["wind"]["speed"] * 3.6,
        "rain_mm": rain_mm,
        "aqi_value": aqi_value,
        "description": weather["weather"][0]["description"],
    }


# Step 3: Route info
# Fetch route distance and ETA from OpenRouteService.
def get_route_info(src_lat: float, src_lon: float, dst_lat: float, dst_lon: float):
    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": ORS_API_KEY}
    body = {"coordinates": [[src_lon, src_lat], [dst_lon, dst_lat]]}

    route_resp = requests.post(ors_url, json=body, headers=headers)
    route_resp.raise_for_status()
    route = route_resp.json()

    if "features" in route:
        feature = route["features"][0]
        segment = feature["properties"]["segments"][0]
        return {
            "distance_km": segment["distance"] / 1000,
            "eta_min": segment["duration"] / 60,
            "raw": route,
        }
    if "routes" in route:
        summary = route["routes"][0].get("summary", {})
        return {
            "distance_km": summary.get("distance", 0) / 1000,
            "eta_min": summary.get("duration", 0) / 60,
            "raw": route,
        }

    raise ValueError(f"Unexpected OpenRouteService response: {route}")


def get_climate_route_info(source: str, destination: str):
    src_lat, src_lon = get_coordinates(source)
    dst_lat, dst_lon = get_coordinates(destination)

    return {
        "source": source,
        "destination": destination,
        "source_coords": {"lat": src_lat, "lon": src_lon},
        "destination_coords": {"lat": dst_lat, "lon": dst_lon},
        "source_weather": get_weather_and_aqi(src_lat, src_lon),
        "destination_weather": get_weather_and_aqi(dst_lat, dst_lon),
        "route": get_route_info(src_lat, src_lon, dst_lat, dst_lon),
    }


# Step 4: Output results
if __name__ == "__main__":
    source = input("Enter source city or address: ").strip()
    destination = input("Enter destination city or address: ").strip()

    if not source or not destination:
        print("Both source and destination are required.")
    else:
        try:
            data = get_climate_route_info(source, destination)
        except Exception as exc:
            print(f"Error: {exc}")
            raise

        print(f"Source: {data['source']} → Destination: {data['destination']}")
        print(f"Source coordinates: {data['source_coords']}")
        print(f"Destination coordinates: {data['destination_coords']}")

        print("\nSource weather + AQI:")
        print(f"  Temperature: {data['source_weather']['temperature_c']} °C")
        print(f"  Wind: {data['source_weather']['wind_kmph']:.2f} km/h")
        print(f"  Rain: {data['source_weather']['rain_mm']} mm")
        print(f"  AQI: {data['source_weather']['aqi_value']}")
        print(f"  Weather: {data['source_weather']['description']}")

        print("\nDestination weather + AQI:")
        print(f"  Temperature: {data['destination_weather']['temperature_c']} °C")
        print(f"  Wind: {data['destination_weather']['wind_kmph']:.2f} km/h")
        print(f"  Rain: {data['destination_weather']['rain_mm']} mm")
        print(f"  AQI: {data['destination_weather']['aqi_value']}")
        print(f"  Weather: {data['destination_weather']['description']}")

        print("\nRoute Info:")
        print(f"  Distance: {data['route']['distance_km']:.2f} km")
        print(f"  ETA: {data['route']['eta_min']:.2f} minutes")
