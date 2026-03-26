import requests
import streamlit as st
from datetime import datetime

# OAuth2 CDSE
TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

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
        st.error("❌ Erreur OAuth2 CDSE")
        st.write("HTTP:", r.status_code)
        st.write("Réponse:", r.text)
        return None

    return r.json()["access_token"]


def sentinelhub_ndvi_request(geom, time_range):
    token = get_sh_token()
    if token is None:
        return None, None

    minx, miny, maxx, maxy = geom.bounds

    # ✅ Mask nuages + ombres (SCL=3,8,9,10,11)
    evalscript = """
    function setup() {
      return {
        input: ["B04", "B08", "SCL", "DATE"],
        output: [
          { id:"ndvi", bands: 1, sampleType: "FLOAT32" },
          { id:"date", bands: 1, sampleType: "UINT32" }
        ]
      };
    }

    function isCloudOrShadow(scl) {
      return (scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11);
    }

    function evaluatePixel(s, scene) {
      // date en format AAAAMMJJ
      let d = new Date(scene.date);
      let dateint = d.getFullYear()*10000 + (d.getMonth()+1)*100 + d.getDate();

      if (isCloudOrShadow(s.SCL)) {
        return {
          ndvi: [NaN],
          date: [dateint]
        };
      }

      let ndvi_val = (s.B08 - s.B04) / (s.B08 + s.B04);
      return {
        ndvi: [ndvi_val],
        date: [dateint]
      };
    }
    """

    body = {
        "input": {
            "bounds": {"bbox": [minx, miny, maxx, maxy]},
            "data": [
                {
                    "type": "S2L2A",
                    "dataFilter": {
                        "timeRange": {
                            "from": time_range[0],
                            "to": time_range[1]
                        }
                    }
                }
            ]
        },
        "output": {
            "width": 2048,
            "height": 2048,
            "responses": [
                {
                    "identifier": "ndvi",
                    "format": {"type": "image/tiff"}
                },
                {
                    "identifier": "date",
                    "format": {"type": "image/tiff"}
                }
            ]
        },
        "evalscript": evalscript
    }

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(PROCESS_URL, json=body, headers=headers)

    if r.status_code != 200:
        st.error("❌ Erreur Process API CDSE")
        st.write("HTTP:", r.status_code)
        st.write("Réponse:", r.text)
        return None, None

    # ✅ réponse multiparts → le NDVI est en première réponse
    return r.content, None
