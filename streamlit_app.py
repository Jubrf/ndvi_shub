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
st.title("🌱 NDVI Sentinel Hub — Parcelle par parcelle + Fallback multi-dates + Masque nuages")

uploaded = st.file_uploader(
    "Uploader un fichier : ZIP SHP ou GEOJSON",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# ✅ FALLBACK NDVI PAR PARCELLE (STYLE KERMAP)
# -----------------------------------------------------------
def fallback_ndvi_for_parcel(geom, max_days=30, step=3):
    """
    Calcule le NDVI pour UNE parcelle avec fallback :
    J0, J-3, J-6, …, jusqu'à max_days.
    Retourne : (ndvi_mean, sensing_date)
    """

    today = datetime.datetime.utcnow().date()

    for delta in range(0, max_days, step):

        day_from = today - datetime.timedelta(days=delta + step)
        day_to   = today - datetime.timedelta(days=delta)

        time_range = (
            f"{day_from.strftime('%Y-%m-%d')}T00:00:00Z",
            f"{day_to.strftime('%Y-%m-%d')}T23:59:59Z"
        )

        st.write(f"🔎 Parcelle : période testée {time_range[0]} → {time_range[1]}")

        ndvi_bytes, sensing_date = sentinelhub_ndvi_with_date(geom, time_range)

        if ndvi_bytes is None:
            st.warning("⏳ Aucune donnée NDVI exploitable dans cette fenêtre.")
            continue

        # Sauvegarde du raster NDVI
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
        tmp.write(ndvi_bytes)
        tmp.close()

        # NDVI moyens sur la parcelle
        values = extract_single_polygon_ndvi(tmp.name, geom)

        if len(values) > 0:
            ndvi_mean = float(values.mean())
            st.success(f"✅ NDVI trouvé pour {sensing_date}")
            return ndvi_mean, sensing_date

        st.warning("🟨 NDVI vide (nuages/ombres). On remonte dans le temps…")

    st.error("❌ Pas de NDVI utilisable jusqu'à J-30.")
    return None, None


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    st.info("Analyse NDVI parcelle par parcelle (fallback multi-dates)…")

    rows = []
    all_dates = []

    for idx, geom in enumerate(geoms):

        st.write(f"### Parcelle {idx+1}")

        # ✅ BBOX locale étendue
        minx, miny, maxx, maxy = geom.bounds
        padding = 0.003    # ~300 m autour
        minx -= padding; miny -= padding
        maxx += padding; maxy += padding

        local_bbox = shape({
            "type": "Polygon",
            "coordinates": [[
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny]
            ]]
        })

        # ✅ NDVI + date avec fallback
        ndvi_mean, sensing_date = fallback_ndvi_for_parcel(local_bbox)

        rows.append({
            "Parcelle": idx + 1,
            "NDVI": ndvi_mean,
            "Date": sensing_date
        })
        all_dates.append(sensing_date)

    # -----------------------------------------------------------
    # ✅ DataFrame final
    # -----------------------------------------------------------
    df = pd.DataFrame(rows)

    st.subheader("📊 Résultats NDVI par parcelle")
    st.dataframe(df)

    # -----------------------------------------------------------
    # ✅ Carte NDVI (palette Kermap)
    # -----------------------------------------------------------
    st.subheader("🗺️ Carte NDVI — palette Kermap")

    def colorize(v):
        if v is None:
            return "#bbbbbb"
        vv = (v + 1) / 2
        if vv < 0.33: return "#d73027"
        if vv < 0.66: return "#fee08b"
        return "#1a9850"

    # BBOX globale pour le centrage
    global_minx = min(shape(f["geometry"]).bounds[0] for f in gdf["features"])
    global_miny = min(shape(f["geometry"]).bounds[1] for f in gdf["features"])
    global_maxx = max(shape(f["geometry"]).bounds[2] for f in gdf["features"])
    global_maxy = max(shape(f["geometry"]).bounds[3] for f in gdf["features"])

    center_lat = (global_miny + global_maxy) / 2
    center_lon = (global_minx + global_maxx) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)

    # Ajouter les parcelles à la carte
    for i, feat in enumerate(gdf["features"]):
        ndvi = df.iloc[i]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7,
            },
            tooltip=f"Parcelle {i+1} — NDVI = {ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    # -----------------------------------------------------------
    # ✅ Export CSV final
    # -----------------------------------------------------------
    st.download_button(
        "📥 Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi_par_parcelle.csv"
    )
