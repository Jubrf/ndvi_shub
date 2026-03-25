import rasterio
import numpy as np
from shapely.geometry import shape

def extract_ndvi_stats(gdf, ndvi_path):
    """
    Calcule le NDVI moyen par polygone.
    gdf = GeoJSON-like {features:[...]}
    ndvi_path = chemin du GeoTIFF NDVI
    """
    with rasterio.open(ndvi_path) as src:
        ndvi = src.read(1)
        transform = src.transform

    for feat in gdf["features"]:
        geom = shape(feat["geometry"])
        values = sample_raster_over_polygon(ndvi, transform, geom)
        feat["properties"]["NDVI"] = float(np.nanmean(values)) if len(values) else None

    return gdf


def sample_raster_over_polygon(array, transform, geom):
    """
    Renvoie la liste des pixels NDVI dans un polygone.
    """
    import shapely.geometry as sg

    minx, miny, maxx, maxy = geom.bounds
    height, width = array.shape

    row_min, col_min = ~transform * (minx, maxy)
    row_max, col_max = ~transform * (maxx, miny)

    row_min, row_max = max(0, int(row_min)), min(height-1, int(row_max))
    col_min, col_max = max(0, int(col_min)), min(width-1, int(col_max))

    values = []

    for i in range(row_min, row_max+1):
        for j in range(col_min, col_max+1):
            x, y = transform * (j + 0.5, i + 0.5)
            if geom.contains(sg.Point(x, y)):
                val = array[i, j]
                if not np.isnan(val):
                    values.append(val)

    return values
