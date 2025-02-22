
import glob, json
from smappy import mapbase
import pymapnik3

# --- MAPNIK INITIALIZATION

# FIXME: pymapnik should take care of this for us
pymapnik3.register_datasources('/usr/local/lib/mapnik/input/')
for font in glob.glob('/usr/local/lib/mapnik/fonts/*.ttf'):
    pymapnik3.register_font(font)

# --- STUFF

class MapnikMap:
    def __init__(self, mapview: mapbase.MapView, background_color: str = None):
        self._view = mapview
        self._background = mapbase.to_color(background_color or '#88CCFF')
        self._layers = []
        self._symbols = [] # legend gets built from this
        self._legend = None
        self._labels = []

    def add_shapes(self,
                   geometry_file: str,
                   line_color: str = None,
                   line_width: float = None,
                   fill_color: str = None,
                   selectors: list = None):
        line = mapbase.to_line_format(line_color, line_width)
        self._layers.append(mapbase.ShapeLayer(geometry_file, line,
                                               mapbase.to_color(fill_color),
                                               selectors))

    # this is entirely based on add_shapes -- no fundamental code
    def add_choropleth(self,
                       geometry_file: str,
                       region_mapping: list,
                       line_color: str = None,
                       line_width: float = None,
                       undefined_color: str = None,
                       levels: int = 10,
                       label_formatter = None):
        line = mapbase.to_line_format(line_color, line_width)
        undefined_color = mapbase.to_color(undefined_color) or \
            mapbase.Color(0.6, 0.6, 0.6)
        label_formatter = label_formatter or \
            (lambda low, high: '%s - %s' % (low, high))

        values = [v for (_, _, v) in region_mapping if v != None]
        lowest = min(values)
        biggest = max(values)
        inc = (biggest - lowest) / levels

        colormapping = {}
        colors = make_color_scale(levels)
        for (idprop, idvalue, value) in region_mapping:
            ix = int(round((value - lowest) / inc)) if value != None else None
            color = colors[ix] if ix != None else undefined_color

            if not color in colormapping:
                colormapping[color] = []
            colormapping[color].append((idprop, idvalue))

        for (color, selectors) in colormapping.items():
            self._layers.append(mapbase.ShapeLayer(
                geometry_file, line, color, selectors
            ))

        for (ix, color) in enumerate(colors):
            low = lowest + (ix * inc)
            high = lowest + ((ix+1) * inc)
            label = label_formatter(low, high)
            self._symbols.append(mapbase.Marker(fill_color = colors[ix],
                                                label = label))

    def add_text_label(self, text: str, lat: float, lng: float, style):
        self._labels.append((text, lat, lng, style))

    def set_legend(self, legend):
        if legend is True:
            legend = mapbase.Legend()
        self._legend = legend

    def render_to(self, filename: str):
        m = pymapnik3.Map(self._view.width, self._view.height)
        ctx = pymapnik3.Context()
        m.set_srs('+proj=merc +ellps=WGS84 +datum=WGS84 +no_defs')
        m.set_background(mapnik_color(self._background))

        for layer in self._layers:
            render_layer(m, ctx, layer)

        styles = set([style for (_, _, _, style) in self._labels])
        render_text_labels(m, ctx, styles, self._labels)

        zoom_to_box(m, self._view)
        pymapnik3.render_to_file(m, filename, 'PNG')

        if self._legend:
            add_legend(filename, self._symbols, self._legend)

# ===== CHOROPLETH HELPERS

def make_color_scale(count):
    import colormaps

    inc = int(len(colormaps._magma_data) / count)
    return [
        mapbase.Color(*tuple([
            x for x in colormaps._magma_data[inc * ix]
        ]))
        for ix in range(count + 1)
    ]

# ===== RENDERING

def render_layer(m, ctx, layer):
    theid = 'id' + str(id(layer))

    if isinstance(layer, mapbase.ShapeLayer):
        s = pymapnik3.Style() # style object to hold rules
        r = pymapnik3.Rule() # rule object to hold symbolizers

        expression = build_expression(layer.get_selectors())
        if expression:
            r.set_filter(expression)

        line = layer.get_line_format()
        if line:
            line_symbolizer = pymapnik3.LineSymbolizer()
            line_symbolizer.set_stroke(mapnik_color(line.get_line_color()))
            line_symbolizer.set_stroke_width(line.get_line_width())
            r.add_symbolizer(line_symbolizer)
            s.add_rule(r)

        if layer.get_fill_color():
            polygon_symbolizer = pymapnik3.PolygonSymbolizer()
            polygon_symbolizer.set_fill(mapnik_color(layer.get_fill_color()))
            r.add_symbolizer(polygon_symbolizer)
            s.add_rule(r)

        m.add_style('ShapeStyle%s' % theid, s)

        geometry_file = layer.get_geometry_file()
        if geometry_file.endswith('.shp'):
            ds = pymapnik3.Shapefile(geometry_file)
        else:
            ds = pymapnik3.GeoJSON(geometry_file)
        layer = pymapnik3.Layer('shapes%s' % theid)

        layer.set_datasource(ds)
        layer.set_srs('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        layer.add_style('ShapeStyle%s' % theid)

        m.add_layer(layer)

    else:
        assert False

def build_expression(selectors: list):
    if not selectors:
        return None

    expr = ' or '.join(["[%s] = '%s'" % (prop, val)
                        for (prop, val)
                        in selectors])
    return pymapnik3.Expression(expr)

def render_text_labels(m, ctx, text_styles, labels):
    # ===== TEXT STYLES
    s = pymapnik3.Style()
    for tstyle in text_styles:
        r = pymapnik3.Rule()
        r.set_filter(pymapnik3.Expression("[style] = '%s'" % tstyle.get_id()))

        ts = pymapnik3.TextSymbolizer()
        ts.set_fill(mapnik_color(tstyle.get_font_color()))
        ts.set_text_size(tstyle.get_font_size())
        ts.set_face_name(tstyle.get_font_name())
        ts.set_name_expression('[text]')
        ts.set_halo_fill(mapnik_color(tstyle.get_halo_color()))
        ts.set_halo_radius(tstyle.get_halo_radius())
        r.add_symbolizer(ts)
        s.add_rule(r)
    m.add_style('text_style', s)

    # ===== TEXTS
    ds = pymapnik3.MemoryDatasource()

    for (text, lat, lon, style) in labels:
        f = pymapnik3.parse_from_geojson(json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)]
            },
            'properties' : {
                'style' : style.get_id(),
                'text'  : text
            }
        }), ctx)
        ds.add_feature(f)

    l = pymapnik3.Layer('layer_texts')
    l.set_clear_label_cache(True)
    l.set_datasource(ds)
    l.add_style('text_style')
    m.add_layer(l)

def project(srs, west, south, east, north):
    source = pymapnik3.Projection('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
    target = pymapnik3.Projection(srs)
    trans = pymapnik3.ProjTransform(source, target)
    thebox = pymapnik3.Box2d(west, south, east, north)
    return trans.forward(thebox)

def zoom_to_box(themap, view):
    # the box is defined in degrees when passed in to us, but now that
    # the projection is Mercator, the bounding box must be specified
    # in metres (no, I don't know why). we solve this by explicitly
    # converting degrees to metres
    themap.zoom_to_box(project(themap.get_srs(), view.west, view.south,
                               view.east, view.north))

def add_legend(filename, used_symbols, legend):
    from PIL import Image, ImageDraw, ImageFont

    legend_scale = legend.get_scale()
    im = Image.open(filename)

    r = 12 * legend_scale
    font = ImageFont.truetype('Arial.ttf', int(r * 2))

    widest = 0
    for symbol in used_symbols:
        (left, top, right, bottom) = font.getbbox(symbol.get_label())
        width = right - left
        widest = max(widest, width)

    offset = 10 * legend_scale
    boxwidth = r * 2 + offset * 3 + widest
    displace = (r * 2) + 12 * legend_scale
    boxheight = displace * len(used_symbols) + offset

    (vertpos, horpos) = legend.get_location()
    assert vertpos in ('top', 'bottom')
    assert horpos in ('left', 'right')

    if vertpos == 'top':
        y1 = offset
        y2 = offset + boxheight
    else:
        (width, height) = im.size
        y1 = height - (boxheight + offset)
        y2 = height - offset

    if horpos == 'left':
        x1 = offset
        x2 = offset + boxwidth
    else:
        (width, height) = im.size
        x1 = width - (offset + boxwidth)
        x2 = width - offset

    box = [(x1, y1), (x2, y2)]

    draw = ImageDraw.Draw(im)
    draw.rectangle(
        box,
        outline = (0, 0, 0),
        fill = (255, 255, 255),
        width = int(2 * legend_scale),
    )

    for ix in range(len(used_symbols)):
        displacement = displace * ix

        symbol = used_symbols[ix]
        if symbol.get_shape() == mapbase.Shape.CIRCLE:
            draw.ellipse(
                [
                    (x1 + offset, y1 + offset + displacement),
                    (x1 + offset + (r * 2), y1 + offset + (r * 2) + displacement)
                ],
                outline = (0, 0, 0),
                fill = symbol.get_fill_color().as_int_tuple(256)
            )

        elif symbol.get_shape() == maplib.TRIANGLE:
            draw.polygon(
                [
                    (x1 + offset + r, y1 + offset + displacement),
                    (x1 + offset, y1 + offset + r*2 + displacement),
                    (x1 + offset + r*2, y1 + offset + r*2 + displacement)
                ],
                outline = (0, 0, 0),
                fill = symbol.get_fill_color().as_int_tuple(256)
            )

        else:
            assert False, 'Unsupported shape: %s' % symbol.get_shape()

        offset = 8 * legend_scale
        draw.text(
            (x1 + 20 * legend_scale + (r * 2), y1 + offset + displacement),
            text = symbol.get_label(),
            fill = (0, 0, 0),
            font = font,
        )

    #im.show()
    im.save(filename, 'PNG')
    return box

def mapnik_color(color: mapbase.Color):
    return pymapnik3.Color(color.as_hex())
