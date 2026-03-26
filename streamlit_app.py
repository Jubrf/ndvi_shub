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
st.title("🌱 NDVI Sentinel Hub — Parcelle par parcelle + Fallback multi-dates + Cloud Mask")

uploaded = st.file_uploader(
    "Uploader un fichier : ZIP SHP ou GEOJSON",
    type=["zip", "geojson"]
)

# -----------------------------------------------------------
# ✅ FALLBACK NDVI PARCELLE PAR PARCELLE (STYLE KERMAP)
# -----------------------------------------------------------
def fallback_ndvi_for_parcel(geom, max_days=30, step=3):
    """
    Tente NDVI sur J0, J-3, J-6... jusqu’à max_days.
    Retourne (ndvi_mean, sensing_date)
    """
    today = datetime.datetime.utcnow().date()

    for delta in range(0, max_days, step):

        from_date = (today - datetime.timedelta(days=delta + step)).strftime("%Y-%m-%dT00:00:00Z")
        to_date   = (today - datetime.timedelta(days=delta)).strftime("%Y-%m-%dT23:59:59Z")

        time_range = (from_date, to_date)

        st.write(f"🔍 Test période : {from_date} → {to_date}")

        # NDVI via Process API
        ndvi_bytes, sensing_date = sentinelhub_ndvi_with_date(geom, time_range)

        if ndvi_bytes is None or sensing_date is None:
            st.warning("⏳ NDVI indisponible sur cette période. On remonte…")
            continue

        # Sauvegarde temporaire NDVI
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
        tmp.write(ndvi_bytes)
        tmp.close()

        # Extraction NDVI parcelle
        values = extract_single_polygon_ndvi(tmp.name, geom)

        if len(values) > 0:
            ndvi_mean = float(values.mean())
            st.success(f"✅ NDVI trouvé : {ndvi_mean} (date : {sensing_date})")
            return ndvi_mean, sensing_date

        st.warning("🟨 NDVI vide (nuages/ombres) → fallback…")

    st.error("❌ Aucun NDVI exploitable jusqu'à J-30")
    return None, None


# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
if uploaded:

    gdf = load_vector(uploaded)
    geoms = [shape(f["geometry"]) for f in gdf["features"]]

    rows = []

    st.info("Calcul NDVI parcelle par parcelle (fallback multi‑dates)…")

    for i, geom in enumerate(geoms):

        st.write(f"\n## Parcelle {i+1}")

        # ✅ BBOX locale étendue
        minx, miny, maxx, maxy = geom.bounds
        pad = 0.003
        minx -= pad; miny -= pad
        maxx += pad; maxy += pad

        bbox_local = shape({
            "type": "Polygon",
            "coordinates": [[
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny]
            ]]
        })

        ndvi_mean, date_used = fallback_ndvi_for_parcel(bbox_local)

        rows.append({
            "Parcelle": i+1,
            "NDVI": ndvi_mean,
            "Date": date_used
        })

    # ✅ Résultats
    df = pd.DataFrame(rows)
    st.subheader("📊 NDVI par parcelle")
    st.dataframe(df)

    # -----------------------------------------------------------
    # ✅ Carte NDVI type Kermap
    # -----------------------------------------------------------
    st.subheader("🗺️ Carte NDVI — palette Kermap")

    def colorize(v):
        if v is None:
            return "#bbbbbb"
        vv = (v + 1) / 2
        if vv < 0.33: return "#d73027"
        if vv < 0.66: return "#fee08b"
        return "#1a9850"

    # Centre carte
    minx = min(g.bounds[0] for g in geoms)
    miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms)
    maxy = max(g.bounds[3] for g in geoms)

    m = folium.Map(location=[(miny+maxy)/2, (minx+maxx)/2], zoom_start=14)

    # Ajout parcelles
    for i, feat in enumerate(gdf["features"]):
        ndvi = df.iloc[i]["NDVI"]
        folium.GeoJson(
            feat["geometry"],
            style_function=lambda x, ndvi=ndvi: {
                "fillColor": colorize(ndvi),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7
            },
            tooltip=f"Parcelle {i+1} — NDVI : {ndvi}"
        ).add_to(m)

    st_folium(m, height=600)

    # ✅ Export CSV
    st.download_button(
        "📥 Télécharger NDVI (CSV)",
        df.to_csv(index=False).encode(),
        "ndvi_par_parcelle.csv"
    )
