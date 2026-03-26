import streamlit as st
import folium
import tempfile
import pandas as pd
import datetime
from shapely.geometry import shape
from streamlit_folium import st_folium

from utils.vector_io import load_vector
from utils.sentinelhub_client import sentinelhub_ndvi_with_date
from utils.ndvi_processing import extract_ndvi_stats

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
st.set_page_config(page_title="NDVI Sentinel Hub", layout="wide")
st.title("🌱 NDVI Sentinel Hub — Fallback multi-dates + Masque nuages + Date")

uploaded = st.file_uploader(
    "Uploader un fichier : ZIP SHP ou GEOJSON",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# ✅ FALLBACK MULTI-DATES STYLE KERMAP
# -----------------------------------------------------------
def fallback_best_ndvi(geom, max_days=30, step=3):
    """
    Fallback NDVI : teste J0, J-3, J-6, … jusqu’à max_days.
    Retourne (ndvi_bytes, date_str) ou (None, None).
    """

    today = datetime.datetime.utcnow().date()

    for delta in range(0, max_days, step):

        day_from = today - datetime.timedelta(days=delta+step)
        day_to   = today - datetime.timedelta(days=delta)

        time_range = (
            f"{day_from.strftime('%Y-%m-%d')}T00:00:00Z",
            f"{day_to.strftime('%Y-%m-%d')}T23:59:59Z"
        )

        st.write(f"🔍 Essai {delta//step + 1} : période {time_range[0]} → {time_range[1]}")

        ndvi_bytes, sensing_date = sentinelhub_ndvi_with_date(geom, time_range)

        if ndvi_bytes is not None and sensing_date is not None:
            st.success(f"✅ NDVI trouvé pour la date : {sensing_date}")
            return ndvi_bytes, sensing_date

        st.warning("❌ Aucun NDVI exploitable sur cette période, on remonte dans le temps…")

    st.error("❌ Aucune tuile exploitable jusqu'à J-30.")
    return None, None


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if uploaded:

    # ✅ Charger les parcelles
    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    # ✅ BBOX globale étendue
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

    st.write("✅ BBOX utilisée :", (minx, miny, maxx, maxy))

    # ✅ NDVI via fallback multi-dates
    st.info("Recherche NDVI via fallback multi-dates…")
    ndvi_bytes, sensing_date = fallback_best_ndvi(bbox_geom)

    if ndvi_bytes is None:
        st.stop()

    st.success(f"✅ Tuile utilisée : {sensing_date}")

    # ✅ Sauvegarder le TIFF
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
    tmp.write(ndvi_bytes)
    tmp.close()

    # ✅ Zonal stats
    st.info("Calcul NDVI moyen par parcelle…")
    gdf = extract_ndvi_stats(gdf, tmp.name)
    st.success("✅ NDVI terminé")

    # -----------------------------------------------------------
    # ✅ Carte NDVI (palette style Kermap)
    # -----------------------------------------------------------
    st.subheader("🗺️ Carte NDVI (palette Kermap)")

    def colorize(v):
        if v is None:
            return "#bbbbbb"
        vv = (v + 1) / 2
        if vv < 0.33: return "#d73027"   # rouge
        if vv < 0.66: return "#fee08b"   # jaune
        return "#1a9850"                 # vert

    m = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=14
    )

    for feat in gdf["features"]:
        ndvi = feat["properties"]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7,
            },
            tooltip=f"NDVI = {ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    # -----------------------------------------------------------
    # ✅ Tableau & Export
    # -----------------------------------------------------------
    st.subheader(f"📊 NDVI par parcelle — Tuile du {sensing_date[:10]}")

    rows = [
        {"Parcelle": i + 1, "NDVI": feat["properties"]["NDVI"]}
        for i, feat in enumerate(gdf["features"])
    ]

    df = pd.DataFrame(rows)
    st.dataframe(df)

    st.download_button(
        "Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi.csv"
    )
