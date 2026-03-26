import streamlit as st
import folium
from shapely.geometry import shape
from streamlit_folium import st_folium
import tempfile
import pandas as pd

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats

st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("NDVI - Sentinel Hub")

uploaded = st.file_uploader("Upload ZIP SHP or GeoJSON", type=["zip", "geojson"])

if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # BBOX étendue
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    padding = 0.005
    minx -= padding; miny -= padding
    maxx += padding; maxy += padding

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

    # Période d'analyse
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    ndvi_bytes = sentinelhub_ndvi_request(global_geom, time_range)
    if ndvi_bytes is None:
        st.error("NDVI request failed.")
        st.stop()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    gdf = extract_ndvi_stats(gdf, tmp.name)

    def colorize(v):
        if v is None:
            return "#aaaaaa"
        r = int((1 - v) * 255)
        g = int(v * 255)
        return f"#{r:02x}{g:02x}00"

    m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], zoom_start=14)

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

    st_folium(m, height=500)

    rows = [{"Parcelle": i+1, "NDVI": feat["properties"]["NDVI"]}
            for i, feat in enumerate(gdf["features"])]

    df = pd.DataFrame(rows)

    st.dataframe(df)

    st.download_button("Télécharger NDVI (CSV)",
                       df.to_csv(index=False).encode(),
                       "ndvi.csv")
