
from smappy import mapbase, mapniklib

class MapStyle:

    def __init__(self):
        self._border_fill_color = '#409050'
        self._border_line_color = 'rgb(10%,10%,10%)'
        self._border_line_width = 1.5

        self._lake_fill_color = '#88CCFF'
        self._glacier_fill_color = '#eeeeee'

default_map_style = MapStyle()

def _norway_montage(filename, legend_box):
    # hacky workaround for broken PIL
    import os
    os.system('gm convert %s /tmp/tst.gif' % filename)

    tmpfile = '/tmp/tst.png'
    os.system('gm convert /tmp/tst.gif %s' % tmpfile)
    #shutil.copyfile(filename, tmpfile)
    # </hack>

    from PIL import Image, ImageDraw
    im = Image.open(open(tmpfile, 'rb'))

    # crop: (left, upper, right, lower)
    southern_no = im.crop((0, 1440, 720, 2500))   # 720x1060
    northern_no = im.crop((530, 380, 1250, 1440)) # 720x1060

    composite = Image.new('RGB', (1440, 1060))
    composite.paste(southern_no, (0, 0))
    composite.paste(northern_no, (720, 0))

    if legend_box:
        ((x1, y1), (x2, y2)) = legend_box
        legend = im.crop((x1, y1, x2, y2))
        composite.paste(legend, (10, 10))

    draw = ImageDraw.Draw(composite)
    draw.line((720, 0, 720, 1060), (0, 0, 0))

    composite.save(filename, 'PNG')

MapView = mapbase.MapView
map_views = {
    'nordic' : MapView(east = 4, west = 30, south = 54.5, north = 65,
                       width = 1800, height = 1400),
    'norway' : MapView(east = 14.8, west = 3.5, south = 57.9, north = 63.9,
                       width = 1200, height = 1250),
    'arctic-norway' : MapView(east = 20, west = 30, south = 65, north = 71.5,
                              width = 1200, height = 800),
    'mid-norway' : MapView(east = 7.5, west = 10, south = 59, north = 63,
                           width = 1400, height = 1200),
    'norway-montage' : MapView(east = 6, west = 30, south = 57.9, north = 71.5,
                               width = 2200, height = 2500,
                               transform = _norway_montage),
    'norway-south' : MapView(east = 6, west = 11, south = 58.0, north = 62,
                               width = 1400, height = 1400),
    'norway-west' : MapView(east = 6, west = 9, south = 60, north = 63,
                               width = 1400, height = 1200),
    'west-nordic' : MapView(east = -4, west = 25, south = 52.5, north = 63.5,
                            width = 1800, height = 1400),
    'europe-all-big' : MapView(east = -15, west = 50, south = 34, north = 71,
                               width = 2000, height = 1600),
    'norway-sweden' : MapView(east = 6, west = 18, south = 57.9, north = 63.9,
                              width = 1800, height = 1200),
    'europe' : MapView(east = 4, west = 50, south = 50, north = 65),
    'europe-trim' : MapView(east = -3, west = 54, south = 50, north = 62.5,
                           width = 2000, height = 1400),
    'europe-all' : MapView(east = -7, west = 57, south = 47.5, north = 62.5,
                           width = 2000, height = 1400),
    'west-europe' : MapView(east = -4, west = 28, south = 52.5, north = 63.5,
                            width = 2000, height = 1600),
    'south-finland' : MapView(east = 23, west = 27, south = 59, north = 64),
    'baltic' : MapView(east = 24, west = 26, south = 53.5, north = 59.7,
                       width = 1600, height = 1200),
    'denmark' : MapView(east = 15.3, west = 7.8, south = 54.5, north = 57.9,
                        width = 1400, height = 1200),
    'estonia' : MapView(east = 24, west = 25.7, south = 57.5, north = 59.7,
                        width = 1600, height = 1000),
    'georgia' : MapView(east = 41, west = 49, south = 40, north = 45,
                        width = 1600, height = 800),
    'world' : MapView(east = -160, west = 160, south = -57, north = 84,
                      width = 3000, height = 2000),
    'germany' : MapView(east = 5, west = 24, south = 47, north = 56,
                      width = 2000, height = 1600),
    'ukraine' : MapView(north = 52.6, west = 21.7,
                        south = 44.4, east = 41.6,
                        width = 2000, height = 1600),
    'finland' : MapView(north = 70.24, west = 19.43,
                        south = 59.44, east = 33,
                        width = 1000, height = 2000),
}

def build_natural_earth(view, shapedir, map_style = default_map_style):
    themap = mapniklib.MapnikMap(view,
                                 background_color = map_style._lake_fill_color)

    borders = shapedir + '/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp'
    themap.add_shapes(borders,
                      line_color = map_style._border_line_color,
                      line_width = map_style._border_line_width,
                      fill_color = map_style._border_fill_color)

    lakes = shapedir + 'ne_10m_lakes/ne_10m_lakes.shp'
    themap.add_shapes(lakes,
                      fill_color = map_style._lake_fill_color)

    chosen_rivers = [
        ('name', 'Volga'),
        ('name', 'Dnipro'),
        ('name', 'Don'),
        ('name', 'Kama'),
        ('name', 'Tigris'),
        ('name', 'Euphrates'),
        ('name', 'Nile'),
        ('name', 'Rosetta Branch'),
        ('name', 'Damietta Branch'),
        ('dissolve', '634River'),
    ]

    rivers = shapedir + 'ne_10m_rivers_lake_centerlines/ne_10m_rivers_lake_centerlines.shp'
    themap.add_shapes(rivers,
                      line_color = map_style._lake_fill_color,
                      line_width = 0.8,
                      selectors = chosen_rivers)

    glaciers = shapedir + 'ne_10m_glaciated_areas/ne_10m_glaciated_areas.shp'
    themap.add_shapes(glaciers,
                      fill_color = map_style._glacier_fill_color)

    return themap
