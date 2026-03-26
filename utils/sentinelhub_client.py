import requests
import streamlit as st

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

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
        st.error("❌ Erreur OAuth2 CDSE")
        st.write(r.text)
        return None

    return r.json()["access_token"]


def sentinelhub_ndvi_request(geom, sensing_date):
    """
    Appelle le Process API CDSE pour une date donnée et une géométrie donnée.
    sensing_date = "2026-03-19T10:40:21Z"
    """

    token = get_sh_token()
    if token is None:
        return None

    minx, miny, maxx, maxy = geom.bounds

    evalscript = """
    function setup() {
      return {
        input: ["B04", "B08", "SCL"],
        output: { id:"default", bands: 1, sampleType: "FLOAT32" }
      };
    }

    function isCloudOrShadow(scl) {
      return (scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11);
    }

    function evaluatePixel(s) {
      if (isCloudOrShadow(s.SCL)) {
        return [NaN];
      }
      let ndvi_val = (s.B08 - s.B04) / (s.B08 + s.B04);
      return [ndvi_val];
    }
    """

    body = {
        "input": {
            "bounds": {"bbox": [minx, miny, maxx, maxy]},
            "data": [{
                "type": "S2L2A",
                "dataFilter": {
                    "timeRange": {
                        "from": sensing_date,
                        "to": sensing_date
                    }
                }
            }]
        },
        "output": {
            "width": 2048,
            "height": 2048,
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
        st.write(r.text)
        return None

    return r.content
