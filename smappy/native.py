'''
Backend which draws the map using smappy's own map-rendering implementation.
'''

import json, math
from typing import Optional
from smappy import mapbase
from PIL import Image, ImageDraw, ImageFont
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

        bboxer = OverlapIndex()
        projector = make_projector(self._view,
                                   self._view.width * RESIZE_FACTOR,
                                   self._view.height * RESIZE_FACTOR)

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
                    coords = [projector(coord) for coord in linestring]

                    lw = 0
                    lc = (0, 0, 0)
                    fc = None
                    if layer.get_line_format():
                        line = layer.get_line_format()
                        lw = int(line.get_line_width())
                        lc = line.get_line_color().as_int_tuple(255)
                    if layer.get_fill_color():
                        fc = layer.get_fill_color().as_int_tuple(255)
                    draw.polygon(coords, outline = lc, width = lw, fill = fc)

        for marker in self._markers:
            mf = marker.get_marker()

            pt = (marker.get_longitude(), marker.get_latitude())
            pt = projector(pt)

            draw.circle(pt, (mf.get_scale() or 10) * RESIZE_FACTOR,
                        fill = mf.get_fill_color().as_int_tuple(255),
                        width = mf.get_line_width() * RESIZE_FACTOR,
                        outline = mf.get_line_color().as_int_tuple(255))

            if not mf.get_title_display() == mapbase.TitleDisplay.NEXT_TO_SYMBOL:
                continue

            style = mf.get_text_style()
            font = ImageFont.truetype(style.get_font_name(),
                                      style.get_font_size() * RESIZE_FACTOR,
                                      encoding = 'unic')
            radius = ((mf.get_scale() or 10) + 2) * RESIZE_FACTOR
            pos = bboxer.find_text_position(pt,
                                            marker.get_title(),
                                            font.getbbox(marker.get_title()),
                                            radius)
            draw.text(pos, marker.get_title(),
                      font = font,
                      fill = style.get_font_color().as_int_tuple(255),
                      stroke_width = style.get_halo_radius() * RESIZE_FACTOR,
                      stroke_fill = style.get_halo_color().as_int_tuple(255))

        for (text, lat, lng, style) in self._labels:
            font = ImageFont.truetype(style.get_font_name(),
                                      style.get_font_size() * RESIZE_FACTOR,
                                      encoding = 'unic')
            pt = projector((lng, lat))
            draw.text(pt, text, font = font,
                      fill = style.get_font_color().as_int_tuple(255),
                      stroke_width = style.get_halo_radius(),
                      stroke_fill = style.get_halo_color())

        # resize to smooth image
        if RESIZE_FACTOR != 1:
            img = img.resize((int(img.width / RESIZE_FACTOR),
                              int(img.height / RESIZE_FACTOR)),
                             resample = Image.Resampling.LANCZOS)

        img.save(filename, 'PNG')

class OverlapIndex:

    def __init__(self):
        self._bboxes = []

    def find_text_position(self, pt, text, bbox, radius):
        height = bbox[3] - bbox[1]

        # first try on the right
        pos = (pt[0] + radius, pt[1] - (height/2) - 5 * RESIZE_FACTOR)
        pbbox = (bbox[0] + pos[0], bbox[1] + pos[1],
                 bbox[2] + pos[0], bbox[3] + pos[1])

        if self.overlaps(pbbox):
            print('Overlaps: ', text)

        self._bboxes.append(pbbox)

        return pos

    def add_bbox(self, pos, bbox):
        self._bboxes.append(bbox)

    def overlaps(self, pbbox):
        for bbox in self._bboxes:
            if overlaps(bbox, pbbox):
                return True
        return False

def overlaps(bbox1, bbox2):
    (left1, top1, right1, bottom1) = bbox1
    (left2, top2, right2, bottom2) = bbox2
    return lines_cross(((left1, top1), (right1, top1)),
                       ((left2, top2), (left2, bottom2)))

def lines_cross(line1, line2):
    return False
    # (start1, end1) = line1
    # (start2, end2) = line2
    # return ((start2[1] > start1[1] and start2[1] < end1[1]) and
    #         (start1[0]

# --- PROJECTIONS

def make_projector(view, width, height):
    # --- compute map size
    northwest = project((view.west, view.north))
    southeast = project((view.east, view.south))
    (west, north) = northwest
    (east, south) = southeast

    # this adjustment ensures the north-south and east-west sides of the map
    # are equally long (in metres), so we don't end up skewing the map
    side_length = max(abs(north - south), abs(east - west))
    north = south + side_length
    east = west + side_length

    def meters2pixels(lnglat):
        # this is GeoJSON, which is lng, lat
        (lng, lat) = lnglat
        y = (lat2y(lat) - north) / (south - north)
        x = (west - lon2x(lng)) / (west - east)
        return (x * width, y * height)

    return meters2pixels

RADIUS = 6378137.0 # in meters on the equator

def lat2y(a):
  return math.log(math.tan(math.pi / 4 + math.radians(a) / 2)) * RADIUS

def lon2x(a):
  return math.radians(a) * RADIUS

def project(lnglat):
    (lng, lat) = lnglat
    return (lon2x(lng), lat2y(lat))

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
