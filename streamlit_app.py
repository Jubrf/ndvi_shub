import streamlit as st
import folium
import tempfile
import pandas as pd
from shapely.geometry import shape
from streamlit_folium import st_folium
import rasterio
import numpy as np

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats
from utils.sentinelhub_catalog import find_s2_product   # ✅ version robuste

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 NDVI Sentinel Hub – Masque Nuages + Date Tuile + Palette Pro")

uploaded = st.file_uploader(
    "Uploader un fichier : ZIP SHP ou GEOJSON",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if uploaded:

    # ✅ Lecture du fichier
    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX globale
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    padding = 0.01    # ≈ 1 km autour
    minx -= padding
    miny -= padding
    maxx += padding
    maxy += padding

    st.write("✅ BBOX élargie :", (minx, miny, maxx, maxy))

    bbox = (minx, miny, maxx, maxy)

    # ✅ Fenêtre temporelle
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    # -----------------------------------------------------------
    # ✅ Recherche tuile Sentinel-2 L2A (avec retry + anti-503)
    # -----------------------------------------------------------
    st.info("Recherche de la dernière tuile Sentinel‑2 L2A…")

    feature = find_s2_product(bbox, time_range)

    if feature is None:
        st.error("❌ Impossible de récupérer une tuile (catalogue CDSE indisponible).")
        st.stop()

    # ✅ Date réelle de la tuile
    sensing_date = feature["properties"]["datetime"]
    st.success(f"✅ Tuile la plus récente : {sensing_date}")

    # -----------------------------------------------------------
    # ✅ NDVI avec masque nuages + ombres
    # -----------------------------------------------------------
    st.info("Récupération NDVI (masque nuages + ombres SCL)…")

    # Construction polygone global pour l'appel
    global_geom = shape({
        "type": "Polygon",
        "coordinates": [[
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny]
        ]]
    })

    ndvi_bytes = sentinelhub_ndvi_request(global_geom, sensing_date)

    if ndvi_bytes is None:
        st.error("❌ Erreur NDVI sur Process API CDSE.")
        st.stop()

    # Sauvegarde NDVI
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    # -----------------------------------------------------------
    # ✅ Zonal stats NDVI parcelle par parcelle
    # -----------------------------------------------------------
    st.info("Calcul NDVI moyen par parcelle…")
    gdf = extract_ndvi_stats(gdf, tmp.name)
    st.success("✅ NDVI calculé")

    # -----------------------------------------------------------
    # ✅ Carte NDVI avec palette type Kermap
    # -----------------------------------------------------------
    st.subheader("🗺️ Carte NDVI (palette pro)")

    def colorize(v):
        if v is None:
            return "#cccccc"
        vv = (v + 1) / 2     # normalisation [-1,1] → [0,1]
        if vv < 0.33:
            return "#d73027"     # rouge
        if vv < 0.66:
            return "#fee08b"     # jaune
        return "#1a9850"         # vert

    center_lat = (miny + maxy) / 2
    center_lon = (minx + maxx) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)

    for feat in gdf["features"]:
        ndvi = feat["properties"]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7
            },
            tooltip=f"NDVI = {ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    # -----------------------------------------------------------
    # ✅ Tableau NDVI + date tuile
    # -----------------------------------------------------------
    st.subheader(f"📊 NDVI par parcelle – Tuile du {sensing_date[:10]}")

    rows = [
        {"Parcelle": i + 1, "NDVI": feat["properties"]["NDVI"]}
        for i, feat in enumerate(gdf["features"])
    ]

    df = pd.DataFrame(rows)
    st.dataframe(df)

    # ✅ Export CSV
    st.download_button(
        "Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi.csv"
    )
