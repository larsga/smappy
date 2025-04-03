
import json
from typing import Optional
from smappy import mapbase
import pymapnik3

# --- STUFF

class MapnikMap(mapbase.AbstractMap):
    def __init__(self, mapview: mapbase.MapView,
                 background_color: Optional[str] = None):
        mapbase.AbstractMap.__init__(self)
        self._view = mapview
        self._background = mapbase.to_color(background_color or '#88CCFF')
        self._legend = None
        self._labels = []

    def add_shapes(self,
                   geometry_file: str,
                   line_color: Optional[str] = None,
                   line_width: Optional[float] = None,
                   line_dash: Optional[tuple] = None,
                   fill_color: Optional[str] = None,
                   fill_opacity: Optional[float] = None,
                   selectors: Optional[list] = None):
        line = mapbase.to_line_format(line_color, line_width, line_dash)
        self._layers.append(mapbase.ShapeLayer(geometry_file, line,
                                               mapbase.to_color(fill_color),
                                               fill_opacity,
                                               selectors))

    def add_text_label(self, text: str, lat: float, lng: float, style):
        self._labels.append((text, lat, lng, style))

    def set_legend(self, legend):
        if legend is True:
            legend = mapbase.Legend()
        self._legend = legend

    def render_to(self, filename: str, format: str = 'png'):
        filename = mapbase.add_extension(filename, format)

        m = pymapnik3.Map(self._view.width, self._view.height)
        ctx = pymapnik3.Context()
        m.set_srs('+proj=merc +ellps=WGS84 +datum=WGS84 +no_defs')
        m.set_background(mapnik_color(self._background))

        for layer in self._layers:
            render_layer(m, ctx, layer)

        default_scale = self._get_default_scale()
        for mt in self.get_marker_types():
            if mt.get_scale() is None:
                mt.set_scale(default_scale)

        render_markers(m, ctx, self.get_marker_types(), self._markers)

        styles = set([style for (_, _, _, style) in self._labels])
        render_text_labels(m, ctx, styles, self._labels)

        zoom_to_box(m, self._view)
        pymapnik3.render_to_file(m, filename, format)

        if self._legend:
            add_legend(filename, self._symbols, self._legend)

    def _get_default_scale(self) -> float:
        size = max(self._view.height, self._view.width)
        factor = 0.005
        return size * factor

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
            dash = line.get_line_dash()
            if dash:
                (length, gap) = dash
                line_symbolizer.set_stroke_dash(length, gap)
            r.add_symbolizer(line_symbolizer)
            s.add_rule(r)

        if layer.get_fill_color():
            polygon_symbolizer = pymapnik3.PolygonSymbolizer()
            polygon_symbolizer.set_fill(mapnik_color(layer.get_fill_color()))
            polygon_symbolizer.set_fill_opacity(layer.get_fill_opacity() or 1.0)
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

def build_expression(selectors: Optional[list]):
    if not selectors:
        return None

    expr = ' or '.join(["[%s] = '%s'" % (prop, val)
                        for (prop, val)
                        in selectors])
    return pymapnik3.Expression(expr)

def render_markers(m, ctx, marker_types, markers):
    # ===== MARKER TYPES
    for marker in marker_types:
        svgfile = '/tmp/%s.svg' % marker.get_id()
        generate_marker_svg(marker, svgfile)

        if not marker.get_show_title():
            sym = pymapnik3.PointSymbolizer()
            sym.set_allow_overlap(True)
            sym.set_ignore_placement(True)
        else:
            style = marker.get_text_style()
            sym = pymapnik3.ShieldSymbolizer()
            sym.set_fill(mapnik_color(style.get_font_color()))
            sym.set_text_size(style.get_font_size())
            sym.set_face_name(style.get_font_name())
            sym.set_name_expression('[name]')
            sym.set_halo_fill(mapnik_color(style.get_halo_color()))
            sym.set_halo_radius(style.get_halo_radius())
            sym.set_displacement(10, 0)

        sym.set_file(svgfile)

        r = pymapnik3.Rule()
        r.add_symbolizer(sym)

        s = pymapnik3.Style()
        s.add_rule(r)

        m.add_style('symbol_%s' % marker.get_id(), s)

    # ===== MARKERS
    for (ix, marker) in enumerate(markers):
        f = pymapnik3.parse_from_geojson(json.dumps({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [marker.get_longitude(), marker.get_latitude()]
            },
            'properties' : {
                'name' : marker.get_title()
            }
        }), ctx)

        ds = pymapnik3.MemoryDatasource()

        layer = pymapnik3.Layer('marker_layer_%s' % ix)
        layer.set_clear_label_cache(True)
        layer.set_datasource(ds)
        layer.add_style('symbol_%s' % marker.get_marker().get_id())

        m.add_layer(layer)

        ds.add_feature(f)

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

    layer = pymapnik3.Layer('layer_texts')
    layer.set_clear_label_cache(True)
    layer.set_datasource(ds)
    layer.add_style('text_style')
    m.add_layer(layer)

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

def add_legend(filename, symbols, legend):
    from PIL import Image, ImageDraw, ImageFont

    used_symbols = list(symbols)

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

        elif symbol.get_shape() == mapbase.Shape.TRIANGLE:
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

def generate_marker_svg(marker, svgfile):
    with open(svgfile, 'w') as f:
        padding = 2
        viewsize = (marker.get_scale()+padding) * 2
        size = marker.get_scale() * 2
        mid = marker.get_scale() + padding / 2.0
        radius = marker.get_scale()

        match marker.get_shape():
            case mapbase.Shape.CIRCLE:
                f.write('''
                    <svg viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="%s" cy="%s" r="%s" stroke="%s" fill="%s"
                              stroke-width="%s"/>
                    </svg>
                ''' % (
                    viewsize,
                    viewsize,
                    mid,
                    mid,
                    radius,
                    marker.get_line_color().as_hex(),
                    marker.get_fill_color().as_hex(),
                    marker.get_line_width()
                ))

            case mapbase.Shape.SQUARE:
                f.write('''
                    <svg viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg">
                      <rect width="%s" height="%s" stroke="%s" fill="%s"/>
                    </svg>
                ''' % (
                    size,
                    size,
                    size,
                    size,
                    marker.get_line_color().as_hex(),
                    marker.get_fill_color().as_hex()
                ))

            case mapbase.Shape.TRIANGLE:
                topx = size / 2.0
                topy = 0

                botleftx = 0
                botlefty = size

                botrightx = size
                botrighty = size

                f.write('''
                    <svg viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg">
                      <polygon points="%s,%s %s,%s %s,%s"
                               stroke="%s" fill="%s" />
                    </svg>
                ''' % (
                    size,
                    size,
                    topx,
                    topy,
                    botleftx,
                    botlefty,
                    botrightx,
                    botrighty,
                    marker.get_line_color().as_hex(),
                    marker.get_fill_color().as_hex()
                ))

            case _:
                raise mapbase.SmappyException('Unknown shape: %s' %
                                              marker.get_shape())
