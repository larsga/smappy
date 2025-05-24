'''
Backend which draws the map using smappy's own map-rendering implementation.
'''

import json, math
from typing import Optional
from smappy import mapbase
from PIL import Image, ImageDraw
import shapefile

RESIZE_FACTOR = 4 # to get antialiasing

class NativeMap(mapbase.AbstractMap):

    def __init__(self, mapview: mapbase.MapView,
                 background_color: Optional[str] = None):
        mapbase.AbstractMap.__init__(self)
        self._view = mapview
        self._background = mapbase.to_color(background_color or '#88CCFF')

    def render_to(self, filename: str, format: str = 'png') -> None:
        filename = mapbase.add_extension(filename, format)
        assert format == 'png'

        # --- compute map size
        northwest = (self._view.west, self._view.north)
        southeast = (self._view.east, self._view.south)
        (northwest, southeast) = transform([northwest, southeast])
        (west, north) = northwest
        (east, south) = southeast

        # this adjustment ensures the north-south and east-west sides of the map
        # are equally long (in metres), so we don't end up skewing the map
        side_length = ((north - south) + (east - west)) / 2
        north = south + side_length
        east = west + side_length

        # --- draw the map
        img = Image.new('RGB', (self._view.width * RESIZE_FACTOR,
                                self._view.height * RESIZE_FACTOR),
                        self._background.as_int_tuple(255))
        draw = ImageDraw.Draw(img)

        for layer in self._layers:
            features = extract_features(layer.get_geometry_file())
            for feature in features:
                linestrings = convert_to_linestrings(feature)
                for linestring in linestrings:
                    coords = transform(linestring)
                    coords2 = [meters2pixels(coord, north, west, south, east,
                                             img.width, img.height)
                               for coord in coords]

                    lw = 0
                    lc = (0, 0, 0)
                    fc = None
                    if layer.get_line_format():
                        line = layer.get_line_format()
                        lw = int(line.get_line_width())
                        lc = line.get_line_color().as_int_tuple(255)
                    if layer.get_fill_color():
                        fc = layer.get_fill_color().as_int_tuple(255)
                    draw.polygon(coords2, outline = lc, width = lw, fill = fc)

        for marker in self._markers:
            mf = marker.get_marker()

            pt = (marker.get_longitude(), marker.get_latitude())
            pt = transform([pt])[0]
            pt = meters2pixels(pt, north, west, south, east,
                               img.width, img.height)

            draw.circle(pt, mf.get_scale() or 40,
                        fill = mf.get_fill_color().as_int_tuple(255),
                        width = mf.get_line_width() * RESIZE_FACTOR,
                        outline = mf.get_line_color().as_int_tuple(255))

        # resize to smooth image
        if RESIZE_FACTOR != 1:
            img = img.resize((int(img.width / RESIZE_FACTOR),
                              int(img.height / RESIZE_FACTOR)),
                             resample = Image.Resampling.LANCZOS)

        img.save(filename, 'PNG')

# --- PROJECTIONS

RADIUS = 6378137.0 # in meters on the equator

def lat2y(a):
  return math.log(math.tan(math.pi / 4 + math.radians(a) / 2)) * RADIUS

def lon2x(a):
  return math.radians(a) * RADIUS

def project(point):
    # this is GeoJSON, which is lng, lat
    (lng, lat) = point
    return (lon2x(lng), lat2y(lat))

def transform(listofpoints):
    # output is in meters
    return [project(p) for p in listofpoints]

def meters2pixels(lnglat, north, west, south, east, width, height):
    (lng, lat) = lnglat
    lat = (lat - north) / (south - north)
    lng = (west - lng) / (west - east)
    #return (lat * view['height'], lng * view['width'])
    return (lng * width, lat * height)

# --- FORMAT HANDLING

def extract_features(filename):
    if filename.endswith('.shp'):
        return extract_features_shp(filename)
    elif filename.endswith('.json') or filename.endswith('.geojson'):
        return extract_features_geojson(filename)
    assert False

def extract_features_shp(filename):
    reader = shapefile.Reader(filename)

    geojson_data = reader.__geo_interface__

    reader.close()

    return geojson_data['features']

def extract_features_geojson(filename):
    return json.load(open(filename))

def convert_to_linestrings(feature):
    if not feature['geometry']:
        return [] # why does pyshp return this?

    if feature['geometry']['type'] == 'Polygon':
        return feature['geometry']['coordinates']

    elif feature['geometry']['type'] == 'MultiPolygon':
        linestrings = []
        for part in feature['geometry']['coordinates']:
            linestrings += part
        return linestrings

    else:
        return [] #assert False
