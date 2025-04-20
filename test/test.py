
import unittest, tempfile, os
from smappy import mapbase, googlemap, prefab

SHAPEDIR = os.environ.get('SHAPEDIR') # shapefiles must be located here

class TestMaps(unittest.TestCase):

    def test_simple_google(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tstfile = tmpdir + '/' + 'tst.html'

            themap = googlemap.GoogleMap(61.8, 9.45, 6, 'GOOGLE_MAPS_KEY')

            m1 = mapbase.Marker('black')
            themap.add_marker(59, 20, 'Oslo', m1)

            m2 = mapbase.Marker('white')
            themap.add_marker(60, 30, 'Helsinki', m2)

            themap.render_to(tstfile)

            inf = open(tstfile)
            thefile = inf.read()
            self.assertTrue('GOOGLE_MAPS_KEY' in thefile)
            inf.close()

    def test_simple_mapnik(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tstfile = tmpdir + '/' + 'tst.png'

            view = prefab.map_views['nordic']
            themap = prefab.build_natural_earth(view, SHAPEDIR)

            m1 = mapbase.Marker('black')
            themap.add_marker(59, 20, 'Oslo', m1)

            m2 = mapbase.Marker('white')
            themap.add_marker(60, 30, 'Helsinki', m2)

            themap.render_to(tstfile)
