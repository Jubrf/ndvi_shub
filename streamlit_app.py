import streamlit as st
import folium
from shapely.geometry import shape
from streamlit_folium import st_folium
import tempfile
import pandas as pd

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 Analyse NDVI – Sentinel Hub")

# DEBUG secrets (à supprimer ensuite)
st.write("DEBUG CLIENT_ID =", st.secrets.get("SENTINELHUB_CLIENT_ID"))
st.write("DEBUG SECRET LENGTH =", len(st.secrets.get("SENTINELHUB_CLIENT_SECRET", "")))

uploaded = st.file_uploader(
    "Uploader vos parcelles (ZIP SHP ou GeoJSON)",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# MAIN LOGIC
# -----------------------------------------------------------
if uploaded:

    st.info("Lecture du fichier vecteur…")
    gdf = load_vector(uploaded)
    st.success(f"{len(gdf['features'])} parcelles chargées ✅")

    # Extraction des géométries Shapely
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ---------------------------------------------------
    # ✅ BBOX GLOBALE pour couvrir TOUTES les parcelles
    # ---------------------------------------------------
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    st.write("✅ BBOX globale :", (minx, miny, maxx, maxy))

    # Construction du polygone global
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

    # -----------------------------------------------------------
    # ✅ Fenêtre temporelle NDVI
    # (à mettre dynamique après si tu veux un date-picker)
    # -----------------------------------------------------------
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    st.info("Demande NDVI à Sentinel Hub…")
    ndvi_bytes = sentinelhub_ndvi_request(global_geom, time_range)

    if ndvi_bytes is None:
        st.error("❌ Impossible d'obtenir le NDVI depuis Sentinel Hub.")
        st.stop()

    # Sauvegarde du NDVI localement
    ndvi_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    ndvi_tmp.write(ndvi_bytes)
    ndvi_tmp.close()

    st.success("✅ NDVI reçu depuis Sentinel Hub")

    # -----------------------------------------------------------
    # ✅ NDVI moyen par parcelle (zonal statistics)
    # -----------------------------------------------------------
    st.info("Calcul NDVI moyen par parcelle…")
    gdf = extract_ndvi_stats(gdf, ndvi_tmp.name)
    st.success("✅ NDVI calculé pour toutes les parcelles")

    # -----------------------------------------------------------
    # ✅ CARTE NDVI
    # -----------------------------------------------------------
    st.subheader("🗺️ Carte NDVI")

    def colorize(v):
        if v is None:
            return "#aaaaaa"
        r = int((1 - v) * 255)
        g = int(v * 255)
        return f"#{r:02x}{g:02x}00"

    # Centre de la carte
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
    tooltip=f"NDVI : {ndvi}"
).add_to(m)

    st_folium(m, height=600)

    # -----------------------------------------------------------
    # ✅ TABLEAU NDVI
    # -----------------------------------------------------------
    st.subheader("📊 NDVI par parcelle")

    rows = [
        {"Parcelle": i + 1, "NDVI": feat["properties"]["NDVI"]}
        for i, feat in enumerate(gdf["features"])
    ]

    st.dataframe(rows)

    # -----------------------------------------------------------
    # ✅ EXPORT CSV
    # -----------------------------------------------------------
    df = pd.DataFrame(rows)

    st.download_button(
        "Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi.csv"
    )
