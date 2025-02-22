
import glob, json
from smappy import mapbase
import pymapnik3

# --- MAPNIK INITIALIZATION

pymapnik3.register_datasources('/usr/local/lib/mapnik/input/')
for font in glob.glob('/usr/local/lib/mapnik/fonts/*.ttf'):
    pymapnik3.register_font(font)

# --- STUFF

class MapnikMapImplementation:
    def __init__(self, mapview: mapbase.MapView):
        pass

class MapnikChoroplethMap:
    def __init__(self, mapview: mapbase.MapView, levels: int = 10):
        self._map_view = mapview
        self._decorator = mapbase.MapDecorator()
        self._levels = levels
        self._region_file = None
        self._region_mapping = None

        # formatting properties
        self._background = '#FFFFFF'
        self._undefined_color = mapbase.Color(0.6, 0.6, 0.6)
        self._border_format = mapbase.LineFormat('rgb(5%,5%,5%)', 0.2)
        self._label_formatter = lambda low, high: '%s - %s' % (low, high)

    def get_decorator(self):
        return self._decorator

    def set_region_file(self, filename: str):
        self._region_file = filename

    def set_region_mapping(self, mapping: list[tuple]):
        '''mapping: list of (idproperty, idvalue, numvalue). None means value
        not known, will be filled with _undefined_color'''
        self._region_mapping = mapping

    # --- formatting

    def set_background_color(self, color):
        self._background = color

    def set_border_format(self, line_color, line_width):
        self._border_format = mapbase.LineFormat(line_color, line_width)

    def set_label_formatter(self, label_formatter):
        self._label_formatter = label_formatter

    # --- render

    def render_to(self, filename: str):
        values = [v for (_, _, v) in self._region_mapping if v != None]
        lowest = min(values)
        biggest = max(values)
        inc = (biggest - lowest) / float(self._levels)

        colormapping = []
        colors = make_color_scale(self._levels)
        for (idprop, idvalue, value) in self._region_mapping:
            ix = int(round((value - lowest) / inc)) if value != None else None
            color = colors[ix] if ix != None else self._undefined_color
            colormapping.append((idprop, idvalue, color))

        render_colored_region_map(filename, self._map_view, self._background,
                                  colormapping, self._region_file,
                                  self._decorator, self._border_format)

        symbols = []
        for ix in range(self._levels):
            low = lowest + (ix * inc)
            high = lowest + ((ix+1) * inc)
            label = self._label_formatter(low, high)
            symbols.append(mapbase.Marker(fill_color = colors[ix],
                                          label = label))

        legend = self._decorator.get_legend()
        if legend:
            add_legend(filename, symbols, legend)

def render_colored_region_map(filename, view, background, colormapping,
                              region_file, decorator, border_format):
    m = pymapnik3.Map(view.width, view.height)
    ctx = pymapnik3.Context()

    m.set_srs('+proj=merc +ellps=WGS84 +datum=WGS84 +no_defs')
    m.set_background(pymapnik3.Color(background))

    s = pymapnik3.Style() # style object to hold rules

    for (prop, value, color) in colormapping:
        rule = make_region_rule(color, border_format)
        rule.set_filter(pymapnik3.Expression("[%s] = '%s'" % (
            prop, value)
        ))
        s.add_rule(rule) # now add the rule to the style

    m.add_style('My Style',s)

    if region_file.endswith('.json'):
        ds = pymapnik3.GeoJSON(region_file)
    elif region_file.endswith('.shp'):
        ds = pymapnik3.Shapefile(region_file)
    else:
        assert False, 'Unknown region file format: %s' % region_file
    layer = pymapnik3.Layer('world')

    layer.set_datasource(ds)
    layer.set_srs('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
    layer.add_style('My Style')

    m.add_layer(layer)

    add_decorator(m, ctx, decorator)

    zoom_to_box(m, view)

    pymapnik3.render_to_file(m, filename, 'PNG')

def make_region_rule(color, border_format):
    r = pymapnik3.Rule() # rule object to hold symbolizers
    # to fill a polygon we create a PolygonSymbolizer
    polygon_symbolizer = pymapnik3.PolygonSymbolizer()
    polygon_symbolizer.set_fill(mapnik_color(color))
    r.add_symbolizer(polygon_symbolizer) # add the symbolizer to the rule object

    # to add outlines to a polygon we create a LineSymbolizer
    line_symbolizer = pymapnik3.LineSymbolizer()
    line_symbolizer.set_stroke(mapnik_color(border_format.get_line_color()))
    line_symbolizer.set_stroke_width(border_format.get_line_width())
    r.add_symbolizer(line_symbolizer) # add the symbolizer to the rule object
    return r

def make_color_scale(count):
    import colormaps

    inc = int(len(colormaps._magma_data) / count)
    return [
        mapbase.Color(*tuple([
            x for x in colormaps._magma_data[inc * ix]
        ]))
        for ix in range(count + 1)
    ]

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

def add_decorator(m, ctx, decorator):
    # ===== TEXT STYLES
    s = pymapnik3.Style()
    for tstyle in decorator.get_text_styles():
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

    for (text, lat, lon, style) in decorator.get_text_labels():
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

    # ===== SHAPES
    for (ix, (geometry_file, line_format)) in enumerate(decorator.get_shapes()):
        s = pymapnik3.Style() # style object to hold rules

        r = pymapnik3.Rule() # rule object to hold symbolizers

        # to add outlines to a polygon we create a LineSymbolizer
        line_symbolizer = pymapnik3.LineSymbolizer()
        line_symbolizer.set_stroke(mapnik_color(line_format.get_line_color()))
        line_symbolizer.set_stroke_width(line_format.get_line_width())
        r.add_symbolizer(line_symbolizer) # add the symbolizer to the rule object
        s.add_rule(r) # now add the rule to the style

        m.add_style('ShapeStyle%s' % ix, s)

        if geometry_file.endswith('.shp'):
            ds = pymapnik3.Shapefile(geometry_file)
        else:
            ds = pymapnik3.GeoJSON(geometry_file)
        layer = pymapnik3.Layer('shapes%s' % ix)

        layer.set_datasource(ds)
        layer.set_srs('+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs')
        layer.add_style('ShapeStyle%s' % ix)

        m.add_layer(layer)

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
