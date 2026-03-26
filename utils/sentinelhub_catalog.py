import requests
import streamlit as st

CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/search"


def find_s2_product(bbox, time_range):
    """
    Recherche la dernière tuile Sentinel‑2 L2A dans le catalogue CDSE.
    Retourne la feature STAC complète.
    """

    minx, miny, maxx, maxy = bbox

    user = st.secrets.get("SENTINELHUB_CLIENT_ID")
    pwd = st.secrets.get("SENTINELHUB_CLIENT_SECRET")

    headers = {
        "Content-Type": "application/json"
    }

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

    r = requests.post(CATALOG_URL, json=body, headers=headers)

    if r.status_code != 200:
        st.error("Erreur catalogue CDSE")
        st.write(r.text)
        return None

    data = r.json()

    if "features" not in data or len(data["features"]) == 0:
        return None

    return data["features"][0]
