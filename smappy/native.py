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
        format = format or 'png'
        filename = mapbase.add_extension(filename, format)
        assert format in ('png', 'pdf')

        bboxer = OverlapIndex()

        # --- draw the map
        width = self._view.width
        height = self._view.height
        if format == 'png':
            drawer = PngDrawer(width, height, self._background)
        else:
            drawer = PdfDrawer(width, height, self._background)

        projector = make_projector(self._view, width, height)

        for layer in self._layers:
            if isinstance(layer, mapbase.ShapeLayer):
                features = extract_features(layer.get_geometry_file(),
                                            layer.get_selectors())
                for feature in features:
                    (linestrings, closed) = convert_to_linestrings(feature)
                    for linestring in linestrings:
                        coords = [projector(coord) for coord in linestring]

                        if closed:
                            drawer.polygon(coords, layer.get_line_format(),
                                           layer.get_fill_color())
                        else:
                            drawer.line(coords, layer.get_line_format())

            elif isinstance(layer, mapbase.RasterLayer):
                render_raster(drawer, self._view, projector,
                            layer.get_raster_file(),
                            layer.get_stops())

            else:
                assert False, 'Unknown layer type: %s' % layer

        for marker in self._markers:
            mf = marker.get_marker()

            pt = (marker.get_longitude(), marker.get_latitude())
            pt = projector(pt)

            drawer.circle(pt, mf.get_scale() or 10, mf.get_fill_color(),
                          line_format = mf)

            if not mf.get_title_display() == mapbase.TitleDisplay.NEXT_TO_SYMBOL:
                continue

            radius = ((mf.get_scale() or 10) + 2) * RESIZE_FACTOR
            bbox = drawer.get_bbox(marker.get_title(), mf.get_text_style())
            pos = bboxer.find_text_position(pt,
                                            marker.get_title(),
                                            bbox,
                                            radius)
            drawer.text(pos, marker.get_title(), mf.get_text_style())

        for (text, lat, lng, style) in self._labels:
            pt = projector((lng, lat))
            drawer.text(pt, text, style)

        if self._legend:
            self._add_legend(drawer)

        drawer.write_to(filename)
        if self._view.transform:
            self._view.transform(filename, None)

    def _add_legend(self, drawer):
        used_symbols = list(self._symbols)
        legend_scale = self._legend.get_scale()

        style = mapbase.TextStyle(font_name = 'Arial',
                                  font_size = 24 * self._legend.get_scale(),
                                  font_color = '#000000')

        widest = 0
        for symbol in used_symbols:
            (left, top, right, bottom) = drawer.get_bbox(symbol.get_label(),
                                                         style)
            width = right - left
            widest = max(widest, width)

        r = 12 * legend_scale
        offset = legend_scale * 8
        boxwidth = r * 2 + offset * 3 + widest
        displace = (r * 2) + 12 * legend_scale
        boxheight = displace * len(used_symbols) + offset

        (vertpos, horpos) = self._legend.get_location()
        assert vertpos in ('top', 'bottom')
        assert horpos in ('left', 'right')

        if vertpos == 'top':
            y1 = offset
            y2 = offset + boxheight
        else:
            (width, height) = (self._view.width, self._view.height)
            y1 = height - (boxheight + offset)
            y2 = height - offset

        if horpos == 'left':
            x1 = offset
            x2 = offset + boxwidth
        else:
            (width, height) = (self._view.width, self._view.height)
            x1 = width - (offset + boxwidth)
            x2 = width - offset

        lf = mapbase.to_line_format('#000000', int(2 * legend_scale))
        drawer.polygon(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)],
            lf,
            mapbase.to_color('#ffffff')
        )

        for (ix, symbol) in enumerate(used_symbols):
            displacement = displace * ix
            if symbol.get_shape() == mapbase.Shape.CIRCLE:
                drawer.circle(
                    (x1 + offset + r, y1 + offset + displacement + r),
                    r,
                    symbol.get_fill_color(),
                    symbol
                )

            elif symbol.get_shape() == mapbase.Shape.TRIANGLE:
                assert False
                # draw.polygon(
                #     [
                #         (x1 + offset + r, y1 + offset + displacement),
                #         (x1 + offset, y1 + offset + r*2 + displacement),
                #         (x1 + offset + r*2, y1 + offset + r*2 + displacement)
                #     ],
                #     outline = (0, 0, 0),
                #     fill = symbol.get_fill_color().as_int_tuple(256)
                # )

            else:
                assert False, 'Unsupported shape: %s' % symbol.get_shape()

            drawer.text(
                (x1 + 20 * legend_scale + (r * 2), y1 + offset + displacement),
                symbol.get_label(),
                style
            )

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

def extract_features(filename, selectors):
    if filename.endswith('.shp'):
        return extract_features_shp(filename, selectors)
    elif filename.endswith('.json') or filename.endswith('.geojson'):
        return extract_features_geojson(filename, selectors)
    assert False

def extract_features_shp(filename, selectors):
    reader = shapefile.Reader(filename)

    geojson_data = reader.__geo_interface__

    reader.close()

    return filter_features(selectors, geojson_data['features'])

def extract_features_geojson(filename, selectors):
    return filter_features(selectors, json.load(open(filename))['features'])

def filter_features(selectors, features):
    if selectors:
        by_prop = {}
        for (idprop, idval) in selectors:
            if idprop not in by_prop:
                by_prop[idprop] = set()
            by_prop[idprop].add(idval)

        accepted = []
        for f in features:
            props = f['properties']
            ok = False
            for (propname, values) in by_prop.items():
                if props.get(propname) in values:
                    ok = True
                    break
            if ok:
                accepted.append(f)
        features = accepted
    return features

def convert_to_linestrings(feature):
    if not feature['geometry']:
        return ([], False) # why does pyshp return this?

    if feature['geometry']['type'] == 'Polygon':
        return (feature['geometry']['coordinates'], True)

    elif feature['geometry']['type'] == 'MultiPolygon':
        linestrings = []
        for part in feature['geometry']['coordinates']:
            linestrings += part
        return (linestrings, True)

    elif feature['geometry']['type'] == 'LineString':
        return ([feature['geometry']['coordinates']], False)

    elif feature['geometry']['type'] == 'MultiLineString':
        linestrings = []
        for part in feature['geometry']['coordinates']:
            linestrings += [part]
        return (linestrings, False)

    else:
        return [[], False] #assert False

# --- PNG DRAWER

class PngDrawer:

    def __init__(self, width, height, background):
        self._img = Image.new('RGB', (width * RESIZE_FACTOR,
                                      height * RESIZE_FACTOR),
                              background.as_int_tuple(255))
        self._draw = ImageDraw.Draw(self._img, mode = 'RGB')

    def get_size(self):
        return (self._img.width, self._img.height)

    def polygon(self, coords, line_format, fill_color):
        lw = 0
        lc = (0, 0, 0)
        fc = None
        if line_format:
            lw = int(line_format.get_line_width()) * RESIZE_FACTOR
            lc = line_format.get_line_color().as_int_tuple(255)
        if fill_color:
            fc = fill_color.as_int_tuple(255)

        coords = [(x * RESIZE_FACTOR, y * RESIZE_FACTOR) for (x, y) in coords]

        # CORRECT CODE, but very slow, because of
        #   https://github.com/python-pillow/Pillow/issues/8976
        # self._draw.polygon(coords, outline = lc, width = lw, fill = fc)

        # TEMPORARY WORKAROUND UNTIL NEXT RELEASE
        ink, fill_ink = self._draw._getink(lc, fc)
        if fill_ink:
            self._draw.draw.draw_polygon(coords, fill_ink, 1)
        self._draw.draw.draw_polygon(coords, ink, 0, lw)

    def line(self, coords, line_format):
        lw = 0
        lc = (0, 0, 0)
        if line_format:
            lw = int(line_format.get_line_width()) * RESIZE_FACTOR
            lc = line_format.get_line_color().as_int_tuple(255)

        coords = [(x * RESIZE_FACTOR, y * RESIZE_FACTOR) for (x, y) in coords]
        self._draw.line(coords, fill = lc, width = lw)

    def circle(self, point, radius, fill, line_format):
        'point is center coordinates'
        point = (point[0] * RESIZE_FACTOR, point[1] * RESIZE_FACTOR)
        width = line_format.get_line_width()
        line_color = line_format.get_line_color().as_int_tuple(255)
        self._draw.circle(point, radius * RESIZE_FACTOR,
                          fill = fill.as_int_tuple(255),
                          width = int(width * RESIZE_FACTOR),
                          outline = line_color)

    def get_bbox(self, text, style):
        # don't scale by resize factor, because the answer here is given in
        # user-scale coordinates. caller will be computing without scaling
        font = ImageFont.truetype(style.get_font_name(),
                                  style.get_font_size(),
                                  encoding = 'unic')
        return font.getbbox(text)

    def text(self, point, text, style):
        font = ImageFont.truetype(style.get_font_name(),
                                  style.get_font_size() * RESIZE_FACTOR,
                                  encoding = 'unic')
        point = (point[0] * RESIZE_FACTOR, point[1] * RESIZE_FACTOR)
        self._draw.text(point, text,
                        font = font,
                        fill = style.get_font_color().as_int_tuple(255),
                        stroke_width = style.get_halo_radius() * RESIZE_FACTOR,
                        stroke_fill = style.get_halo_color().as_int_tuple(255))

    def bitmap(self, image, pos, mask):
        image = Image.fromarray(image, mode = 'RGB')
        mask = Image.fromarray(mask, mode = 'L')
        image = image.resize((image.size[0] * RESIZE_FACTOR,
                              image.size[1] * RESIZE_FACTOR),
                           Image.Resampling.NEAREST)
        mask = mask.resize((mask.size[0] * RESIZE_FACTOR,
                            mask.size[1] * RESIZE_FACTOR),
                           Image.Resampling.NEAREST)
        self._img.paste(image, (0, 0), mask)

    def write_to(self, filename):
        if RESIZE_FACTOR != 1:
            img = self._img.resize((int(self._img.width / RESIZE_FACTOR),
                                    int(self._img.height / RESIZE_FACTOR)),
                                   resample = Image.Resampling.LANCZOS)
        else:
            img = self._img

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

    def line(self, coords, line_format):
        self._set_line_and_fill(line_format, None)
        for ix in range(len(coords) - 1):
            self._pdf.line(x1 = coords[ix][0],
                           y1 = coords[ix][1],
                           x2 = coords[ix + 1][0],
                           y2 = coords[ix + 1][1])

    def _set_line_and_fill(self, line_format, fill_color):
        'Returns drawing style'
        if fill_color:
            (r, g, b) = fill_color.as_int_tuple(255)
            self._pdf.set_fill_color(r, g, b)

        if line_format:
            self._pdf.set_line_width(line_format.get_line_width() / 1.5)
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
        'returns (left, top, right, bottom)'
        self._install_font(style)
        #self._pdf.get_string_width(text)
        estimate = (len(text) / 2.7) * style.get_font_size()
        return (0, 0, estimate, style.get_font_size())

    def _install_font(self, style):
        pass

        # FIXME: not sure how to get this to work again

        # font = style.get_font_name()
        # if font not in self._installed_fonts:
        #     self._pdf.add_font(family = extract_font_name(font), fname = font)
        #     self._installed_fonts.add(font)

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
    if ix2 == -1:
        ix2 = len(filename)
    return filename[ix+1 : ix2]

# ===========================================================================
# EXPERIMENTAL RASTER IMPLEMENTATION

def render_raster(drawer, view, projector, filename, stops):
    # step 1: render into buffer matching view dimensions
    import rasterio, numpy

    minimum_value = stops[0][0]

    dataset = rasterio.open(filename)
    band1 = dataset.read(1)

    (lng, lat) = (view.west, view.north)
    lat = find_correct_north(lng, lat, projector)

    (row, col) = dataset.index(lng, lat)
    startcol = col

    buffer = numpy.zeros((view.height, view.width, 3),
                         dtype = numpy.uint8) # 3-tuples of (RGB)
    mask = numpy.zeros((view.height, view.width),
                         dtype = numpy.uint8) # 1-tuples of (A)
    while lat > view.south:
        while lng < view.east:
            value = band1[row, col]
            # print(lng, lat, value)
            (x, y) = projector((lng, lat))
            if value >= minimum_value:
                try:
                    buffer[int(y)][int(x)] = value_to_color(value, stops)
                    mask[int(y)][int(x)] = 255
                except IndexError:
                    pass # we don't care
            else:
                try:
                    mask[int(y)][int(x)] = 1 # means: pixel with no value
                except IndexError:
                    pass # we don't care

            col += 1
            (lng, lat) = dataset.xy(row, col)

        row += 1
        col = startcol
        (lng, lat) = dataset.xy(row, col)

    # step 2: interpolate missing data
    interpolate(buffer, mask)

    # step 3: paste into drawer
    drawer.bitmap(buffer, (0, 0), mask)

def interpolate(buffer, mask):
    for y in range(buffer.shape[0]):
        prev_x = None
        prev_m = None
        for x in range(buffer.shape[1]):
            if mask[y][x] == 255:
                if prev_m == 255 and prev_x + 1 < x:
                    colordelta = diff(buffer[y][prev_x], buffer[y][x],
                                      x - prev_x)
                    color = buffer[y][prev_x]
                    while prev_x+1 < x:
                        prev_x += 1
                        color = add_color(color, colordelta)
                        buffer[y][prev_x] = color
                        mask[y][prev_x] = 255

                prev_x = x
                prev_m = 255
            elif mask[y][x] == 1:
                if prev_m == 1:
                    for xx in range(prev_x + 1, x):
                        mask[y][xx] = 1 # interpolate 'no data'
                prev_x = x
                prev_m = 1

    for x in range(buffer.shape[1]):
        prev_y = None
        for y in range(buffer.shape[0]):
            if mask[y][x] == 255:
                if prev_y is not None and prev_y + 1 < y:
                    colordelta = diff(buffer[prev_y][x], buffer[y][x],
                                      y - prev_y)
                    color = buffer[prev_y][x]
                    while prev_y+1 < y:
                        prev_y += 1
                        color = add_color(color, colordelta)
                        buffer[prev_y][x] = color
                        mask[prev_y][x] = 255

                prev_y = y
            elif mask[y][x] == 1:
                prev_y = None

def diff(c1, c2, dist):
    return ((int(c2[0]) - int(c1[0])) / dist,
            (int(c2[1]) - int(c1[1])) / dist,
            (int(c2[2]) - int(c1[2])) / dist)

def add_color(color, delta):
    return (color[0] + delta[0],
            color[1] + delta[1],
            color[2] + delta[2])

def value_to_color(value):
    meters_0    = (64, 144, 80)   # '#409050'
    meters_800  = (239, 236, 198) # pale tan colour
    meters_1500 = (166, 137, 90)  # dark brown
    meters_3000 = (255, 255, 255) # white

    if value <= 800:
        return intermediate_color(meters_0, meters_800, value / 800)
    elif value <= 1500:
        return intermediate_color(meters_800, meters_1500, (value-800) / 700)
    else:
        return intermediate_color(meters_1500, meters_3000,
                                  (min(value, 3000) - 1500) / 1500)

def value_to_color(value, stops):
    for (ix, (stop, color)) in enumerate(stops):
        if value <= stop:
            dist = (value - stops[ix-1][0]) / (stop - stops[ix-1][0])
            return intermediate_color(stops[ix-1][1], color, dist)
    return color # max out to last colour

def intermediate_color(c1, c2, percent):
    # percent 0.0 => c1
    # percent 1.0 => c2
    delta = [d * (1000 * percent) for d in diff(c1, c2, 1000)]
    return add_color(c1, delta)

def find_correct_north(lng, lat, projector):
    pos = projector((lng, lat))
    while pos[1] > 1:
        lat += 0.01
        pos = projector((lng, lat))
    return lat
