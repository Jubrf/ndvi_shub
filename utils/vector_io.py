import tempfile
import json
import zipfile
import os
import shapefile
from shapely.geometry import shape
from shapely.ops import transform
import pyproj

def load_vector(uploaded):

    suffix = ".zip" if uploaded.name.endswith(".zip") else ".geojson"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded.read())
    tmp.close()

    # GEOJSON
    if suffix == ".geojson":
        with open(tmp.name, "r") as f:
            data = json.load(f)
        features = []
        for feat in data["features"]:
            geom = shape(feat["geometry"])
            features.append({"geometry": geom.__geo_interface__, "properties": {}})
        return {"features": features}

    # ZIP SHP
    with zipfile.ZipFile(tmp.name, "r") as z:
        extract_dir = tempfile.mkdtemp()
        z.extractall(extract_dir)

    shp = None
    for f in os.listdir(extract_dir):
        if f.endswith(".shp"):
            shp = os.path.join(extract_dir, f)
            break
    if shp is None:
        raise ValueError("Pas de SHP dans l'archive.")

    sf = shapefile.Reader(shp)
    shapes = sf.shapes()

    geoms = [shape(s.__geo_interface__) for s in shapes]

    # reprojection si PRJ
    prj = shp.replace(".shp", ".prj")
    if os.path.exists(prj):
        with open(prj) as f:
            wkt = f.read()
        try:
            src = pyproj.CRS.from_wkt(wkt)
            if src.to_epsg() != 4326:
                dst = pyproj.CRS.from_epsg(4326)
                proj = pyproj.Transformer.from_crs(src, dst, always_xy=True).transform
                geoms = [transform(proj, g) for g in geoms]
        except:
            pass

    return {"features": [{"geometry": g.__geo_interface__, "properties": {}} for g in geoms]}
