import streamlit as st
import folium
from shapely.geometry import shape
from streamlit_folium import st_folium
import tempfile
import pandas as pd
import rasterio

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats
from utils.sentinelhub_catalog import find_s2_product

st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 NDVI Sentinel Hub – Cloud Mask + Date + Palette Pro")

uploaded = st.file_uploader("Upload ZIP SHP or GeoJSON", type=["zip", "geojson"])

if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX étendue
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    padding = 0.01
    minx -= padding; miny -= padding
    maxx += padding; maxy += padding

    bbox = (minx, miny, maxx, maxy)

    # ✅ Période de recherche
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    st.info("Recherche du dernier produit Sentinel‑2 L2A…")
feature = find_s2_product(bbox, time_range)

if feature is None:
    st.error("❌ Impossible d'obtenir une tuile (serveur/stac down)")
    st.stop()

# ✅ récupération date (toujours présente car feature STAC)
sensing_date = feature["properties"]["datetime"]
st.success(f"✅ Date dernière tuile S2 : {sensing_date}")

    # ✅ Polygone global
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

    st.info("Téléchargement NDVI (avec masque nuages + ombres)…")
    ndvi_bytes = sentinelhub_ndvi_request(global_geom, sensing_date)

    if ndvi_bytes is None:
        st.stop()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    gdf = extract_ndvi_stats(gdf, tmp.name)

    # ✅ Palette "Kermap-like"
    def colorize(v):
        if v is None:
            return "#cccccc"
        vv = (v + 1) / 2
        if vv < 0.33: return "#d73027"
        if vv < 0.66: return "#fee08b"
        return "#1a9850"

    m = folium.Map(location=[(miny + maxy)/2, (minx + maxx)/2], zoom_start=14)

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

    rows = [{"Parcelle": i+1, "NDVI": feat["properties"]["NDVI"]}
            for i, feat in enumerate(gdf["features"])]
    df = pd.DataFrame(rows)

    st.subheader(f"📊 NDVI par parcelle – Image du {sensing_date[:10]}")
    st.dataframe(df)

    st.download_button("Télécharger NDVI (CSV)",
                       df.to_csv(index=False).encode(),
                       "ndvi.csv")
