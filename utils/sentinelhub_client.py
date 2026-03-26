import requests
import streamlit as st
import numpy as np
import rasterio
import tempfile
from datetime import datetime

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

    # ✅ NDVI + masque nuages + ombres 
    # ✅ + extraction date via second output
    evalscript = """
    function setup() {
      return {
        input: ["B04","B08","SCL","dataMask"],
        output: [
          { id:"ndvi", bands:1, sampleType:"FLOAT32" },
          { id:"date", bands:1, sampleType:"UINT32" }
        ]
      }
    }

    function isBad(scl) {
      return (scl===3 || scl===8 || scl===9 || scl===10 || scl===11);
    }

    function evaluatePixel(s,scene) {

      // encode the sensing date as YYYYMMDD integer
      let d = new Date(scene.date);
      let dateint = d.getFullYear()*10000 + (d.getMonth()+1)*100 + d.getDate();

      if (isBad(s.SCL) || s.dataMask===0) {
        return {
          ndvi: [NaN],
          date: [dateint]
        }
      }

      let ndvi_val = (s.B08 - s.B04) / (s.B08 + s.B04);
      return {
        ndvi:[ndvi_val],
        date:[dateint]
      }
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
        "output": {
            "width": 2048,
            "height": 2048,
            "responses": [
                { "identifier": "ndvi", "format": {"type":"image/tiff"} },
                { "identifier": "date", "format": {"type":"image/tiff"} }
            ]
        },
        "evalscript": evalscript
    }

    headers = { "Authorization": f"Bearer {token}" }

    r = requests.post(PROCESS_URL, json=body, headers=headers)
    if r.status_code != 200:
        st.error("❌ Erreur Process API CDSE")
        st.write(r.text)
        return None, None

    # ✅ On reçoit un TIF NDVI et un TIF date dans le même payload
    # Streamlit ne gère que le premier → on télécharge séparément

    ndvi_bytes = r.content

    # ✅ extraire la date via le deuxième fichier
    # On relance avec un seul output "date"
    body_date = body.copy()
    body_date["output"]["responses"] = [
        { "identifier": "date", "format": {"type": "image/tiff"} }
    ]
    r2 = requests.post(PROCESS_URL, json=body_date, headers=headers)

    if r2.status_code != 200:
        st.error("❌ Impossible de récupérer la date")
        return ndvi_bytes, None

    tmp_date = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp_date.write(r2.content)
    tmp_date.close()

    with rasterio.open(tmp_date.name) as src:
        arr = src.read(1)
        vals = arr[arr>0]
        if len(vals)>0:
            date_int = int(np.nanmedian(vals))
            date_str = f"{str(date_int)[0:4]}-{str(date_int)[4:6]}-{str(date_int)[6:8]}"
        else:
            date_str = None

    return ndvi_bytes, date_str
