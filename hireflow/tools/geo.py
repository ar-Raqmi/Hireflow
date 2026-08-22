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
        "tokyo": "jp", "osaka": "jp", "kyoto": "jp", "yokohama": "jp", "nagoya": "jp",
        "kuala lumpur": "my", "penang": "my", "kuching": "my", "george town": "my",
        "jakarta": "id", "bali": "id", "bandung": "id", "surabaya": "id",
        "seoul": "kr", "busan": "kr", "incheon": "kr",
        "singapore": "sg",
        "manila": "ph", "cebu": "ph",
        "hong kong": "hk",
        "bangkok": "th", "ho chi minh": "vn", "hanoi": "vn",
        "beijing": "cn", "shanghai": "cn", "shenzhen": "cn",
        "london": "gb", "manchester": "gb", "birmingham": "gb", "edinburgh": "gb",
        "paris": "fr", "lyon": "fr",
        "dublin": "ie",
        "new york": "us", "san francisco": "us", "los angeles": "us", "seattle": "us",
        "austin": "us", "chicago": "us", "boston": "us", "denver": "us",
        "bangalore": "in", "bengaluru": "in", "mumbai": "in", "delhi": "in",
        "hyderabad": "in", "pune": "in", "chennai": "in", "kolkata": "in",
        "berlin": "de", "munich": "de", "hamburg": "de", "cologne": "de",
        "amsterdam": "nl", "rotterdam": "nl",
        "madrid": "es", "barcelona": "es",
        "rome": "it", "milan": "it",
        "toronto": "ca", "vancouver": "ca", "montreal": "ca", "ottawa": "ca",
        "sydney": "au", "melbourne": "au", "brisbane": "au",
        "dubai": "ae", "abu dhabi": "ae", "doha": "qa", "istanbul": "tr",
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
    def _resolve(cls, raw: str) -> str:
        token = raw.strip().lower()
        if not token or token in cls._ANYWHERE:
            return ""
        iso = token.split("/")[-1].strip() if "/" in token else token
        if len(iso) == 2 and iso in cls._COUNTRY_CODES | cls._REGION_CODES:
            return iso
        if token in cls._CITIES:
            return cls._CITIES[token]
        for key, code in cls._COUNTRIES.items():
            if key in token:
                return code
        for key, region in cls._REGIONS.items():
            if key in token:
                return region
        return ""