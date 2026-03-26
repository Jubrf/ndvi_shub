import requests
import streamlit as st
import time

CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/search"

def find_s2_product(bbox, time_range):
    """
    Recherche S2 L2A avec :
    ✅ retry 3x
    ✅ pause progressive
    ✅ détection 503/500/HTML
    ✅ fallback propre
    Retourne le feature STAC ou None.
    """

    minx, miny, maxx, maxy = bbox

    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [minx, miny, maxx, maxy],
        "datetime": f"{time_range[0]}/{time_range[1]}",
        "limit": 1,
        "sortby": [{
            "field": "properties.datetime",
            "direction": "desc"
        }]
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):   # ✅ 3 tentatives
        try:
            r = requests.post(CATALOG_URL, json=body, headers=headers, timeout=10)

            # ✅ serveur down
            if r.status_code == 503:
                st.warning(f"Catalogue CDSE indisponible (503). Tentative {attempt+1}/3…")
                time.sleep(1 + attempt)  # pause progressive
                continue

            # ✅ bizarre → renvoie HTML
            if "text/html" in r.headers.get("Content-Type", ""):
                st.warning(f"Catalogue CDSE renvoie du HTML. Tentative {attempt+1}/3…")
                time.sleep(1 + attempt)
                continue

            # ✅ autre erreur
            if r.status_code != 200:
                st.warning(f"Erreur catalogue CDSE (HTTP {r.status_code}). Tentative {attempt+1}/3…")
                time.sleep(1 + attempt)
                continue

            # ✅ OK → JSON
            data = r.json()
            if "features" in data and len(data["features"]) > 0:
                return data["features"][0]

            # ✅ aucune tuile trouvée → inutile de réessayer
            return None

        except Exception as e:
            st.warning(f"Erreur réseau catalogue : {e}. Tentative {attempt+1}/3…")
            time.sleep(1 + attempt)

    # ✅ après 3 tentatives
    st.error("❌ Catalogue CDSE indisponible après 3 tentatives.")
    return None
