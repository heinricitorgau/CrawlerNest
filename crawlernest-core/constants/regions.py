"""
Regional groupings, country name aliases, and university country hints.
"""

from typing import Dict

# Regional country groupings
REGION_COUNTRIES: Dict[str, set[str]] = {
    "Asia": {
        "China (Mainland)", "Hong Kong SAR", "Taiwan", "Japan", "South Korea",
        "Singapore", "Malaysia", "Thailand", "Indonesia", "Philippines", "Vietnam",
        "India", "Pakistan", "Bangladesh", "Sri Lanka", "Kazakhstan", "Mongolia",
        "Brunei", "Cambodia", "Laos", "Myanmar", "Nepal", "Bhutan",
    },
    "Europe": {
        "United Kingdom", "Ireland", "France", "Germany", "Netherlands", "Belgium",
        "Switzerland", "Austria", "Italy", "Spain", "Portugal", "Sweden", "Norway",
        "Denmark", "Finland", "Poland", "Czech Republic", "Hungary", "Greece",
        "Romania", "Bulgaria", "Serbia", "Croatia", "Slovenia", "Slovakia",
        "Ukraine", "Russia", "Estonia", "Latvia", "Lithuania", "Iceland",
    },
    "Arab Region": {
        "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain",
        "Egypt", "Jordan", "Lebanon", "Iraq", "Morocco", "Tunisia", "Algeria",
        "Palestine", "Sudan", "Yemen", "Syria", "Libya",
    },
    "Latin America & Caribbean": {
        "Brazil", "Mexico", "Argentina", "Chile", "Colombia", "Peru", "Ecuador",
        "Uruguay", "Paraguay", "Bolivia", "Venezuela", "Costa Rica", "Panama",
        "Guatemala", "Dominican Republic", "Cuba", "Jamaica",
    },
    "Latin America": {
        "Brazil", "Mexico", "Argentina", "Chile", "Colombia", "Peru", "Ecuador",
        "Uruguay", "Paraguay", "Bolivia", "Venezuela", "Costa Rica", "Panama",
        "Guatemala", "Dominican Republic", "Cuba", "Jamaica",
    },
    "Middle East & Africa": {
        "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain",
        "Egypt", "Jordan", "Lebanon", "Iraq", "Morocco", "Tunisia", "Algeria",
        "Palestine", "Sudan", "Yemen", "Syria", "Libya", "South Africa", "Nigeria",
        "Kenya", "Ghana", "Uganda", "Tanzania", "Ethiopia", "Senegal", "Turkey", "Israel",
        "Türkiye", "Iran", "Cyprus",
    },
    "Middle East": {
        "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain",
        "Egypt", "Jordan", "Lebanon", "Iraq", "Palestine", "Yemen", "Syria", "Turkey", "Israel",
        "Türkiye", "Iran", "Cyprus", "Morocco", "Tunisia", "Algeria", "Sudan", "Libya",
    },
    "Africa": {
        "Egypt", "Morocco", "Tunisia", "Algeria", "Sudan", "Libya", "South Africa", "Nigeria",
        "Kenya", "Ghana", "Uganda", "Tanzania", "Ethiopia", "Senegal",
    },
    "North America": {
        "United States", "US", "USA", "Canada",
    },
    "Oceania": {
        "Australia", "New Zealand", "Fiji", "Papua New Guinea",
    },
    "United States": {
        "United States", "US", "USA",
    },
    "Canada": {
        "Canada",
    },
    "Emerging Europe & Central Asia (EECA)": {
        "Russia", "Ukraine", "Kazakhstan", "Georgia", "Armenia", "Azerbaijan",
        "Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan", "Belarus",
        "Moldova",
    },
    "Central Asia": {
        "Kazakhstan", "Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan",
    },
    "Southern Asia": {
        "India", "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan", "Afghanistan",
    },
    "Eastern Asia": {
        "China (Mainland)", "Hong Kong SAR", "Taiwan", "Japan", "South Korea", "Mongolia",
    },
    "South-eastern Asia": {
        "Singapore", "Malaysia", "Thailand", "Indonesia", "Philippines", "Vietnam",
        "Brunei", "Cambodia", "Laos", "Myanmar",
    },
    "The Caribbean": {
        "Jamaica", "Cuba", "Dominican Republic", "Trinidad and Tobago", "Barbados", "Puerto Rico", "Grenada",
    },
    "Central America": {
        "Mexico", "Costa Rica", "Panama", "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Belize",
    },
    "South America": {
        "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador", "Paraguay", "Peru",
        "Uruguay", "Venezuela", "Guyana", "Suriname",
    },
    "Northern Europe": {
        "Sweden", "Norway", "Denmark", "Finland", "Iceland",       
    },
    "Western Europe": {
       "United Kingdom", "Ireland", "France", "Germany", "Netherlands", "Belgium", "Luxembourg", "Switzerland", "Austria",
    },
    "Eastern Europe": {
        "Poland", "Czech Republic", "Hungary", "Romania", "Bulgaria", "Slovakia", "Slovenia",
        "Croatia", "Serbia", "Ukraine", "Belarus", "Moldova", "Russia", "Estonia", "Latvia", "Lithuania", "Malta", "Croatia", "Slovenia", "Serbia",
        "Bosnia and Herzegovina", "Montenegro", "Albania", "North Macedonia",
    },
    "Western Asia": {
        "Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain",
        "Jordan", "Lebanon", "Iraq", "Israel", "Türkiye", "Turkey", "Iran", "Cyprus",
    },
    "Southern Europe": {
        "Italy", "Spain", "Portugal", "Greece",
    },
}

# Country name aliases for normalization
COUNTRY_NAME_ALIASES: Dict[str, str] = {
    "trinidad and tobago": "trinidad & tobago",
    "turkiye": "turkey",
    "kz": "kazakhstan",
    "kg": "kyrgyzstan",
    "uz": "uzbekistan",
    "tj": "tajikistan",
    "tm": "turkmenistan",
    "hk": "hong kong sar",
    "kr": "south korea",
    "jp": "japan",
    "cn": "china (mainland)",
    "tw": "taiwan",
    "gb": "united kingdom",
    "uk": "united kingdom",
    "us": "united states",
    "ae": "united arab emirates",
    "kyrgyz republic": "kyrgyzstan",
    "republic of kazakhstan": "kazakhstan",
    "republic of uzbekistan": "uzbekistan",
    "people's republic of china": "china (mainland)",
    "china mainland": "china (mainland)",
    "iran, islamic republic of": "iran",
    "united arab emirates (uae)": "united arab emirates",
    "uae": "united arab emirates",
    "ksa": "saudi arabia",
    "syrian arab republic": "syria",
    "state of palestine": "palestine",
    "republic of turkey": "turkey",
    "turkey (turkiye)": "turkey",
}

# Country slug aliases for URL matching
COUNTRY_SLUG_ALIASES: Dict[str, str] = {
    "kazakhstan": "kazakhstan",
    "kyrgyzstan": "kyrgyzstan",
    "uzbekistan": "uzbekistan",
    "tajikistan": "tajikistan",
    "turkmenistan": "turkmenistan",
    "mexico": "mexico",
    "costa rica": "costa rica",
    "panama": "panama",
    "guatemala": "guatemala",
    "honduras": "honduras",
    "el salvador": "el salvador",
    "nicaragua": "nicaragua",
    "belize": "belize",
    "puerto rico": "puerto rico",
    "cuba": "cuba",
    "dominican republic": "dominican republic",
    "trinidad tobago": "trinidad and tobago",
    "trinidad and tobago": "trinidad and tobago",
    "jamaica": "jamaica",
    "grenada": "grenada",
    "barbados": "barbados",
    "argentina": "argentina",
    "bolivia": "bolivia",
    "brazil": "brazil",
    "chile": "chile",
    "colombia": "colombia",
    "ecuador": "ecuador",
    "paraguay": "paraguay",
    "peru": "peru",
    "uruguay": "uruguay",
    "venezuela": "venezuela",
    "guyana": "guyana",
    "suriname": "suriname",
    "saudi arabia": "saudi arabia",
    "united arab emirates": "united arab emirates",
    "qatar": "qatar",
    "kuwait": "kuwait",
    "oman": "oman",
    "bahrain": "bahrain",
    "jordan": "jordan",
    "lebanon": "lebanon",
    "iraq": "iraq",
    "israel": "israel",
    "turkiye": "turkey",
    "turkey": "turkey",
    "iran": "iran",
    "cyprus": "cyprus",
}

# University-specific country hints
UNIVERSITY_COUNTRY_HINTS: Dict[str, str] = {
    "astana international university": "kazakhstan",
    "atyrau oil and gas university named after safi utebayev": "kazakhstan",
}
