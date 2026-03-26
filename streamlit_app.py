import streamlit as st
import folium
import tempfile
import pandas as pd
import datetime
from shapely.geometry import shape
from streamlit_folium import st_folium

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_with_date
from utils.ndvi_processing import extract_single_polygon_ndvi

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 NDVI Sentinel Hub — Parcelle par parcelle + Recherche date auto")

uploaded = st.file_uploader(
    "Uploader un ZIP SHP ou GEOJSON",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# ✅ NOUVEAU : trouver la DERNIERE DATE DISPONIBLE (CDSE)
# -----------------------------------------------------------
def find_latest_available_date(geom, max_days=60):
    """
    Cherche la dernière date réellement disponible dans CDSE,
    en partant de J0 → J-1 → J-2 … jusqu’à 60 jours.
    """
    today = datetime.datetime.utcnow().date()

    st.info("Recherche de la dernière date réellement disponible…")

    for delta in range(0, max_days):
        day = today - datetime.timedelta(days=delta)
        d_from = f"{day}T00:00:00Z"
        d_to   = f"{day}T23:59:59Z"
        time_range = (d_from, d_to)

        st.write(f"🔍 Test date : {day}")

        ndvi_bytes, date_used = sentinelhub_ndvi_with_date(geom, time_range)

        if ndvi_bytes is not None and date_used is not None:
            st.success(f"✅ Date trouvée : {date_used}")
            return date_used

    st.error("❌ Aucune tuile trouvée sur 60 jours.")
    return None


# -----------------------------------------------------------
# ✅ NDVI parcelle par parcelle
# -----------------------------------------------------------
def ndvi_for_parcel(geom, date_str):
    """
    Calcule le NDVI pour une parcelle à UNE date précise.
    """
    d_from = f"{date_str}T00:00:00Z"
    d_to   = f"{date_str}T23:59:59Z"

    ndvi_bytes, _ = sentinelhub_ndvi_with_date(geom, (d_from, d_to))
    if ndvi_bytes is None:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    values = extract_single_polygon_ndvi(tmp.name, geom)
    if len(values) == 0:
        return None

    return float(values.mean())


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX globale pour trouver la date
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    pad = 0.02
    minx -= pad; miny -= pad
    maxx += pad; maxy += pad

    global_bbox = shape({
        "type":"Polygon",
        "coordinates":[[
            [minx,miny],[maxx,miny],
            [maxx,maxy],[minx,maxy],
            [minx,miny]
        ]]
    })

    # ✅ Trouver la date réellement disponible dans CDSE
    date_used = find_latest_available_date(global_bbox)

    if date_used is None:
        st.stop()

    rows = []

    st.info(f"Calcul NDVI parcelle par parcelle pour la date {date_used}…")

    for idx, geom in enumerate(geoms):

        st.write(f"### Parcelle {idx+1}")

        # bbox locale
        minx, miny, maxx, maxy = geom.bounds
        pad = 0.003
        minx -= pad; miny -= pad
        maxx += pad; maxy += pad

        bbox_local = shape({
            "type":"Polygon",
            "coordinates":[[
                [minx,miny],[maxx,miny],
                [maxx,maxy],[minx,maxy],
                [minx,miny]
            ]]
        })

        ndvi_mean = ndvi_for_parcel(bbox_local, date_used)

        rows.append({
            "Parcelle": idx+1,
            "NDVI": ndvi_mean,
            "Date": date_used
        })

    df = pd.DataFrame(rows)
    st.subheader("📊 NDVI par parcelle")
    st.dataframe(df)

    # ✅ Carte NDVI style Kermap
    def colorize(v):
        if v is None: return "#bbbbbb"
        vv = (v+1)/2
        if vv < 0.33: return "#d73027"
        if vv < 0.66: return "#fee08b"
        return "#1a9850"

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=14)

    for i, feat in enumerate(gdf["features"]):
        ndvi = df.iloc[i]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color":"black",
                "weight":1,
                "fillOpacity":0.7
            },
            tooltip=f"Parcelle {i+1} — NDVI={ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    st.download_button(
        "Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi_par_parcelle.csv"
    )
