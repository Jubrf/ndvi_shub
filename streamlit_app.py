import streamlit as st
import folium
import tempfile
import pandas as pd
from shapely.geometry import shape
from streamlit_folium import st_folium

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_with_date
from utils.ndvi_processing import extract_ndvi_stats

st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 NDVI Sentinel Hub – Cloud Mask + Date + Palette Pro")

uploaded = st.file_uploader("Upload ZIP SHP or GeoJSON", type=["zip","geojson"])

if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX globale
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    padding = 0.01
    minx -= padding; miny -= padding
    maxx += padding; maxy += padding

    st.write("✅ BBOX :", (minx,miny,maxx,maxy))

    bbox_geom = shape({
        "type":"Polygon",
        "coordinates":[[
            [minx,miny],[maxx,miny],
            [maxx,maxy],[minx,maxy],
            [minx,miny]
        ]]
    })

    # ✅ période NDVI
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    # ✅ NDVI + date directe via le Process API
    st.info("Récupération NDVI + date via Process API (sans catalogue)…")
    ndvi_bytes, sensing_date = sentinelhub_ndvi_with_date(bbox_geom, time_range)

    if ndvi_bytes is None:
        st.error("Impossible d'obtenir l'image NDVI.")
        st.stop()

    st.success(f"✅ Tuile utilisée : {sensing_date}")

    # Sauvegarde NDVI
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    # ✅ Zonal stats
    gdf = extract_ndvi_stats(gdf, tmp.name)
    st.success("✅ NDVI calculé pour chaque parcelle")

    # ✅ Palette Kermap
    def colorize(v):
        if v is None:
            return "#cccccc"
        vv = (v+1)/2
        if vv < 0.33: return "#d73027"
        if vv < 0.66: return "#fee08b"
        return "#1a9850"

    m = folium.Map(location=[(miny+maxy)/2,(minx+maxx)/2], zoom_start=14)

    for feat in gdf["features"]:
        ndvi = feat["properties"]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color":"black",
                "weight":1,
                "fillOpacity":0.7
            },
            tooltip=f"NDVI = {ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    # ✅ Tableau
    rows = [
        {"Parcelle": i+1, "NDVI": feat["properties"]["NDVI"]}
        for i, feat in enumerate(gdf["features"])
    ]

    df = pd.DataFrame(rows)
    st.subheader(f"📊 NDVI par parcelle – tuile du {sensing_date}")
    st.dataframe(df)

    st.download_button("Télécharger CSV", df.to_csv(index=False).encode(), "ndvi.csv")
