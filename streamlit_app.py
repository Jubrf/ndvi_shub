# Full code placeholdimport streamlit as st
import folium
from shapely.geometry import shape
from streamlit_folium import st_folium
import tempfile

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_request
from utils.ndvi_processing import extract_ndvi_stats

st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")

st.title("🌱 Analyse NDVI – Sentinel Hub")

uploaded = st.file_uploader("Upload ZIP SHP ou GeoJSON", type=["zip", "geojson"])

if uploaded:
    gdf = load_vector(uploaded)
    st.success(f"{len(gdf['features'])} parcelles chargées ✅")

    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # BBOX globale
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)
    bbox = (minx, miny, maxx, maxy)

    st.write("BBOX :", bbox)

    # Dates
    time_range = ("2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z")

    st.info("Demande NDVI à Sentinel Hub…")

    ndvi_bytes = sentinelhub_ndvi_request(geoms[0], time_range)

    # Sauvegarder NDVI localement
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    st.success("✅ NDVI reçu depuis Sentinel Hub")

    # Zonal statistics
    gdf = extract_ndvi_stats(gdf, tmp.name)

    # Carte NDVI
    st.subheader("🗺️ Carte NDVI")
    m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], zoom_start=13)

    def col(v):
        if v is None: return "#aaaaaa"
        r = int((1 - v) * 255)
        g = int(v * 255)
        return f"#{r:02x}{g:02x}00"

    for feat in gdf["features"]:
        ndvi = feat["properties"]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": col(ndvi),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7
            }
        ).add_to(m)

    st_folium(m, height=600)

    # Tableau
    st.subheader("📊 NDVI par parcelle")
    rows = [{"Parcelle": i+1, "NDVI": f["properties"]["NDVI"]} for i, f in enumerate(gdf["features"])]
    st.dataframe(rows)er
