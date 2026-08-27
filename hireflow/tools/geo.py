from __future__ import annotations


class LocationMapper:
    """Maps free-form location preference words to freehire codes.

    ``map()`` returns a dict with ``countries`` (ISO-2 codes) and ``regions``
    from freehire's facets. Unrecognised words are ignored so an unrestricted
    search still happens (never block a run over a mapping miss).
    """

    _COUNTRIES = {
        "afghanistan": "af", "albania": "al", "algeria": "dz", "argentina": "ar",
        "armenia": "am", "australia": "au", "austria": "at", "azerbaijan": "az",
        "bahrain": "bh", "bangladesh": "bd", "belarus": "by", "belgium": "be",
        "brazil": "br", "bulgaria": "bg", "cambodia": "kh", "canada": "ca",
        "chile": "cl", "china": "cn", "colombia": "co", "croatia": "hr",
        "cyprus": "cy", "czech republic": "cz", "czechia": "cz", "denmark": "dk",
        "egypt": "eg", "estonia": "ee", "fiji": "fj", "finland": "fi",
        "france": "fr", "georgia": "ge", "germany": "de", "ghana": "gh",
        "greece": "gr", "hong kong": "hk", "hungary": "hu", "iceland": "is",
        "india": "in", "indonesia": "id", "iran": "ir", "iraq": "iq",
        "ireland": "ie", "israel": "il", "italy": "it", "japan": "jp",
        "jordan": "jo", "kazakhstan": "kz", "kenya": "ke", "kuwait": "kw",
        "latvia": "lv", "lebanon": "lb", "lithuania": "lt", "luxembourg": "lu",
        "malaysia": "my", "malta": "mt", "mexico": "mx", "morocco": "ma",
        "myanmar": "mm", "netherlands": "nl", "new zealand": "nz",
        "nigeria": "ng", "north korea": "kp", "norway": "no", "oman": "om",
        "pakistan": "pk", "palestine": "ps", "philippines": "ph", "poland": "pl",
        "portugal": "pt", "qatar": "qa", "romania": "ro", "saudi arabia": "sa",
        "serbia": "rs", "singapore": "sg", "slovakia": "sk", "slovenia": "si",
        "south africa": "za", "south korea": "kr", "korea": "kr", "spain": "es",
        "sri lanka": "lk", "sweden": "se", "switzerland": "ch", "taiwan": "tw",
        "thailand": "th", "turkey": "tr", "uae": "ae", "united arab emirates": "ae",
        "ukraine": "ua", "uk": "gb", "united kingdom": "gb", "usa": "us",
        "united states": "us", "uruguay": "uy", "uzbekistan": "uz",
        "vietnam": "vn", "yemen": "ye", "zimbabwe": "zw",
    }
    _CITIES = {
        "tokyo": ("jp", "Tokyo"), "osaka": ("jp", "Osaka"), "kyoto": ("jp", "Kyoto"),
        "yokohama": ("jp", "Yokohama"), "nagoya": ("jp", "Nagoya"), "sendai": ("jp", "Sendai"),
        "fukuoka": ("jp", "Fukuoka"), "sapporo": ("jp", "Sapporo"), "kobe": ("jp", "Kobe"),
        "hiroshima": ("jp", "Hiroshima"),
        "kuala lumpur": ("my", "Kuala Lumpur"), "penang": ("my", "Penang"),
        "george town": ("my", "George Town"),
        "jakarta": ("id", "Jakarta"), "bali": ("id", "Bali"), "bandung": ("id", "Bandung"),
        "seoul": ("kr", "Seoul"), "busan": ("kr", "Busan"), "incheon": ("kr", "Incheon"),
        "singapore": ("sg", "Singapore"),
        "manila": ("ph", "Manila"), "cebu": ("ph", "Cebu"),
        "hong kong": ("hk", "Hong Kong"),
        "bangkok": ("th", "Bangkok"), "ho chi minh": ("vn", "Ho Chi Minh"), "hanoi": ("vn", "Hanoi"),
        "beijing": ("cn", "Beijing"), "shanghai": ("cn", "Shanghai"), "shenzhen": ("cn", "Shenzhen"),
        "london": ("gb", "London"), "manchester": ("gb", "Manchester"), "birmingham": ("gb", "Birmingham"),
        "edinburgh": ("gb", "Edinburgh"),
        "paris": ("fr", "Paris"), "lyon": ("fr", "Lyon"), "lyons": ("fr", "Lyon"),
        "dublin": ("ie", "Dublin"),
        "new york": ("us", "New York"), "san francisco": ("us", "San Francisco"),
        "los angeles": ("us", "Los Angeles"), "seattle": ("us", "Seattle"),
        "austin": ("us", "Austin"), "chicago": ("us", "Chicago"), "boston": ("us", "Boston"),
        "denver": ("us", "Denver"),
        "bangalore": ("in", "Bangalore"), "bengaluru": ("in", "Bengaluru"),
        "mumbai": ("in", "Mumbai"), "delhi": ("in", "Delhi"), "hyderabad": ("in", "Hyderabad"),
        "pune": ("in", "Pune"), "chennai": ("in", "Chennai"), "kolkata": ("in", "Kolkata"),
        "berlin": ("de", "Berlin"), "munich": ("de", "Munich"), "hamburg": ("de", "Hamburg"),
        "cologne": ("de", "Cologne"),
        "amsterdam": ("nl", "Amsterdam"), "rotterdam": ("nl", "Rotterdam"),
        "madrid": ("es", "Madrid"), "barcelona": ("es", "Barcelona"),
        "rome": ("it", "Rome"), "milan": ("it", "Milan"),
        "toronto": ("ca", "Toronto"), "vancouver": ("ca", "Vancouver"),
        "montreal": ("ca", "Montreal"), "ottawa": ("ca", "Ottawa"),
        "sydney": ("au", "Sydney"), "melbourne": ("au", "Melbourne"), "brisbane": ("au", "Brisbane"),
        "dubai": ("ae", "Dubai"), "abu dhabi": ("ae", "Abu Dhabi"), "doha": ("qa", "Doha"),
        "istanbul": ("tr", "Istanbul"),
    }
    _STATES = {
        "johor": ("my", "Johor"), "selangor": ("my", "Selangor"),
        "penang": ("my", "Penang"), "kuala kuala": ("my", "Kuala Lumpur"),
        "aichi": ("jp", "Nagoya"), "osaka": ("jp", "Osaka"), "kanto": ("jp", "Kanto"),
        "surabaya": ("id", "Surabaya"),
        "karnataka": ("in", "Bangalore"),
    }
    _REGIONS = {
        "asia": "apac", "apac": "apac", "south east asia": "apac", "asean": "apac",
        "emea": "emea", "europe": "emea", "middle east": "emea", "africa": "emea",
        "us": "us", "north america": "us",
        "latam": "latam", "latin america": "latam", "south america": "latam",
    }
    _REGION_CODES = frozenset({"apac", "emea", "us", "latam"})
    _COUNTRY_CODES = frozenset(set(_COUNTRIES.values()) | {"gb", "us", "kr", "ae"})
    _ANYWHERE = {"anywhere", "remote", "world wide", "worldwide", "globally", "any", ""}

    @classmethod
    def map(cls, locations: list[str] | None) -> dict[str, list[str]]:
        countries: list[str] = []
        regions: list[str] = []
        for raw in locations or []:
            code = cls._resolve(raw)
            if not code:
                continue
            if code in cls._REGION_CODES:
                if code not in regions:
                    regions.append(code)
            elif code not in countries:
                countries.append(code)
        return {"countries": countries, "regions": regions}

    @classmethod
    def map_full(cls, locations: list[str] | None) -> dict[str, list[str]]:
        countries: list[str] = []
        regions: list[str] = []
        cities: list[str] = []
        linkedin_parts: list[str] = []
        for raw in locations or []:
            stripped = raw.strip()
            if not stripped or stripped.lower() in cls._ANYWHERE:
                continue
            resolved = cls._resolve_city(stripped)
            if resolved is not None:
                code, city = resolved
                if city and city not in cities:
                    cities.append(city)
                if code in cls._REGION_CODES:
                    if code not in regions:
                        regions.append(code)
                elif code and code not in countries:
                    countries.append(code)
                if city and city not in linkedin_parts:
                    linkedin_parts.append(city)
                continue
            code = cls._resolve(stripped)
            if code in cls._REGION_CODES:
                if code not in regions:
                    regions.append(code)
                linkedin_parts.append(stripped)
            elif code:
                if code not in countries:
                    countries.append(code)
                linkedin_parts.append(stripped)
            else:
                cities.append(stripped)
                linkedin_parts.append(stripped)
        return {
            "countries": countries,
            "regions": regions,
            "cities": cities,
            "linkedin_location": ", ".join(linkedin_parts),
        }

    @classmethod
    def _resolve_city(cls, token: str) -> tuple[str, str] | None:
        lowered = token.lower()
        if lowered in cls._CITIES:
            return cls._CITIES[lowered]
        for key, pair in cls._STATES.items():
            if key == lowered or key in lowered:
                return pair
        return None

    @classmethod
    def country_name(cls, code: str) -> str:
        for name, country_code in cls._COUNTRIES.items():
            if country_code == code:
                return name
        return ""

    @classmethod
    def _resolve(cls, raw: str) -> str:
        token = raw.strip().lower()
        if not token or token in cls._ANYWHERE:
            return ""
        iso = token.split("/")[-1].strip() if "/" in token else token
        if len(iso) == 2 and iso in cls._COUNTRY_CODES | cls._REGION_CODES:
            return iso
        for key, code in cls._COUNTRIES.items():
            if key in token:
                return code
        for key, region in cls._REGIONS.items():
            if key in token:
                return region
        resolved = cls._resolve_city(token)
        if resolved is not None:
            return resolved[0]
        return ""
