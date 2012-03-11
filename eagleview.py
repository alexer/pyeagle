#! /usr/bin/env python
import gtk
from gtk import gdk
import cairo
import math

from cairogtk import CairoGTK, BaseDrawing
import eagle

class EagleDrawing(BaseDrawing):
	def __init__(self, libraries, module):
		self.libraries = libraries
		self.module = module

	def get_size(self):
		return ((self.module.minx*254, self.module.miny*254), (self.module.maxx*254, self.module.maxy*254))
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

		cr.set_line_cap(cairo.LINE_CAP_ROUND)

		self.draw_item(cr, self.module)

	def draw_item(self, cr, item):
		if isinstance(item, eagle.SchemaSheetSection):
			self.draw_schema(cr, item)
		elif isinstance(item, eagle.BoardSection):
			self.draw_board(cr, item)
		elif isinstance(item, eagle.SchemaSymbolSection):
			self.draw_schemasymbol(cr, item)
		elif isinstance(item, eagle.BoardPackageSection):
			self.draw_boardpackage(cr, item)
		elif isinstance(item, eagle.SymbolSection):
			self.draw_symbol(cr, item)
		elif isinstance(item, eagle.PackageSection):
			self.draw_package(cr, item)
		elif isinstance(item, eagle.LineSection):
			self.draw_line(cr, item)
		elif isinstance(item, eagle.CircleSection):
			self.draw_circle(cr, item)
		elif isinstance(item, eagle.RectangleSection):
			self.draw_rectangle(cr, item)
		elif isinstance(item, eagle.PinSection):
			self.draw_pin(cr, item)
		elif isinstance(item, eagle.PadSection):
			self.draw_pad(cr, item)
		#else:
		#	raise TypeError, 'Unknown section: ' + item.secname

	def draw_schema(self, cr, sch):
		for item in sch.subsections[1]:
			self.draw_item(cr, item)
		cr.set_source_rgb(0.0, 0.0, 1.0)
		for bus in sch.subsections[2]:
			for path in bus.subsections[0]:
				for item in path.subsections[0]:
					self.draw_item(cr, item)
		cr.set_source_rgb(0.0, 1.0, 0.0)
		for item in sch.subsections[0]:
			self.draw_item(cr, item)
		for net in sch.subsections[3]:
			for path in net.subsections[0]:
				for item in path.subsections[0]:
					self.draw_item(cr, item)

	def draw_board(self, cr, brd):
		for item in brd.subsections[2]:
			self.draw_item(cr, item)
		for item in brd.subsections[1]:
			self.draw_item(cr, item)
		for net in brd.subsections[3]:
			for item in net.subsections[0]:
				self.draw_item(cr, item)

	def draw_symbol(self, cr, sym):
		for item in sym.subsections[0]:
			self.draw_item(cr, item)

	def draw_package(self, cr, pac):
		for item in pac.subsections[0]:
			self.draw_item(cr, item)

	def draw_schemasymbol(self, cr, item1):
		item2 = [item for item in item1.subsections[0] if isinstance(item, eagle.SchemaSymbol2Section)][0]
		cr.save()
		cr.translate(item2.x, item2.y)
		if item2.mirrored:
			cr.scale(-1, 1)
		cr.rotate(math.radians(item2.angle))
		lib = self.libraries[item1.libno-1]
		syms = lib.subsections[1][0]
		sym = syms.subsections[0][item1.symno-1]
		self.draw_symbol(cr, sym)
		cr.restore()

	def draw_boardpackage(self, cr, item):
		cr.save()
		cr.translate(item.x, item.y)
		if item.mirrored:
			cr.scale(-1, 1)
		cr.rotate(math.radians(360 * item.angle / 4096.))
		brd = self.module
		pacs = brd.subsections[0][item.libno-1]
		pac = pacs.subsections[0][item.pacno-1]
		self.draw_symbol(cr, pac)
		cr.restore()

	def draw_line(self, cr, item):
		if item.linetype == 0x00:
			cr.set_line_width(item.width_2*2)
			cr.move_to(item.x1, item.y1)
			cr.line_to(item.x2, item.y2)
			cr.stroke()
		elif item.linetype == 0x01:
			cr.save()
			cr.set_source_rgb(1.0, 1.0, 0.0)
			cr.move_to(item.x1, item.y1)
			cr.line_to(item.x2, item.y2)
			cr.identity_matrix()
			cr.set_line_width(1)
			cr.stroke()
			cr.restore()
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

	def draw_rectangle(self, cr, item):
		cr.rectangle(item.x1, item.y1, item.x2-item.x1, item.y2-item.y1)
		cr.fill()

	def draw_pin(self, cr, item):
		length = 'Point Short Middle Long'.split().index(item.length)*25400
		angle = [0, 90, 180, 270].index(item.angle)
		point = [(length, 0), (0, length), (-length, 0), (0, -length)][angle]
		cr.set_line_width(6*254)
		cr.move_to(item.x, item.y)
		cr.rel_line_to(*point)
		cr.stroke()
		if isinstance(self.module, eagle.SymbolSection):
			cr.save()
			cr.set_source_rgb(0.0, 1.0, 0.0)
			cr.arc(item.x, item.y, 10000, 0, 2*math.pi)
			cr.identity_matrix()
			cr.set_line_width(1)
			cr.stroke()
			cr.restore()

	def draw_pad(self, cr, item):
		cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
		cr.arc(item.x, item.y, item.diameter_2 or item.drill_2*1.5, 0, 2*math.pi)
		cr.arc(item.x, item.y, item.drill_2, 0, 2*math.pi)
		cr.fill()

class EagleGTK(CairoGTK):
	ypol = -1

if __name__ == "__main__":
	import sys

	library, itemtype, name = sys.argv[1:4]

	with file(library) as f:
		root = eagle.read_layers(f)
		libs = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.LibrarySection)]
		if itemtype == 'schema':
			item = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.SchemaSection)][0]
			libs = item.subsections[1]
			item = item.subsections[2][0]
		elif itemtype == 'board':
			item = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.BoardSection)][0]
		else:
			items = libs[0].subsections['device symbol package'.split().index(itemtype)][0]
			item = [item for item in items.subsections[0] if item.name == name][0]

	widget = EagleGTK(EagleDrawing(libs, item))

	window = gtk.Window()
	window.connect("delete-event", gtk.main_quit)
	widget.show()
	window.add(widget)
	window.present()
	widget._reshape()

	gtk.main()

