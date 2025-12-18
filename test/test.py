
import unittest, tempfile, os
from pathlib import Path
from PIL import Image
from smappy import mapbase, googlemap, prefab

SHAPEDIR = os.environ.get('SHAPEDIR') # shapefiles must be located here
ROOT = Path(__file__).parent
MIN_SIMILARITY = 5

class BlobCache:

    def get_blob(self, name):
        blob = ROOT / 'blob-cache' / name
        return blob

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
            self.assertTrue('Oslo' in thefile)
            self.assertTrue('Helsinki' in thefile)
            inf.close()

    def test_simple_native_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tstfile = tmpdir + '/' + 'tst'

            rivers = [
               ('name', 'Rhine'),
               ('name', 'Main'),
            ]
            view = prefab.MapView(west = 5, east = 28, north = 56, south = 46,
                                  width = 2000, height = 1600)
            themap = prefab.build_natural_earth(view, SHAPEDIR, rivers = rivers)
            themap.render_to(tstfile)

            base = cache.get_blob('simple-native.png')
            self.assertTrue(img_eq(base, tstfile + '.png'))

    def test_elevation_native_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tstfile = tmpdir + '/' + 'tst'

            view = prefab.MapView(east = 30, west = 4, south = 54.5, north = 65,
                                  width = 1800, height = 1400)
            themap = prefab.build_natural_earth(view, SHAPEDIR,
                                                elevation = True)
            themap.render_to(tstfile)

            base = cache.get_blob('elevation-native.png')
            self.assertTrue(img_eq(base, tstfile + '.png'))

def img_eq(f1, f2):
    return img_diff(f1, f2) < MIN_SIMILARITY

def img_diff(f1, f2):
    img1 = Image.open(f1)
    img2 = Image.open(f2)

    if img1.width != img2.width or img1.height != img2.height:
        return 1_000_000_000

    total = 0
    for (p1, p2) in zip(img1.getdata(), img2.getdata()):
        total += abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) + abs(p1[2] - p2[2])

    length = len(img1.getdata())

    img1.close()
    img2.close()
    return total / (length * 3)

cache = BlobCache()
