"""
NewsStreamAI — Fast Ingestion Geocoder
Extracts city/country locations from news texts and assigns GPS coordinates for 3D Globe visualization.
"""
import re
from typing import Optional, Dict, Any, List

# Top global cities with precise coordinates
CITIES_DB: Dict[str, Dict[str, Any]] = {
    # France & Europe
    "paris": {"lat": 48.8566, "lon": 2.3522, "country": "France", "code": "FR"},
    "marseille": {"lat": 43.2965, "lon": 5.3698, "country": "France", "code": "FR"},
    "lyon": {"lat": 45.7640, "lon": 4.8357, "country": "France", "code": "FR"},
    "toulouse": {"lat": 43.6047, "lon": 1.4442, "country": "France", "code": "FR"},
    "nice": {"lat": 43.7102, "lon": 7.2620, "country": "France", "code": "FR"},
    "cadarache": {"lat": 43.6873, "lon": 5.7622, "country": "France", "code": "FR"},
    "bordeaux": {"lat": 44.8378, "lon": -0.5792, "country": "France", "code": "FR"},
    "strasbourg": {"lat": 48.5734, "lon": 7.7521, "country": "France", "code": "FR"},
    "londres": {"lat": 51.5074, "lon": -0.1278, "country": "Royaume-Uni", "code": "GB"},
    "london": {"lat": 51.5074, "lon": -0.1278, "country": "Royaume-Uni", "code": "GB"},
    "bruxelles": {"lat": 50.8503, "lon": 4.3517, "country": "Belgique", "code": "BE"},
    "brussels": {"lat": 50.8503, "lon": 4.3517, "country": "Belgique", "code": "BE"},
    "berlin": {"lat": 52.5200, "lon": 13.4050, "country": "Allemagne", "code": "DE"},
    "munich": {"lat": 48.1351, "lon": 11.5820, "country": "Allemagne", "code": "DE"},
    "francfort": {"lat": 50.1109, "lon": 8.6821, "country": "Allemagne", "code": "DE"},
    "rome": {"lat": 41.9028, "lon": 12.4964, "country": "Italie", "code": "IT"},
    "milan": {"lat": 45.4642, "lon": 9.1900, "country": "Italie", "code": "IT"},
    "madrid": {"lat": 40.4168, "lon": -3.7038, "country": "Espagne", "code": "ES"},
    "barcelone": {"lat": 41.3879, "lon": 2.1699, "country": "Espagne", "code": "ES"},
    "amsterdam": {"lat": 52.3676, "lon": 4.9041, "country": "Pays-Bas", "code": "NL"},
    "genève": {"lat": 46.2044, "lon": 6.1432, "country": "Suisse", "code": "CH"},
    "geneva": {"lat": 46.2044, "lon": 6.1432, "country": "Suisse", "code": "CH"},
    "zurich": {"lat": 47.3769, "lon": 8.5417, "country": "Suisse", "code": "CH"},
    "kyiv": {"lat": 50.4501, "lon": 30.5234, "country": "Ukraine", "code": "UA"},
    "kiev": {"lat": 50.4501, "lon": 30.5234, "country": "Ukraine", "code": "UA"},
    "moscou": {"lat": 55.7558, "lon": 37.6173, "country": "Russie", "code": "RU"},
    "moscow": {"lat": 55.7558, "lon": 37.6173, "country": "Russie", "code": "RU"},
    
    # North America
    "washington": {"lat": 38.9072, "lon": -77.0369, "country": "États-Unis", "code": "US"},
    "new york": {"lat": 40.7128, "lon": -74.0060, "country": "États-Unis", "code": "US"},
    "san francisco": {"lat": 37.7749, "lon": -122.4194, "country": "États-Unis", "code": "US"},
    "silicon valley": {"lat": 37.3875, "lon": -122.0575, "country": "États-Unis", "code": "US"},
    "los angeles": {"lat": 34.0522, "lon": -118.2437, "country": "États-Unis", "code": "US"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "country": "États-Unis", "code": "US"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "country": "États-Unis", "code": "US"},
    "austin": {"lat": 30.2672, "lon": -97.7431, "country": "États-Unis", "code": "US"},
    "boston": {"lat": 42.3601, "lon": -71.0589, "country": "États-Unis", "code": "US"},
    "toronto": {"lat": 43.6532, "lon": -79.3832, "country": "Canada", "code": "CA"},
    "montréal": {"lat": 45.5017, "lon": -73.5673, "country": "Canada", "code": "CA"},
    
    # Asia & Middle East
    "tokyo": {"lat": 35.6762, "lon": 139.6503, "country": "Japon", "code": "JP"},
    "pékin": {"lat": 39.9042, "lon": 116.4074, "country": "Chine", "code": "CN"},
    "beijing": {"lat": 39.9042, "lon": 116.4074, "country": "Chine", "code": "CN"},
    "shanghai": {"lat": 31.2304, "lon": 121.4737, "country": "Chine", "code": "CN"},
    "shenzhen": {"lat": 22.5431, "lon": 114.0579, "country": "Chine", "code": "CN"},
    "taipei": {"lat": 25.0330, "lon": 121.5654, "country": "Taïwan", "code": "TW"},
    "séoul": {"lat": 37.5665, "lon": 126.9780, "country": "Corée du Sud", "code": "KR"},
    "seoul": {"lat": 37.5665, "lon": 126.9780, "country": "Corée du Sud", "code": "KR"},
    "hong kong": {"lat": 22.3193, "lon": 114.1694, "country": "Hong Kong", "code": "HK"},
    "singapour": {"lat": 1.3521, "lon": 103.8198, "country": "Singapour", "code": "SG"},
    "singapore": {"lat": 1.3521, "lon": 103.8198, "country": "Singapour", "code": "SG"},
    "new delhi": {"lat": 28.6139, "lon": 77.2090, "country": "Inde", "code": "IN"},
    "tel aviv": {"lat": 32.0853, "lon": 34.7818, "country": "Israël", "code": "IL"},
    "jérusalem": {"lat": 31.7683, "lon": 35.2137, "country": "Israël", "code": "IL"},
    "gaza": {"lat": 31.5017, "lon": 34.4668, "country": "Palestine", "code": "PS"},
    "beyrouth": {"lat": 33.8938, "lon": 35.5018, "country": "Liban", "code": "LB"},
    "tehéran": {"lat": 35.6892, "lon": 51.3890, "country": "Iran", "code": "IR"},
    "dubaï": {"lat": 25.2048, "lon": 55.2708, "country": "Émirats Arabes Unis", "code": "AE"},
    "dubai": {"lat": 25.2048, "lon": 55.2708, "country": "Émirats Arabes Unis", "code": "AE"},
    "riyad": {"lat": 24.7136, "lon": 46.6753, "country": "Arabie Saoudite", "code": "SA"},

    # Latin America, Africa & Oceania
    "sydney": {"lat": -33.8688, "lon": 151.2093, "country": "Australie", "code": "AU"},
    "le caire": {"lat": 30.0444, "lon": 31.2357, "country": "Égypte", "code": "EG"},
    "johannesburg": {"lat": -26.2041, "lon": 28.0473, "country": "Afrique du Sud", "code": "ZA"},
    "alger": {"lat": 36.7538, "lon": 3.0588, "country": "Algérie", "code": "DZ"},
    "rabat": {"lat": 34.0209, "lon": -6.8416, "country": "Maroc", "code": "MA"},
    "tunis": {"lat": 36.8065, "lon": 10.1815, "country": "Tunisie", "code": "TN"},
    "dakar": {"lat": 14.7167, "lon": -17.4677, "country": "Sénégal", "code": "SN"},
    "brasilia": {"lat": -15.7975, "lon": -47.8919, "country": "Brésil", "code": "BR"},
    "são paulo": {"lat": -23.5505, "lon": -46.6333, "country": "Brésil", "code": "BR"},
    "buenos aires": {"lat": -34.6037, "lon": -58.3816, "country": "Argentine", "code": "AR"}
}

# Country centroids for fallback
COUNTRIES_DB: Dict[str, Dict[str, Any]] = {
    "france": {"lat": 46.2276, "lon": 2.2137, "country": "France", "code": "FR"},
    "états-unis": {"lat": 37.0902, "lon": -95.7129, "country": "États-Unis", "code": "US"},
    "etats-unis": {"lat": 37.0902, "lon": -95.7129, "country": "États-Unis", "code": "US"},
    "usa": {"lat": 37.0902, "lon": -95.7129, "country": "États-Unis", "code": "US"},
    "royaume-uni": {"lat": 55.3781, "lon": -3.4360, "country": "Royaume-Uni", "code": "GB"},
    "uk": {"lat": 55.3781, "lon": -3.4360, "country": "Royaume-Uni", "code": "GB"},
    "allemagne": {"lat": 51.1657, "lon": 10.4515, "country": "Allemagne", "code": "DE"},
    "italie": {"lat": 41.8719, "lon": 12.5674, "country": "Italie", "code": "IT"},
    "espagne": {"lat": 40.4637, "lon": -3.7492, "country": "Espagne", "code": "ES"},
    "chine": {"lat": 35.8617, "lon": 104.1954, "country": "Chine", "code": "CN"},
    "china": {"lat": 35.8617, "lon": 104.1954, "country": "Chine", "code": "CN"},
    "japon": {"lat": 36.2048, "lon": 138.2529, "country": "Japon", "code": "JP"},
    "japan": {"lat": 36.2048, "lon": 138.2529, "country": "Japon", "code": "JP"},
    "russie": {"lat": 61.5240, "lon": 105.3188, "country": "Russie", "code": "RU"},
    "russia": {"lat": 61.5240, "lon": 105.3188, "country": "Russie", "code": "RU"},
    "ukraine": {"lat": 48.3794, "lon": 31.1656, "country": "Ukraine", "code": "UA"},
    "israël": {"lat": 31.0461, "lon": 34.8516, "country": "Israël", "code": "IL"},
    "israel": {"lat": 31.0461, "lon": 34.8516, "country": "Israël", "code": "IL"},
    "iran": {"lat": 32.4279, "lon": 53.6880, "country": "Iran", "code": "IR"},
    "taïwan": {"lat": 23.6978, "lon": 120.9605, "country": "Taïwan", "code": "TW"},
    "taiwan": {"lat": 23.6978, "lon": 120.9605, "country": "Taïwan", "code": "TW"},
    "inde": {"lat": 20.5937, "lon": 78.9629, "country": "Inde", "code": "IN"},
    "india": {"lat": 20.5937, "lon": 78.9629, "country": "Inde", "code": "IN"},
    "brésil": {"lat": -14.2350, "lon": -51.9253, "country": "Brésil", "code": "BR"},
    "canada": {"lat": 56.1304, "lon": -106.3468, "country": "Canada", "code": "CA"},
    "australie": {"lat": -25.2744, "lon": 133.7751, "country": "Australie", "code": "AU"},
    "suisse": {"lat": 46.8182, "lon": 8.2275, "country": "Suisse", "code": "CH"},
    "belgique": {"lat": 50.5039, "lon": 4.4699, "country": "Belgique", "code": "BE"}
}

# Key regions and geographical landmarks
REGIONS_DB: Dict[str, Dict[str, Any]] = {
    "pyrénées": {"lat": 42.8000, "lon": 0.5000, "name": "Pyrénées", "country": "France", "code": "FR"},
    "pyrenees": {"lat": 42.8000, "lon": 0.5000, "name": "Pyrénées", "country": "France", "code": "FR"},
    "alpes": {"lat": 45.8326, "lon": 6.8652, "name": "Alpes", "country": "France", "code": "FR"},
    "alps": {"lat": 45.8326, "lon": 6.8652, "name": "Alpes", "country": "France", "code": "FR"},
    "bretagne": {"lat": 48.2020, "lon": -2.9326, "name": "Bretagne", "country": "France", "code": "FR"},
    "corse": {"lat": 42.0396, "lon": 9.0129, "name": "Corse", "country": "France", "code": "FR"},
    "normandie": {"lat": 49.1829, "lon": -0.3707, "name": "Normandie", "country": "France", "code": "FR"},
    "californie": {"lat": 36.7783, "lon": -119.4179, "name": "Californie", "country": "États-Unis", "code": "US"},
    "california": {"lat": 36.7783, "lon": -119.4179, "name": "Californie", "country": "États-Unis", "code": "US"},
    "texas": {"lat": 31.9686, "lon": -99.9018, "name": "Texas", "country": "États-Unis", "code": "US"},
    "floride": {"lat": 27.6648, "lon": -81.5158, "name": "Floride", "country": "États-Unis", "code": "US"},
    "florida": {"lat": 27.6648, "lon": -81.5158, "name": "Floride", "country": "États-Unis", "code": "US"},
    "mer rouge": {"lat": 20.2802, "lon": 38.5126, "name": "Mer Rouge", "country": "International", "code": "INT"},
    "red sea": {"lat": 20.2802, "lon": 38.5126, "name": "Mer Rouge", "country": "International", "code": "INT"},
    "détroit de taïwan": {"lat": 24.5000, "lon": 119.5000, "name": "Détroit de Taïwan", "country": "Taïwan", "code": "TW"},
}

# Key institutions, tech hubs & cultural landmarks
ENTITIES_DB: Dict[str, Dict[str, Any]] = {
    "tsmc": {"lat": 24.7820, "lon": 120.9980, "name": "Hsinchu (TSMC)", "country": "Taïwan", "code": "TW"},
    "openai": {"lat": 37.7749, "lon": -122.4194, "name": "San Francisco (OpenAI)", "country": "États-Unis", "code": "US"},
    "apple": {"lat": 37.3346, "lon": -122.0090, "name": "Cupertino (Apple)", "country": "États-Unis", "code": "US"},
    "google": {"lat": 37.4220, "lon": -122.0841, "name": "Mountain View (Google)", "country": "États-Unis", "code": "US"},
    "nvidia": {"lat": 37.3708, "lon": -121.9636, "name": "Santa Clara (NVIDIA)", "country": "États-Unis", "code": "US"},
    "microsoft": {"lat": 47.6740, "lon": -122.1215, "name": "Redmond (Microsoft)", "country": "États-Unis", "code": "US"},
    "rockstar": {"lat": 40.7242, "lon": -73.9967, "name": "New York (Rockstar Games)", "country": "États-Unis", "code": "US"},
    "one piece": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo (Shueisha)", "country": "Japon", "code": "JP"},
    "eiichirō ōda": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo (Oda)", "country": "Japon", "code": "JP"},
    "eiichiro oda": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo (Oda)", "country": "Japon", "code": "JP"},
    "manga": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo", "country": "Japon", "code": "JP"},
    "anime": {"lat": 35.6762, "lon": 139.6503, "name": "Tokyo", "country": "Japon", "code": "JP"},
    "g7": {"lat": 50.8503, "lon": 4.3517, "name": "Sommet International (G7)", "country": "Belgique", "code": "BE"},
    "otan": {"lat": 50.8788, "lon": 4.4258, "name": "Bruxelles (OTAN)", "country": "Belgique", "code": "BE"},
    "nato": {"lat": 50.8788, "lon": 4.4258, "name": "Bruxelles (NATO)", "country": "Belgique", "code": "BE"},
    "cern": {"lat": 46.2330, "lon": 6.0557, "name": "Genève (CERN)", "country": "Suisse", "code": "CH"},
    "nasa": {"lat": 38.8830, "lon": -77.0163, "name": "Washington (NASA)", "country": "États-Unis", "code": "US"},
    "esa": {"lat": 48.8475, "lon": 2.3025, "name": "Paris (ESA)", "country": "France", "code": "FR"}
}

class FastGeocoder:
    @staticmethod
    def extract_location(title: str, text: str = "", category: str = "", sources: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extracts location from title, text, entities, regions and fallbacks.
        Priority: 1. Specific City -> 2. Region -> 3. Known Entity -> 4. Country -> 5. Category/Source fallback.
        """
        combined = f"{title} {text[:600]}".lower()
        
        # 1. Search for city match
        for city, info in CITIES_DB.items():
            pattern = rf"\b{re.escape(city)}\b"
            if re.search(pattern, combined):
                capitalized_city = city.capitalize()
                return {
                    "latitude": info["lat"],
                    "longitude": info["lon"],
                    "location_name": f"{capitalized_city}, {info['country']}",
                    "country_code": info["code"],
                    "is_city_precise": True
                }
                
        # 2. Search for region / landmark match
        for region, info in REGIONS_DB.items():
            pattern = rf"\b{re.escape(region)}\b"
            if re.search(pattern, combined):
                return {
                    "latitude": info["lat"],
                    "longitude": info["lon"],
                    "location_name": f"{info['name']}, {info['country']}",
                    "country_code": info["code"],
                    "is_city_precise": True
                }

        # 3. Search for known entities / hubs (TSMC, OpenAI, One Piece, etc.)
        for entity, info in ENTITIES_DB.items():
            pattern = rf"\b{re.escape(entity)}\b"
            if re.search(pattern, combined):
                return {
                    "latitude": info["lat"],
                    "longitude": info["lon"],
                    "location_name": info["name"],
                    "country_code": info["code"],
                    "is_city_precise": True
                }

        # 4. Search for country match
        for country_key, info in COUNTRIES_DB.items():
            pattern = rf"\b{re.escape(country_key)}\b"
            if re.search(pattern, combined):
                return {
                    "latitude": info["lat"],
                    "longitude": info["lon"],
                    "location_name": info["country"],
                    "country_code": info["code"],
                    "is_city_precise": False
                }
                
        # 5. Fallback based on category
        cat_lower = category.lower()
        if "manga" in cat_lower or "anime" in cat_lower:
            return {
                "latitude": 35.6762,
                "longitude": 139.6503,
                "location_name": "Tokyo, Japon",
                "country_code": "JP",
                "is_city_precise": True
            }
        elif "politique" in cat_lower or "monde" in cat_lower:
            return {
                "latitude": 48.8566,
                "longitude": 2.3522,
                "location_name": "Paris, France",
                "country_code": "FR",
                "is_city_precise": True
            }

        return None

geocoder = FastGeocoder()

