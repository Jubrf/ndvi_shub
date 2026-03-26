import requests
import streamlit as st

# Token endpoint CDSE
TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

# Process API CDSE
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


def get_sh_token():
    client_id = st.secrets.get("SENTINELHUB_CLIENT_ID")
    client_secret = st.secrets.get("SENTINELHUB_CLIENT_SECRET")

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    r = requests.post(TOKEN_URL, data=payload)

    if r.status_code != 200:
        st.error("❌ Erreur lors de l'obtention du token OAuth2 CDSE")
        st.write("Code HTTP :", r.status_code)
        st.write("Réponse :", r.text)
        return None

    return r.json()["access_token"]


def sentinelhub_ndvi_request(geom, time_range):
    token = get_sh_token()
    if token is None:
        return None

    minx, miny, maxx, maxy = geom.bounds

    evalscript = """
    function setup() {
      return {
        input: ["B04", "B08"],
        output: { id: "default", bands: 1, sampleType: "FLOAT32" }
      };
    }

    function evaluatePixel(s) {
      return [(s.B08 - s.B04) / (s.B08 + s.B04)];
    }
    """

    body = {
        "input": {
            "bounds": {
                "bbox": [minx, miny, maxx, maxy]
            },
            "data": [{
                "type": "S2L2A",
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
            "height": 512,
            "responses": [{
                "identifier": "default",
                "format": {"type": "image/tiff"}
            }]
        },
        "evalscript": evalscript
    }

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(PROCESS_URL, json=body, headers=headers)

    if r.status_code != 200:
        st.error("❌ Erreur Process API CDSE")
        st.write("Code HTTP :", r.status_code)
        st.write("Réponse :", r.text)
        return None

    return r.content
