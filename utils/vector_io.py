import tempfile
import json
import zipfile
import os
import shapefile  # pyshp
from shapely.geometry import shape
import pyproj
from shapely.ops import transform

def load_vector(uploaded):
    """
    Charge un ZIP SHP ou un GeoJSON et renvoie un dict {features:[...]}
    """

    suffix = ".zip" if uploaded.name.endswith(".zip") else ".geojson"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.read())
    tmp.close()

    if suffix == ".geojson":
        with open(tmp.name) as f:
            gj = json.load(f)
        features = [{"geometry": shape(feat["geometry"]).__geo_interface__, "properties": {}} for feat in gj["features"]]
        return {"features": features}

    with zipfile.ZipFile(tmp.name, "r") as z:
        extract_dir = tempfile.mkdtemp()
        z.extractall(extract_dir)

    shp_file = [f for f in os.listdir(extract_dir) if f.endswith(".shp")][0]
    sf = shapefile.Reader(os.path.join(extract_dir, shp_file))
    shapes = sf.shapes()

    geoms = [shape(s.__geo_interface__) for s in shapes]

    # Reprojection si PRJ
    prj = shp_file.replace(".shp", ".prj")
    crs = None
    if os.path.exists(os.path.join(extract_dir, prj)):
        with open(os.path.join(extract_dir, prj)) as f:
            wkt = f.read()
        try:
            crs = pyproj.CRS.from_wkt(wkt)
        except:
            pass

    if crs and crs.to_epsg() != 4326:
        to_wgs = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
        geoms = [transform(to_wgs, g) for g in geoms]

    features = [{"geometry": g.__geo_interface__, "properties": {}} for g in geoms]
    return {"features": features}
