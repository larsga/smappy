
# smappy

A simple mapping engine in pure Python3 with a Python API. Can produce
static maps in PNG and PDF format, as well as Google Maps in
HTML/JavaScript.  Supports Shapefiles, GeoJSON, and GeoTIFF input.

Still in early phases of development, but usable.

Features:

  * Configurable maps based on Natural Earth data.
  * Configurable display of Shapefiles and GeoJSON from any source.
  * Adding markers, optionally with text labels.
  * Adding text labels without markers.
  * Raster data overlay.
  * Choropleth maps.
  * Legends.

## Natural Earth examples

If you first download and unzip [Natural
Earth](https://www.naturalearthdata.com) shapefiles into the folder
`/foo`, running this script:

```
from smappy import prefab

view = prefab.map_views['nordic']
themap = prefab.build_natural_earth(view, '/foo')
themap.render_to('demo')
```

Will produce this map in PNG format:

You can load a TOML file to change the layout (this file is built-in):

```
from smappy import prefab

view = prefab.map_views['nordic']
map_style = prefab.load_map_style('grayscale')
themap = prefab.build_natural_earth(view, '/foo')
themap.render_to('demo')
```

That will produce this map in PNG format:

If you download and unzip
[ETOPO1](https://www.ncei.noaa.gov/products/etopo-global-relief-model)
elevation data into the same folder, you can also add elevations:

```
from smappy import prefab

view = prefab.map_views['nordic']
themap = prefab.build_natural_earth(view, '/foo', elevation = True)
themap.render_to('demo')
```

Here is the map with elevations:

The maps can also be decorated with text labels and markers:

```
import os, csv, sys
from smappy import prefab, mapbase

map_style = prefab.default_map_style
map_style.set_border_line_width(2.5)

view = prefab.map_views['germany']
themap = prefab.build_natural_earth(view, os.environ['SHAPEDIR'],
                                    map_style = map_style,
                                    elevation = True)

place_text = mapbase.TextStyle(
   font_size = 29,
    font_name = 'DejaVuSerif.ttf',
    font_color = 'black',
    halo_color = 'white',
    halo_radius = 3,
)

marker = mapbase.Marker(
    '#FFFF00',
    text_style = place_text,
    title_display = mapbase.TitleDisplay.NEXT_TO_SYMBOL
)

for row in csv.DictReader(open('first-lager-brewery.csv'), delimiter = ';'):
    lat = float(row['Lat'])
    lng = float(row['Long'])
    year = int(row['Year'])

themap.render_to('lager-map')
```

The output looks like this:
