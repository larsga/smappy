
import re
from enum import Enum
from typing import Optional

class SmappyException(Exception):
    pass

class Shape(Enum):
    CIRCLE = 1
    SQUARE = 2
    TRIANGLE = 3

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

def to_color(spec: Optional[str|Color]) -> Optional[Color]:
    if spec is None:
        return None

    if isinstance(spec, Color):
        return spec

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
    raise SmappyException('Cannot parse color: "%s"' % spec)

def ourhex(num):
    return hex(num)[2 : ].zfill(2)

def unhex(h):
    return _unhexdigit(h[0]) * 16 + _unhexdigit(h[1])

def _unhexdigit(digit):
    if digit >= '0' and digit <= '9':
        return int(digit)
    else:
        return ord(digit.lower()) - 87

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

DEFAULT_TEXT_STYLE = TextStyle()

# ===== LINE FORMAT

def to_line_format(line_color: Optional[str], line_width: Optional[float],
                   line_dash: Optional[tuple] = None):
    if line_color and line_width:
        return LineFormat(to_color(line_color), line_width, line_dash)
    else:
        return None

class LineFormat:

    def __init__(self, line_color: Color, line_width: float,
                 line_dash: Optional[tuple]):
        self._line_color = line_color
        self._line_width = line_width
        self._line_dash = line_dash

    def get_line_color(self):
        return self._line_color

    def get_line_width(self):
        return self._line_width

    def get_line_dash(self):
        return self._line_dash

# ===== MARKER

class TitleDisplay(Enum):
    NO_DISPLAY     = 1
    INSIDE_SYMBOL  = 2
    NEXT_TO_SYMBOL = 3

class Marker:

    def __init__(self, fill_color: Color,
                 label:str = None,
                 scale:float = None,
                 text_style: TextStyle = DEFAULT_TEXT_STYLE,
                 title_display: TitleDisplay = TitleDisplay.NO_DISPLAY,
                 shape: Shape = Shape.CIRCLE,
                 marker_id: str|None = None):
        '''label: name for the class of things represented by the marker'''
        self._fill_color = to_color(fill_color)
        self._label = label
        self._scale = scale
        self._text_style = text_style
        self._title_display = title_display
        self._shape = shape
        self._id = marker_id or 'marker%s' % id(self)

    def get_id(self):
        return self._id

    def get_label(self):
        return self._label

    def get_fill_color(self):
        return self._fill_color

    def get_shape(self):
        return self._shape

    def get_text_style(self):
        return self._text_style

    def get_scale(self) -> float:
        return self._scale

    def get_line_color(self):
        return to_color('black')

    def get_line_width(self):
        return 1.5

    def get_text_color(self):
        return to_color('black')

    def set_scale(self, scale: float):
        self._scale = scale

    def get_title_display(self) -> TitleDisplay:
        return self._title_display

class PositionedMarker:

    def __init__(self, lat: float, lng: float, title: str, marker: Marker,
                 data: dict = {}):
        self._lat = float(lat)
        self._lng = float(lng)
        self._title = title
        self._marker = marker
        self._data = data

    def get_id(self):
        return 'posm%s' % id(self)

    def get_latitude(self):
        return self._lat

    def get_longitude(self):
        return self._lng

    def get_title(self):
        return self._title

    def get_marker(self):
        return self._marker

    def get_description(self):
        return None

    def get_data(self):
        return self._data

    def get_text_inside_symbol(self) -> str|None:
        'This is the text we display inside the circle/triangle/...'
        if self._marker._title_display == TitleDisplay.INSIDE_SYMBOL:
            return self._title
        else:
            return None

# ===== LEGEND

class Legend:

    def __init__(self, location = ('top', 'right'), scale = 1.5,
                 sortkeyfunc = None):
        self._location = location
        self._scale = scale
        self._sortkeyfunc = sortkeyfunc

    def get_location(self):
        return self._location

    def get_scale(self):
        return self._scale

    def get_sorting_key_function(self):
        return self._sortkeyfunc

# ===== LAYERS

class ShapeLayer:

    def __init__(self, geometry_file: str, line: Optional[LineFormat],
                 fill_color: Optional[Color], fill_opacity: Optional[float],
                 selectors: list = []):
        self._geometry_file = geometry_file
        self._line = line
        self._fill_color = fill_color
        self._fill_opacity = fill_opacity
        self._selectors = selectors

    def get_geometry_file(self):
        return self._geometry_file

    def get_line_format(self):
        return self._line

    def get_fill_color(self):
        return self._fill_color

    def get_fill_opacity(self):
        return self._fill_opacity

    def get_selectors(self):
        return self._selectors

class RasterLayer:

    def __init__(self, rasterfile, stops):
        self._rasterfile = rasterfile
        self._stops = stops

    def get_raster_file(self):
        return self._rasterfile

    def get_stops(self):
        return self._stops

# ===== BASE MAP

class AbstractMap:

    def __init__(self):
        self._markers = []
        self._symbols = set() # legend gets built from this
        self._layers = []
        self._legend = None
        self._labels = []

    def add_shapes(self,
                   geometry_file: str,
                   line_color: Optional[str] = None,
                   line_width: Optional[float] = None,
                   line_dash: Optional[tuple] = None,
                   fill_color: Optional[str] = None,
                   fill_opacity: Optional[float] = None,
                   selectors: Optional[list] = None) -> None:
        line = to_line_format(line_color, line_width, line_dash)
        self._layers.append(ShapeLayer(geometry_file, line,
                                       to_color(fill_color),
                                       fill_opacity,
                                       selectors))

    def add_raster(self, rasterfile, stops):
        self._layers.append(RasterLayer(rasterfile, stops))

    def add_text_label(self, lat: float, lng: float, text: str, style) -> None:
        self._labels.append((text, lat, lng, style))

    def set_legend(self, legend):
        if legend is True:
            legend = Legend()
        self._legend = legend

    def add_marker(self, lat: float, lng: float, title: str,
                   marker: Marker, descr : str|None = None,
                   data: dict = {}):
        self._markers.append(PositionedMarker(lat, lng, title, marker, data))
        self._symbols.add(marker)

    def get_marker_types(self):
        return self._symbols

    def get_markers(self):
        return self._markers

    # this is entirely based on add_shapes -- no fundamental code
    def add_choropleth(self,
                       geometry_file: str,
                       region_mapping: list,
                       line_color: Optional[str] = None,
                       line_width: Optional[float] = None,
                       undefined_color: Optional[str] = None,
                       levels: int = 10,
                       label_formatter = None):
        line = to_line_format(line_color, line_width)
        undefined_color = to_color(undefined_color) or Color(0.6, 0.6, 0.6)
        label_formatter = label_formatter or \
            (lambda low, high: '%s - %s' % (low, high))

        values = [v for (_, _, v) in region_mapping if v is not None]
        lowest = min(values)
        biggest = max(values)
        inc = (biggest - lowest) / levels

        colormapping = {}
        colors = make_color_scale(levels)
        for (idprop, idvalue, value) in region_mapping:
            ix = int(round((value - lowest) / inc)) if value is not None else None
            color = colors[ix] if ix is not None else undefined_color

            if color not in colormapping:
                colormapping[color] = []
            colormapping[color].append((idprop, idvalue))

        for (color, selectors) in colormapping.items():
            fill_opacity = 1.0
            self._layers.append(ShapeLayer(
                geometry_file, line, color, fill_opacity, selectors
            ))

        for (ix, color) in enumerate(colors):
            low = lowest + (ix * inc)
            high = lowest + ((ix+1) * inc)
            label = label_formatter(low, high)
            self._symbols.add(Marker(fill_color = colors[ix], label = label))

# ===== CHOROPLETH HELPERS

def make_color_scale(count):
    import colormaps

    inc = int(len(colormaps._magma_data) / count)
    return [
        Color(*tuple([
            x for x in colormaps._magma_data[inc * ix]
        ]))
        for ix in range(count + 1)
    ]

# ===== FILE NAME HANDLING

def add_extension(filename, format):
    extension = {
        'png'   : '.png',
        'html'  : '.html',
        'pdf'   : '.pdf',
        'svg'   : '.svg',
        'latex' : '.tex',
        'tiff'  : '.tif',
        'docx'  : '.docx',
    }[format]
    if not filename.endswith(extension):
        filename += extension
    return filename
