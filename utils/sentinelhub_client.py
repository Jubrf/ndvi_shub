import requests
import streamlit as st
from shapely.geometry import mapping

# Sentinel Hub endpoints
TOKEN_URL = "https://services.sentinel-hub.com/oauth/token"
PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"


def get_sh_token():
    """
    Récupère le token Sentinel Hub via OAuth2.
    """
    client_id = st.secrets.get("SENTINELHUB_CLIENT_ID")
    client_secret = st.secrets.get("SENTINELHUB_CLIENT_SECRET")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    r = requests.post(TOKEN_URL, data=payload)
    r.raise_for_status()

    return r.json()["access_token"]


def sentinelhub_ndvi_request(geom, time_range):
    """
    Appel Sentinel Hub Process API pour générer du NDVI.
    geom : géométrie Shapely
    """

    token = get_sh_token()

    evalscript = """
    // NDVI = (NIR - RED) / (NIR + RED)
    // B08 = NIR ; B04 = RED
    function setup() {
      return {
        input: ["B04", "B08"],
        output: { bands: 1, sampleType: "FLOAT32" }
      };
    }

    function evaluatePixel(sample) {
      return [ (sample.B08 - sample.B04) / (sample.B08 + sample.B04) ];
    }
    """

    bbox = geometry_to_bbox(geom)

    body = {
        "input": {
            "bounds": {
                "bbox": bbox
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {
                        "from": time_range[0],
                        "to": time_range[1]
                    }
                }
            }]
        },
        "output": {
            "width": 512,
            "height": 512
        },
        "evalscript": evalscript
    }

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(PROCESS_URL, headers=headers, json=body)
    r.raise_for_status()

    return r.content  # GeoTIFF NDVI


def geometry_to_bbox(geom):
    """
    Convertit une géométrie Shapely en bounding box [minx, miny, maxx, maxy]
    """
    minx, miny, maxx, maxy = geom.bounds
    return [minx, miny, maxx, maxy]
