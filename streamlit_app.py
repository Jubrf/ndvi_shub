import streamlit as st
import folium
from shapely.geometry import shape
from streamlit_folium import st_folium
import tempfile
import pandas as pd
import rasterio
import numpy as np

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats

st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 Analyse NDVI Sentinel Hub (Cloud Mask + Date + Palette Pro)")

uploaded = st.file_uploader(
    "Uploader un ZIP SHP ou un GeoJSON",
    type=["zip", "geojson"]
)

if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX étendue
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    padding = 0.01
    minx -= padding
    miny -= padding
    maxx += padding
    maxy += padding

    bbox_geom = shape({
        "type": "Polygon",
        "coordinates": [[
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny]
        ]]
    })

    # ✅ Période d'analyse
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    st.info("Récupération NDVI et date (Sentinel Hub CDSE)…")
    ndvi_bytes, date_info = sentinelhub_ndvi_request(bbox_geom, time_range)
    if ndvi_bytes is None:
        st.stop()

    # ✅ sauver raster NDVI
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    # ✅ Lire la date depuis le NDVI TIF (dernière date rencontrée)
    with rasterio.open(tmp.name) as src:
        arr = src.read(1)
        # NDVI seulement – la date a été encodée dans un 2e raster normalement, mais on prend la plus récente utilisée
        # Pour être exact → afficher la période analysée
        date_used = f"{time_range[0]} à {time_range[1]}"

    st.success(f"✅ NDVI calculé (période d'analyse : {date_used})")

    # ✅ Zonal statistics
    gdf = extract_ndvi_stats(gdf, tmp.name)

    # ✅ Palette type Kermap
    def colorize(v):
        if v is None:
            return "#cccccc"
        # Palette RdYlGn inversée (style Kermap)
        # v normalisé 0..1
        vv = (v + 1) / 2
        if vv < 0.33:
            return "#d73027"
        elif vv < 0.66:
            return "#fee08b"
        else:
            return "#1a9850"

    m = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], zoom_start=14)

    for i, feat in enumerate(gdf["features"]):
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

    # ✅ Tableau
    rows = [{"Parcelle": i + 1, "NDVI": feat["properties"]["NDVI"]}
            for i, feat in enumerate(gdf["features"])]

    df = pd.DataFrame(rows)
    st.subheader("📊 NDVI par parcelle")
    st.dataframe(df)

    st.download_button(
        "Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi.csv"
    )
