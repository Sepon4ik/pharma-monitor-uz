"""ArzonApteka API client.

Discovered endpoints:
- POST /api/v4/{lang}/trigrams (FormData) — text search, returns product catalog
- POST /api/v4/{lang}/search (JSON) — pharmacy/price data by medicine IDs
- GET  /api/v4/{lang}/pharmacies — list of all pharmacies
"""

import time
import httpx
from ..config import API_BASE_URL, SITE_ORIGIN, make_api_key

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": SITE_ORIGIN,
    "Referer": f"{SITE_ORIGIN}/",
}


class ArzonAptekaClient:
    def __init__(self, lang: str = "ru"):
        self.lang = lang
        self.client = httpx.Client(timeout=60, headers=DEFAULT_HEADERS)

    def _endpoint(self, path: str) -> str:
        return f"/api/v4/{self.lang}/{path}"

    def _headers_for(self, endpoint: str) -> dict:
        return {**DEFAULT_HEADERS, "Api-Key": make_api_key(endpoint)}

    def trigram_search(self, query: str) -> list[dict]:
        """Text search — returns list of products with IDs."""
        endpoint = self._endpoint("trigrams")
        resp = self.client.post(
            f"{API_BASE_URL}{endpoint}",
            data={
                "user": "pharma-monitor",
                "search": query,
                "region": "-3",
                "country_code": "1",
                "detail": "true",
                "platform": "web",
            },
            headers=self._headers_for(endpoint),
        )
        data = resp.json()
        if data.get("ok"):
            return data["result"] if isinstance(data["result"], list) else []
        return []

    def search_by_ids(self, medicine_ids: list[str], region: str = "-3") -> dict:
        """Get pharmacy/price data for given medicine IDs."""
        endpoint = self._endpoint("search")
        resp = self.client.post(
            f"{API_BASE_URL}{endpoint}",
            json={
                "country_code": "1",
                "platform": "web",
                "region": region,
                "search": medicine_ids,
                "user": "pharma-monitor",
            },
            headers={
                **self._headers_for(endpoint),
                "Content-Type": "application/json",
            },
        )
        data = resp.json()
        if data.get("ok"):
            return data["result"]
        return {}

    def get_pharmacies(self) -> list[dict]:
        """Get list of all pharmacies."""
        endpoint = self._endpoint("pharmacies")
        resp = self.client.get(
            f"{API_BASE_URL}{endpoint}",
            headers=self._headers_for(endpoint),
        )
        data = resp.json()
        if data.get("ok"):
            return data["result"].get("result", [])
        return []

    def discover_products(self, queries: list[str]) -> dict[str, dict]:
        """Discover all products matching given search queries."""
        all_products = {}
        for query in queries:
            products = self.trigram_search(query)
            for prod in products:
                pid = str(prod["id"])
                if pid not in all_products:
                    all_products[pid] = {
                        "id": pid,
                        "name": prod.get("name", ""),
                        "fullname": prod.get("fullname", ""),
                        "vendor": prod.get("vendor", ""),
                        "country": prod.get("country", ""),
                        "photo_url": prod.get("photo_url", ""),
                    }
            time.sleep(0.3)
        return all_products

    def get_prices_for_products(self, medicine_ids: list[str], batch_size: int = 30) -> list[dict]:
        """Get pharmacy data for products, returns flat list of observations."""
        observations = []
        for i in range(0, len(medicine_ids), batch_size):
            batch = medicine_ids[i:i + batch_size]
            result = self.search_by_ids(batch)
            drugstores = result.get("drugstores", [])
            for ds in drugstores:
                for drug in ds.get("drugs", []):
                    observations.append({
                        "pharmacy_id": ds["org_id"],
                        "pharmacy_name": ds["org_name"],
                        "pharmacy_address": ds.get("address", ""),
                        "pharmacy_lat": ds.get("lat_c", ""),
                        "pharmacy_lon": ds.get("long_c", ""),
                        "pharmacy_region": ds.get("region2", ""),
                        "pharmacy_phone": ds.get("phone", ""),
                        "good_id": drug["good_id"],
                        "good_name": drug["good_name"],
                        "vendor_name": drug.get("vendor_name", ""),
                        "vendor_country": drug.get("vendor_country", ""),
                        "price": int(drug.get("price", 0)),
                        "count": int(drug.get("count", 0)),
                        "last_update": drug.get("last_update", ""),
                    })
            time.sleep(0.5)
        return observations

    def close(self):
        self.client.close()
