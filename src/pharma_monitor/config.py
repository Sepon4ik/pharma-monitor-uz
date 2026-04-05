"""Application configuration."""

import hashlib
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "pharma_monitor.db"

# ArzonApteka API
API_BASE_URL = "https://api.arzonapteka.name"
API_SECRET = os.environ.get("ARZON_API_SECRET", "Nx3WWr")
SITE_ORIGIN = "https://arzonapteka.uz"

# Tracked brands (display_name -> search queries for trigrams)
TRACKED_BRANDS = {
    "Prolife": ["prolife"],
    "OMRON": ["omron"],
    "Microlife": ["microlife"],
    "B.Well": ["b.well", "b. well"],
    "Beurer": ["beurer"],
    "Rossmax": ["rossmax"],
    "Little Doctor": ["little doctor"],
    "A&D": ["a&d", "a and d company", "a and d "],
    "Citizen": ["citizen"],
    "YUWELL": ["yuwell"],
    "KD Medical": ["kd medical", "kd-meter", "kd-scope"],
    "Amrus": ["amrus"],
    "CS Medica": ["cs medica"],
    "Accu-Chek": ["accu-chek", "accu chek"],
    "OneTouch": ["onetouch", "one touch", "lifescan"],
    "Dr.Frei": ["dr.frei", "dr frei"],
    "MediTech": ["meditech"],
    "Braun": ["braun"],
    "Medico": ["medico"],
    "iHealth": ["ihealth"],
}

# Categories for grouping products
DEVICE_CATEGORIES = {
    "tonometer": ["тонометр", "давлен", "blood pressure"],
    "nebulizer": ["небулайзер", "ингалятор", "nebulizer", "inhaler"],
    "thermometer": ["термометр", "thermometer"],
    "glucometer": ["глюкометр", "тест-полоск"],
    "oximeter": ["пульсоксиметр", "oximeter"],
    "stethoscope": ["стетоскоп", "фонендоскоп"],
    "accessory": ["манжет", "маска для", "мундштук"],
}


# Known pharmacy chains — pattern -> display name
PHARMACY_CHAINS = {
    "шамс дорихона": "Шамс Дорихона",
    "vaksina": "Vaksina",
    "city pharm": "City Pharm",
    "navbahor apteka": "Navbahor Apteka",
    "+03": "03 Аптека",
    "ноль три": "03 Аптека",
    "pul`s farm": "Puls Farm",
    "puls farm": "Puls Farm",
    "shafran": "Shafran",
    "oriyo": "Oriyo-Mehr",
    "marjon farm": "Marjon Farm Trade",
    "biotek farm": "Biotek Farm",
    "farmakov": "Farmakov",
    "dotz pharm": "Dotz Pharm",
    "шохфарм": "Шохфарм",
    "easy pharm": "Easy Pharm",
    "eco pharma": "Eco Pharma",
    "pharzam": "Pharzam Pharm",
    "гармония фарм": "Гармония Фарм",
    "spharma": "SpharmA",
    "olam pharm": "Olam Pharm",
    "аптек д5": "Д5",
    "aero pharm": "Aero Pharm",
    "dehkon dorixona": "Dehkon Dorixona",
    "uni pharm": "Uni Pharm",
    "ok pharm": "OK Pharm",
    "зам зам": "Зам Зам Фарм",
    "top pharm": "Top Pharm",
    "дори таъминоти": "Дори Таъминоти",
    "amir pharmacy": "Amir Pharmacy",
    "mega farm": "Mega Farm",
    "шифобахш": "Шифобахш",
    "ifor pharma": "Ifor Pharma",
    "doc.pharm": "Doc.Pharm",
    "неболейка": "Неболейка",
    "5+": "5+",
    "farm turkiston": "Farm Turkiston",
    "millenium": "Millenium Medikal",
    "econom apteka": "Econom Apteka",
    "oxymed": "OXYmed",
    "nurvita": "Nurvita Pharm",
    "cardinal pharm": "Cardinal Pharm",
    "pharma pulse": "Pharma Pulse",
    "5555 pharm": "5555 Pharm",
}


def detect_chain(pharmacy_name: str) -> str:
    """Detect pharmacy chain from name. Returns chain name or 'Independent'."""
    name_lower = pharmacy_name.lower()
    for pattern, chain_name in PHARMACY_CHAINS.items():
        if pattern in name_lower:
            return chain_name
    return "Independent"


def make_api_key(endpoint: str) -> str:
    """Generate API key: md5(BASE_URL + endpoint + SECRET)."""
    raw = f"{API_BASE_URL}{endpoint}{API_SECRET}"
    return hashlib.md5(raw.encode()).hexdigest()


def classify_product(name: str) -> str:
    """Classify product into a category based on its name."""
    name_lower = name.lower()
    for category, keywords in DEVICE_CATEGORIES.items():
        if any(kw in name_lower for kw in keywords):
            return category
    return "other"


def detect_brand(name: str, vendor: str) -> str:
    """Detect brand from product name and vendor."""
    text = f"{name} {vendor}".lower()
    for brand, queries in TRACKED_BRANDS.items():
        if any(q in text for q in queries):
            return brand
    return "Other"
