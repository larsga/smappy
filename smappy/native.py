'''
Backend which draws the map using smappy's own map-rendering implementation.
'''

import json, math
from typing import Optional
from smappy import mapbase
from PIL import Image, ImageDraw, ImageFont
import fpdf
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
        assert format in ('png', 'pdf')

        bboxer = OverlapIndex()

        # --- draw the map
        if format == 'png':
            drawer = PngDrawer(self._view.width,
                               self._view.height,
                               self._background)
        else:
            drawer = PdfDrawer(self._view.width,
                               self._view.height,
                               self._background)
        (width, height) = drawer.get_size()
        projector = make_projector(self._view, width, height)

        for layer in self._layers:
            features = extract_features(layer.get_geometry_file())
            for feature in features:
                linestrings = convert_to_linestrings(feature)
                for linestring in linestrings:
                    coords = [projector(coord) for coord in linestring]

                    drawer.polygon(coords, layer.get_line_format(),
                                   layer.get_fill_color())

        for marker in self._markers:
            mf = marker.get_marker()

            pt = (marker.get_longitude(), marker.get_latitude())
            pt = projector(pt)

            drawer.circle(pt, mf.get_scale() or 10, mf.get_fill_color(),
                          line_format = mf)

            if not mf.get_title_display() == mapbase.TitleDisplay.NEXT_TO_SYMBOL:
                continue

            radius = ((mf.get_scale() or 10) + 2)
            bbox = drawer.get_bbox(marker.get_title(), mf.get_text_style())
            pos = bboxer.find_text_position(pt,
                                            marker.get_title(),
                                            bbox,
                                            radius)
            drawer.text(pos, marker.get_title(), mf.get_text_style())

        for (text, lat, lng, style) in self._labels:
            pt = projector((lng, lat))
            drawer.text(pt, text, style)

        drawer.write_to(filename)

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

# --- PNG DRAWER

class PngDrawer:

    def __init__(self, width, height, background):
        self._img = Image.new('RGB', (width * RESIZE_FACTOR,
                                      height * RESIZE_FACTOR),
                              background.as_int_tuple(255))
        self._draw = ImageDraw.Draw(self._img)

    def get_size(self):
        return (self._img.width, self._img.height)

    def polygon(self, coords, line_format, fill_color):
        lw = 0
        lc = (0, 0, 0)
        fc = None
        if line_format:
            lw = int(line_format.get_line_width()) #* RESIZE_FACTOR
            lc = line_format.get_line_color().as_int_tuple(255)
        if fill_color:
            fc = fill_color.as_int_tuple(255)
        self._draw.polygon(coords, outline = lc, width = lw, fill = fc)

    def circle(self, point, radius, fill, line_format):
        width = line_format.get_line_width() * RESIZE_FACTOR
        line_color = line_format.get_line_color().as_int_tuple(255)
        self._draw.circle(point, radius * RESIZE_FACTOR,
                          fill = fill.as_int_tuple(255),
                          width = width,
                          outline = line_color)

    def get_bbox(self, text, style):
        font = ImageFont.truetype(style.get_font_name(),
                                  style.get_font_size() * RESIZE_FACTOR,
                                  encoding = 'unic')
        return font.getbbox(marker.get_title())

    def text(self, point, text, style):
        font = ImageFont.truetype(style.get_font_name(),
                                  style.get_font_size() * RESIZE_FACTOR,
                                  encoding = 'unic')
        self._draw.text(point, text,
                        font = font,
                        fill = style.get_font_color().as_int_tuple(255),
                        stroke_width = style.get_halo_radius() * RESIZE_FACTOR,
                        stroke_fill = style.get_halo_color().as_int_tuple(255))

    def write_to(self, filename):
        if RESIZE_FACTOR != 1:
            img = self._img.resize((int(self._img.width / RESIZE_FACTOR),
                                    int(self._img.height / RESIZE_FACTOR)),
                                   resample = Image.Resampling.LANCZOS)

        img.save(filename, 'PNG')

class PdfDrawer:

    def __init__(self, width, height, background):
        self._size = (width, height)
        self._pdf = fpdf.FPDF()
        self._pdf.add_page(format = self._size)

        (r, g, b) = background.as_int_tuple(255)
        self._pdf.set_fill_color(r = r, g = g, b = b)
        self._pdf.rect(h = self._pdf.h, w = self._pdf.w, x = 0, y = 0,
                       style = 'DF')

        self._installed_fonts = set()

    def get_size(self):
        return self._size

    def polygon(self, coords, line_format, fill_color):
        style = self._set_line_and_fill(line_format, fill_color)
        self._pdf.polygon(coords, style = style)

    def _set_line_and_fill(self, line_format, fill_color):
        'Returns drawing style'
        if fill_color:
            (r, g, b) = fill_color.as_int_tuple(255)
            self._pdf.set_fill_color(r, g, b)

        if line_format:
            self._pdf.set_line_width(line_format.get_line_width())
            (r, g, b) = line_format.get_line_color().as_int_tuple(255)
            self._pdf.set_draw_color(r, g, b)
        else:
            self._pdf.set_line_width(0)
            (r, g, b) = fill_color.as_int_tuple(255)
            self._pdf.set_draw_color(r, g, b)

        if fill_color:
            return 'DF'
        else:
            return 'D'

    def circle(self, point, radius, fill, line_format):
        style = self._set_line_and_fill(line_format, fill)
        self._pdf.circle(point[0], point[1], radius, style = style)

    def get_bbox(self, text, style):
        self._install_font(style)
        return (0, 0, 1, 1)

    def _install_font(self, style):
        font = style.get_font_name()
        if font not in self._installed_fonts:
            self._pdf.add_font(family = extract_font_name(font), fname = font)
            self._installed_fonts.add(font)

    def text(self, point, text, style):
        self._install_font(style)
        self._pdf.set_font(extract_font_name(style.get_font_name()))

        # this doesn't work -- need thicker version of the text, basically
        if False and style.get_halo_color():
            self._pdf.set_font_size((style.get_font_size() + style.get_halo_radius()) * 2)
            (r, g, b) = style.get_halo_color().as_int_tuple(255)
            #self._pdf.set_text_color(r, g, b)
            self._pdf.set_text_color(255, 0, 0)
            height = self._pdf.get_string_width('x') * 2.2
            self._pdf.text(point[0], point[1] + height, text)

        (r, g, b) = style.get_font_color().as_int_tuple(255)
        self._pdf.set_text_color(r, g, b)
        self._pdf.set_font_size(style.get_font_size() * 2)
        # Pillow has the text anchor top left, but fpdf has bottom left
        height = self._pdf.get_string_width('x') * 2.2
        self._pdf.text(point[0], point[1] + height, text)

    def write_to(self, filename):
        self._pdf.output(filename)

def extract_font_name(filename):
    ix = filename.rfind('/')
    ix2 = filename.rfind('.')
    return filename[ix+1 : ix2]
