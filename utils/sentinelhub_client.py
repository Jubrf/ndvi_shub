import requests
import streamlit as st
import json

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


def get_sh_token():
    client_id = st.secrets["SENTINELHUB_CLIENT_ID"]
    client_secret = st.secrets["SENTINELHUB_CLIENT_SECRET"]

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


def sentinelhub_ndvi_with_date(geom, time_range):
    token = get_sh_token()
    if token is None:
        return None, None

    minx, miny, maxx, maxy = geom.bounds

    evalscript = """
    function setup() {
      return {
        input: ["B04","B08","SCL","dataMask"],
        output: { bands: 1, sampleType:"FLOAT32" }
      }
    }

    function isBad(scl) {
      return (scl===3 || scl===8 || scl===9 || scl===10 || scl===11);
    }

    function evaluatePixel(s,scene) {
      if (isBad(s.SCL) || s.dataMask===0) {
        return [NaN];
      }
      return [(s.B08 - s.B04) / (s.B08 + s.B04)];
    }
    """

    body = {
        "input": {
            "bounds": { "bbox": [minx,miny,maxx,maxy] },
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
        "processingOptions": {
            "includeMetadata": True
        },
        "output": {
            "width": 1024,
            "height": 1024,
            "responses": [
                { "identifier": "default", "format": {"type":"image/tiff"} }
            ]
        },
        "evalscript": evalscript
    }

    headers = { "Authorization": f"Bearer {token}" }

    r = requests.post(PROCESS_URL, json=body, headers=headers)

    if r.status_code != 200:
        st.warning("⚠️ Process API erreur")
        st.write(r.text)
        return None, None

    ndvi_bytes = r.content

    # ✅ date via header metadata
    metadata = r.headers.get("x-process-metadata")
    sensing_date = None

    if metadata:
        meta = json.loads(metadata)
        try:
            sensing_date = meta["data"][0]["meta"]["sensingTime"]
        except:
            sensing_date = None

    return ndvi_bytes, sensing_date
