
import re
from enum import Enum

class Shape(Enum):
    CIRCLE = 1

class MapView:
    def __init__(self, east, west, south, north, width = 2000, height = 1200,
                 transform = None):
        self.east = east
        self.west = west
        self.south = south
        self.north = north
        self.width = width
        self.height = height
        self.transform = transform

# ===== TEXT STYLE
# for formatting

class TextStyle:

    def __init__(self, font_name = None, font_size = None, font_color = None,
                 halo_color = None, halo_radius = 0):
        self._font_name = font_name or 'DejaVu Sans Book'
        self._font_size = font_size or 30
        self._font_color = to_color(font_color or '#ffffff')
        self._halo_color = to_color(halo_color or '#000000')
        self._halo_radius = halo_radius

    def get_id(self):
        return 'id' + str(id(self))

    def get_font_size(self):
        return self._font_size

    def get_font_name(self):
        return self._font_name

    def get_font_color(self):
        return self._font_color

    def get_halo_color(self):
        return self._halo_color

    def get_halo_radius(self):
        return self._halo_radius

# ===== LINE FORMAT

class LineFormat:

    def __init__(self, line_color, line_width):
        self._line_color = to_color(line_color)
        self._line_width = line_width

    def get_line_color(self):
        return self._line_color

    def get_line_width(self):
        return self._line_width

# ===== MARKER

class Marker:

    def __init__(self, fill_color, label = None):
        self._fill_color = fill_color
        self._label = label

    def get_label(self):
        return self._label

    def get_fill_color(self):
        return self._fill_color

    def get_shape(self):
        return Shape.CIRCLE

# ===== COLOR

class Color:

    def __init__(self, red : float, green : float, blue : float):
        self._rgb = (red, green, blue)

    def as_hex(self):
        return '#' + ''.join([ourhex(int(round(v * 255))) for v in self._rgb])

    def as_int_tuple(self, scale):
        return tuple([int(round(v * scale)) for v in self._rgb])

RE_RGB_EXPR = re.compile('rgb\\(([0-9]+)%,\\s*([0-9]+)%,\\s*([0-9]+)%\\)')
RE_RGB_HEX = re.compile('#[A-Fa-f0-9]{6}')

def to_color(spec):
    m = RE_RGB_EXPR.match(spec)
    if m:
        return Color(int(m.group(1)) / 100,
                     int(m.group(2)) / 100,
                     int(m.group(3)) / 100)

    m = RE_RGB_HEX.match(spec)
    if m:
        return Color(unhex(spec[1 : 3]) / 255,
                     unhex(spec[3 : 5]) / 255,
                     unhex(spec[5 : 7]) / 255)

    if spec == 'black':
        return Color(0, 0, 0)
    elif spec == 'white':
        return Color(1, 1, 1)
    assert False, 'Unsupported spec: %s' % spec

def ourhex(num):
    return hex(num)[2 : ].zfill(2)

def unhex(h):
    return _unhexdigit(h[0]) * 16 + _unhexdigit(h[1])

def _unhexdigit(digit):
    if digit >= '0' and digit <= '9':
        return int(digit)
    else:
        return ord(digit.lower()) - 87

# ===== LEGEND

class Legend:

    def __init__(self, location = ('top', 'right'), scale = 1.0):
        self._location = location
        self._scale = scale

    def get_location(self):
        return self._location

    def get_scale(self):
        return self._scale

# ===== MAP DECORATOR

class MapDecorator:
    def __init__(self):
        self._labels = []
        self._legend = None
        self._shapes = []

    def get_text_styles(self):
        return set([style for (_, _, _, style) in self._labels])

    def get_text_labels(self):
        return self._labels

    def add_text_label(self, text, lat, lng, style):
        self._labels.append((text, lat, lng, style))

    def get_legend(self):
        return self._legend

    def set_legend(self, legend):
        if legend is True:
            legend = Legend()
        self._legend = legend

    # FIXME: add support for fill
    def add_shapes(self, geometry_file: str, line: LineFormat):
        self._shapes.append((geometry_file, line))

    def get_shapes(self):
        return self._shapes
