import rasterio
import numpy as np
from shapely.geometry import shape

def sample_raster_over_polygon(array, transform, geom):
    import shapely.geometry as sg

    minx, miny, maxx, maxy = geom.bounds
    height, width = array.shape

    row_min, col_min = ~transform * (minx, maxy)
    row_max, col_max = ~transform * (maxx, miny)

    row_min = max(0, int(row_min))
    col_min = max(0, int(col_min))
    row_max = min(height - 1, int(row_max))
    col_max = min(width - 1, int(col_max))

    values = []

    for i in range(row_min, row_max + 1):
        for j in range(col_min, col_max + 1):
            x, y = transform * (j + 0.5, i + 0.5)
            if geom.contains(sg.Point(x, y)):
                v = array[i, j]
                if not np.isnan(v):
                    values.append(v)

    return values


def extract_single_polygon_ndvi(ndvi_path, geom):
    with rasterio.open(ndvi_path) as src:
        arr = src.read(1)
        transform = src.transform

    vals = sample_raster_over_polygon(arr, transform, geom)
    return np.array(vals)
