#! /usr/bin/env python
import gtk
from gtk import gdk
import cairo
import math

from cairogtk import CairoGTK, BaseDrawing
import eagle

class EagleDrawing(BaseDrawing):
	def __init__(self, module):
		self.module = module

	def get_size(self):
		return ((-10**6, -10**6), (10**6, 10**6))
		points = self.points()
		minx, miny = maxx, maxy = points.next()
		for x, y in points:
			minx = min(minx, x)
			miny = min(miny, y)
			maxx = max(maxx, x)
			maxy = max(maxy, y)
		return (minx, miny), (maxx, maxy)

	def draw(self, cr):
		# Draw red cross at origo
		cr.set_source_rgb(1.0, 0.0, 0.0)
		cr.set_line_width(cr.device_to_user_distance(1, 1)[0])
		cr.move_to(*cr.device_to_user_distance(0, -10))
		cr.rel_line_to(*cr.device_to_user_distance(0, 20))
		cr.move_to(*cr.device_to_user_distance(-10, 0))
		cr.rel_line_to(*cr.device_to_user_distance(20, 0))
		cr.stroke()

		self.draw_item(cr, self.module)

	def draw_item(self, cr, item):
		if isinstance(item, eagle.SymbolSection):
			self.draw_symbol(cr, item)
		elif isinstance(item, eagle.LineSection):
			self.draw_line(cr, item)
		elif isinstance(item, eagle.CircleSection):
			self.draw_circle(cr, item)
		elif isinstance(item, eagle.PinSection):
			self.draw_pin(cr, item)
		else:
			raise TypeError, 'Unknown section: ' + self.module.secname

	def draw_symbol(self, cr, sym):
		cr.set_line_cap(cairo.LINE_CAP_ROUND)
		for item in sym.subsections[0]:
			self.draw_item(cr, item)

	def draw_line(self, cr, item):
		if item.linetype == 0x00:
			cr.set_line_width(item.width_2*2)
			cr.move_to(item.x1, item.y1)
			cr.line_to(item.x2, item.y2)
			cr.stroke()
		elif item.linetype in (0x78, 0x79, 0x7a, 0x7b, 0x7c, 0x7d, 0x7e, 0x7f, 0x81):
			r = math.sqrt((item.x1-item.cx)**2 + (item.y1-item.cy)**2)
			start = math.atan2(item.y1-item.cy, item.x1-item.cx)
			end = math.atan2(item.y2-item.cy, item.x2-item.cx)
			cr.set_line_width(item.width_2*2)
			(cr.arc if item.clockwise else cr.arc_negative)(item.cx, item.cy, r, start, end)
			cr.stroke()
		#else:
		#	raise ValueError, 'Unknown line type: ' + hex(item.linetype)

	def draw_circle(self, cr, item):
		cr.set_line_width(item.width_2*2)
		cr.arc(item.x1, item.y1, item.r, 0, 2*math.pi)
		cr.stroke()

	def draw_pin(self, cr, item):
		length = 'Point Short Middle Long'.split().index(item.length)*25400
		angle = [0, 90, 180, 270].index(item.angle)
		point = [(length, 0), (0, length), (-length, 0), (0, -length)][angle]
		cr.set_line_width(6*254)
		cr.move_to(item.x, item.y)
		cr.rel_line_to(*point)
		cr.stroke()
		cr.save()
		cr.set_source_rgb(0.0, 1.0, 0.0)
		cr.arc(item.x, item.y, 10000, 0, 2*math.pi)
		cr.identity_matrix()
		cr.set_line_width(1)
		cr.stroke()
		cr.restore()

class EagleGTK(CairoGTK):
	ypol = -1

if __name__ == "__main__":
	import sys

	library, itemtype, name = sys.argv[1:4]

	with file(library) as f:
		root = eagle.read_layers(f)
		lib = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.LibrarySection)][0]
		items = lib.subsections['device symbol package'.split().index(itemtype)][0]
		item = [item for item in items.subsections[0] if item.name == name][0]

	widget = EagleGTK(EagleDrawing(item))

	window = gtk.Window()
	window.connect("delete-event", gtk.main_quit)
	widget.show()
	window.add(widget)
	window.present()
	widget._reshape()

	gtk.main()

