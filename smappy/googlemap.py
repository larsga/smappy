'''
Smappy implementation producing HTML Google Maps.
'''

import json
from smappy import mapbase

class GoogleMap(mapbase.AbstractMap):

    def __init__(self, center_lat: float, center_lng: float, zoom: int,
                 apikey: str):
        mapbase.AbstractMap.__init__(self)
        self._center_lat = center_lat
        self._center_lng = center_lng
        self._zoom = zoom
        self._apikey = apikey

    def get_id(self):
        return 'id%s' % id(self)

    def get_center_longitude(self):
        return self._center_lng

    def get_center_latitude(self):
        return self._center_lat

    def get_zoom_level(self):
        return self._zoom

    def get_api_key(self):
        return self._apikey

    def render_to(self, filename:str , width: str = '100%',
                  height: str = '100%', format: str = 'html'):
        if format != 'html':
            raise mapbase.SmappyException('Incorrect format "%s"' % format)

        filename = mapbase.add_extension(filename, format)
        _render(self, filename, width, height)

# ===== RENDERING

def _to_jstr(value):
    if value == None:
        return 'null'

    return "'%s'" % value.replace("'", "\\'")

def _render(themap, filename, width = '100%', height = '100%', bottom = ''):
    outf = open(filename, 'w', encoding = 'utf-8')
    outf.write('''
<meta name="viewport" content="width=device-width"> <!-- mobile scaling -->
<meta http-equiv="content-type" content="text/html; charset=utf-8">
<script src="https://maps.googleapis.com/maps/api/js?sensor=false&key=%s" type="text/javascript"></script>
<style>
body {
  font-family: Arial, sans-serif;
}
div.listing {
  display: none;
  width: 500px;
}
div.infowindow {
  display: normal;
  width: 350px;
  font-size: 8pt;
}
#legend {
  background: #fff;
  padding: 10px;
  margin: 10px;
  border: 3px solid #000;
}
</style>

<div id="%s" style="width: %s; height: %s"></div>

<script type="text/javascript">
var mapOptions = {
  center: new google.maps.LatLng(%s, %s),
  zoom: %s,
  streetViewControl: false,
  mapTypeControl: false
};
var map = new google.maps.Map(document.getElementById('%s'), mapOptions);

var markers = [];
var marker_dict = {};

function add_marker(theid, lat, lng, title, symbol, label, textcolor, data) {
  var thelabel = null;
  if (label != null) {
    thelabel = new google.maps.Marker({
      text: label,
      color: textcolor
    });
  }

  var marker = new google.maps.Marker({
      position: new google.maps.LatLng(lat, lng),
      map: map,
      title: title,
      icon: symbol,
      label: thelabel
  });

  marker.popupid = theid;
  marker.data = data;
  markers.push(marker);
  marker_dict[theid] = marker;

  google.maps.event.addListener(marker, 'click', function() {
    // retrieve the element to show in the window
    var element = document.getElementById(marker.popupid);

    // we can't pass this element in because it gets destroyed
    // once the window is closed, so we make a copy
    element = element.cloneNode(true);

    // we want the copy displayed small, so we change the class
    element.className = 'infowindow';

    // switch display from off to on
    element.style.display = "";

    var infowindow = new google.maps.InfoWindow({
      content: element
    });

    infowindow.open(map, marker);
  });

  return marker;
}
    ''' % (themap.get_api_key(),
           themap.get_id(),
           width,
           height,
           themap.get_center_latitude(),
           themap.get_center_longitude(),
           themap.get_zoom_level(),
           themap.get_id()))

    for marker in themap.get_marker_types():
        render_marker_type(outf, marker)

    for marker in themap.get_markers():
        outf.write(u"add_marker('%s', %s, %s, %s, %s, %s, %s, %s);\n" %
                   (marker.get_id(),
                    marker.get_latitude(),
                    marker.get_longitude(),
                    _to_jstr(marker.get_title()),
                    marker.get_marker().get_id(),
                    _to_jstr(None), # displayed text label
                    #_to_jstr(marker.get_marker().get_title()),
                    _to_jstr(marker.get_marker().get_text_color().as_hex()),
                    json.dumps(marker.get_data())))

    for layer in themap._layers:
        assert isinstance(layer, mapbase.ShapeLayer)

        render(outf, layer)

    outf.write(u'</script>\n\n\n')

    # if themap.has_legend():
    #     outf.write('<div id="legend">\n')
    #     for symbol in themap.get_symbols():
    #         outf.write('''
    #           <svg height="19" width="16">
    #             <circle cx="8" cy="13" r="5" stroke="black" stroke-width="1"
    #                     fill="%s" />
    #           </svg> %s<br>
    #         ''' % (symbol.get_color(), symbol.get_title()))
    #     outf.write('</div>\n')

    #     outf.write('''
    #       <script>
    #         var legend = document.getElementById('legend');
    #         map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(legend);
    #       </script>
    #     ''')

    for marker in themap.get_markers():
        desc = marker.get_description() or ''
        outf.write(u'''
          <div id="%s" class="listing">
            %s<br>%s</div>
        ''' % (marker.get_id(), marker.get_title(), desc))

    outf.write(bottom)
    outf.close()

def render_marker_type(outf, marker):
        outf.write('''
var %s = {
  fillColor: "%s",
  strokeColor: "%s",
  strokeWeight: %s,
  fillOpacity: 1,
  path: google.maps.SymbolPath.CIRCLE,
  scale: %s
};
        ''' % (marker.get_id(), marker.get_fill_color().as_hex(),
               marker.get_line_color().as_hex(),
               marker.get_line_width(),
               marker.get_scale()))

def render_shape(outf, shape):
    pass
#  // Define the LatLng coordinates for the polygon's path.
#  const triangleCoords = [
#    { lat: 25.774, lng: -80.19 },
#    { lat: 18.466, lng: -66.118 },
#    { lat: 32.321, lng: -64.757 },
#    { lat: 25.774, lng: -80.19 },
#  ];
#  // Construct the polygon.
#  const bermudaTriangle = new google.maps.Polygon({
#    paths: triangleCoords,
#    strokeColor: "#FF0000",
#    strokeOpacity: 0.8,
#    strokeWeight: 2,
#    fillColor: "#FF0000",
#    fillOpacity: 0.35,
#  });
