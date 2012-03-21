#! /usr/bin/env python
import gtk
from gtk import gdk
import cairo
import math

from cairogtk import CairoGTK, BaseDrawing
import eagle

pattern_sizes = [
	(1, 1), (1, 1), (4, 4), (8, 8),
	(8, 8), (8, 8), (8, 8), (4, 4),
	(8, 8), (2, 2), (8, 4), (4, 4),
	(2, 2), (2, 2), (2, 2), (2, 2),
]

patterns = [
	[], [(0, 0)], [(x, y) for x in range(4) for y in range(2)], [(i, 7-i) for i in range(8)],
	[((i+j)%8, (2-i)%8) for i in range(8) for j in range(3)], [((i+j)%8, (5+i)%8) for i in range(8) for j in range(3)], [(i, i) for i in range(8)], [(i, j) for i in range(4) for j in range(4) if not i or not j],
	[(i, (3-i)%8) for i in range(8)] + [(i, (4+i)%8) for i in range(8)], [(0, 0), (1, 1)], [(0, 2), (4, 0)], [(0, 0), (2, 2)],
	[(1, 0)], [(0, 0)], [(0, 1)], [(1, 1)],
]

class EagleDrawing(BaseDrawing):
	colors = [tuple(int(c, 16)/255. for c in (c[0:2], c[2:4], c[4:6], 'cc')) for c in '000000 23238d 238d23 238d8d 8d2323 8d238d 8d8d23 8d8d8d 272727 0000b4 00b400 00b4b4 b40000 b400b4 b4b400 b4b4b4'.split()]
	def __init__(self, drc, grid, layers, libraries, module):
		self.drc = drc
		self.grid = grid
		self.layers = layers
		self.libraries = libraries
		self.module = module

		# DRC settings (for calculating pad/via sizes)
		if drc:
			self.min_drill = drc.min_drill
			# XXX: Top and bottom are different settings
			self.min_pad = drc.restring_mins[0]
			self.max_pad = drc.restring_maxs[0]
			self.min_via = drc.restring_mins[3]
			self.max_via = drc.restring_maxs[3]
		else:
			self.min_drill = eagle.mm2u(0.6096)
			self.min_pad = eagle.mm2u(0.254)
			self.max_pad = eagle.mm2u(0.508)
			self.min_via = eagle.mm2u(0.2032)
			self.max_via = eagle.mm2u(0.508)

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

	def set_color_by_layer(self, cr, item, mirrored, **kwargs):
		layerno = item.layer if not mirrored else self.layers[item.layer].other
		color = self.colors[self.layers[layerno].color]
		cr.set_source_rgba(*color)

	def set_pattern_by_layer(self, cr, item, mirrored, **kwargs):
		layerno = item.layer if not mirrored else self.layers[item.layer].other
		pattern = self.layers[layerno].fill
		target = cr.get_target()
		pat_surf = target.create_similar(cairo.CONTENT_COLOR_ALPHA, *pattern_sizes[pattern])
		pat_cr = cairo.Context(pat_surf)
		pat_cr.push_group()
		self.set_color_by_layer(pat_cr, item, mirrored = mirrored, **kwargs)
		for x, y in patterns[pattern]:
			pat_cr.rectangle(x, y, 1, 1)
		pat_cr.fill()
		pat = pat_cr.pop_group()
		pat.set_extend(cairo.EXTEND_REPEAT)
		cr.set_source(pat)

	def fill_with_pattern_by_layer(self, cr, item, **kwargs):
		cr.save()
		cr.identity_matrix()
		cr.set_line_width(1.5)
		self.set_color_by_layer(cr, item, **kwargs)
		cr.stroke_preserve()
		self.set_pattern_by_layer(cr, item, **kwargs)
		cr.fill()
		cr.restore()

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

		#self.draw_grid(cr, self.grid)
		self.draw_item(cr, self.module, mirrored = False)

	def draw_item(self, cr, item, **kwargs):
		if isinstance(item, eagle.SchemaSheetSection):
			self.draw_schema(cr, item, **kwargs)
		elif isinstance(item, eagle.BoardSection):
			self.draw_board(cr, item, **kwargs)
		elif isinstance(item, eagle.SchemaDeviceSection):
			self.draw_schemadevice(cr, item, **kwargs)
		elif isinstance(item, eagle.BoardPackageSection):
			self.draw_boardpackage(cr, item, **kwargs)
		elif isinstance(item, eagle.SymbolSection):
			self.draw_symbol(cr, item, **kwargs)
		elif isinstance(item, eagle.PackageSection):
			self.draw_package(cr, item, **kwargs)
		elif isinstance(item, eagle.LineSection):
			self.draw_line(cr, item, **kwargs)
		elif isinstance(item, eagle.CircleSection):
			self.draw_circle(cr, item, **kwargs)
		elif isinstance(item, eagle.RectangleSection):
			self.draw_rectangle(cr, item, **kwargs)
		elif isinstance(item, eagle.PinSection):
			self.draw_pin(cr, item, **kwargs)
		elif isinstance(item, eagle.ViaSection):
			self.draw_via(cr, item, **kwargs)
		elif isinstance(item, eagle.PadSection):
			self.draw_pad(cr, item, **kwargs)
		elif isinstance(item, eagle.SmdSection):
			self.draw_smd(cr, item, **kwargs)
		elif isinstance(item, eagle.TextBaseSection):
			pass # XXX: Todo
		elif isinstance(item, eagle.JunctionSection):
			self.draw_junction(cr, item, **kwargs)
		elif isinstance(item, eagle.PolygonSection):
			self.draw_polygon(cr, item, **kwargs)
		elif isinstance(item, (eagle.SchemaConnectionSection, eagle.BoardConnectionSection)):
			pass
		#else:
		#	raise TypeError, 'Unknown section: ' + item.secname

	def draw_grid(self, cr, grid):
		factor = [10, 10000, 254, 254000][grid.unit&0x03]*grid.size*grid.multiple
		miny, maxy = -100, 100
		minx, maxx = -100, 100
		for x in range(minx, maxx):
			cr.move_to(x*factor, miny*factor)
			cr.line_to(x*factor, maxy*factor)
		for y in range(miny, maxy):
			cr.move_to(minx*factor, y*factor)
			cr.line_to(maxx*factor, y*factor)
		cr.save()
		cr.identity_matrix()
		cr.set_line_width(0.5)
		cr.set_source_rgba(*self.colors[7])
		cr.stroke()
		cr.restore()

	def draw_schema(self, cr, sch, **kwargs):
		for item in sch.subsections[1]:
			self.draw_item(cr, item, **kwargs)
		cr.set_source_rgb(0.0, 0.0, 1.0)
		for bus in sch.subsections[2]:
			for path in bus.subsections[0]:
				for item in path.subsections[0]:
					self.draw_item(cr, item, **kwargs)
		cr.set_source_rgb(0.0, 1.0, 0.0)
		for item in sch.subsections[0]:
			self.draw_item(cr, item, **kwargs)
		for net in sch.subsections[3]:
			for path in net.subsections[0]:
				for item in path.subsections[0]:
					self.draw_item(cr, item, **kwargs)

	def draw_board(self, cr, brd, **kwargs):
		for item in brd.subsections[2]:
			self.draw_item(cr, item, **kwargs)
		for item in brd.subsections[1]:
			self.draw_item(cr, item, **kwargs)
		for net in brd.subsections[3]:
			for item in net.subsections[0]:
				self.draw_item(cr, item, **kwargs)

	def draw_symbol(self, cr, sym, **kwargs):
		for item in sym.subsections[0]:
			self.draw_item(cr, item, **kwargs)

	def draw_package(self, cr, pac, **kwargs):
		for item in pac.subsections[0]:
			self.draw_item(cr, item, **kwargs)

	def draw_schemadevice(self, cr, schdev, **kwargs):
		schsyms = [item for item in schdev.subsections[0] if isinstance(item, eagle.SchemaSymbolSection)]
		for schsym in schsyms:
			if not schsym.placed:
				continue
			cr.save()
			cr.translate(schsym.x, schsym.y)
			if schsym.mirrored:
				cr.scale(-1, 1)
			cr.rotate(math.radians(360 * schsym.angle / 4096.))
			lib = self.libraries[schdev.libno-1]
			devs = lib.subsections[0][0]
			syms = lib.subsections[1][0]
			dev = devs.subsections[0][schdev.devno-1]
			devsym = dev.subsections[1][schsym.symno-1]
			sym = syms.subsections[0][devsym.symno-1]
			self.draw_symbol(cr, sym, **kwargs)
			cr.restore()

	def draw_boardpackage(self, cr, item, mirrored, **kwargs):
		cr.save()
		cr.translate(item.x, item.y)
		if item.mirrored:
			mirrored = not mirrored
			cr.scale(-1, 1)
		cr.rotate(math.radians(360 * item.angle / 4096.))
		brd = self.module
		pacs = brd.subsections[0][item.libno-1]
		pac = pacs.subsections[0][item.pacno-1]
		self.draw_symbol(cr, pac, mirrored = mirrored, **kwargs)
		cr.restore()

	def draw_polygon(self, cr, item, **kwargs):
		for subsec in item.subsections[0]:
			self.draw_item(cr, subsec, **kwargs)

	def draw_line(self, cr, item, **kwargs):
		self.set_color_by_layer(cr, item, **kwargs)
		if item.linetype in (0x00, 0x01):
			cr.save()
			cr.move_to(item.x1, item.y1)
			cr.line_to(item.x2, item.y2)
			if item.linetype == 0x00 and item.width_2:
				cr.set_line_width(item.width_2*2)
			else:
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

	def draw_circle(self, cr, item, **kwargs):
		self.set_color_by_layer(cr, item, **kwargs)
		cr.set_line_width(item.width_2*2)
		cr.arc(item.x1, item.y1, item.r, 0, 2*math.pi)
		cr.stroke()

	def draw_rectangle(self, cr, item, **kwargs):
		cr.rectangle(item.x1, item.y1, item.x2-item.x1, item.y2-item.y1)
		self.fill_with_pattern_by_layer(cr, item, **kwargs)

	def draw_junction(self, cr, item, **kwargs):
		cr.set_source_rgba(*self.colors[2])
		cr.arc(item.x, item.y, eagle.in2u(0.02), 0, 2*math.pi)
		cr.fill()

	def draw_pin(self, cr, item, **kwargs):
		length = item.length*25400
		angle = item.angle / 1024
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

	def draw_via(self, cr, item, **kwargs):
		cr.save()
		cr.translate(item.x, item.y)
		cr.set_source_rgba(*self.colors[2])
		cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
		diameter_2 = item.diameter_2 or item.drill_2 + max(item.drill_2*2*0.25, self.min_via)
		if item.shape == 0:
			cr.rectangle(-diameter_2, -diameter_2, diameter_2*2, diameter_2*2)
		elif item.shape == 1:
			cr.arc(0, 0, diameter_2, 0, 2*math.pi)
		elif item.shape == 2:
			a_2 = (math.sqrt(2)-1)*diameter_2
			cr.move_to(-diameter_2, a_2)
			cr.line_to(-a_2, diameter_2)
			cr.line_to(a_2, diameter_2)
			cr.line_to(diameter_2, a_2)
			cr.line_to(diameter_2, -a_2)
			cr.line_to(a_2, -diameter_2)
			cr.line_to(-a_2, -diameter_2)
			cr.line_to(-diameter_2, -a_2)
			cr.line_to(-diameter_2, a_2)
		cr.arc(0, 0, item.drill_2, 0, 2*math.pi)
		cr.fill()
		cr.restore()

	def draw_pad(self, cr, item, **kwargs):
		cr.save()
		cr.translate(item.x, item.y)
		cr.rotate(math.radians(360 * item.angle / 4096.))
		cr.set_source_rgba(*self.colors[2])
		cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
		diameter_2 = item.diameter_2 or item.drill_2 + max(item.drill_2*2*0.25, self.min_pad)
		if item.shape == 0:
			cr.rectangle(-diameter_2, -diameter_2, diameter_2*2, diameter_2*2)
		elif item.shape == 1:
			cr.arc(0, 0, diameter_2, 0, 2*math.pi)
		elif item.shape == 2:
			a_2 = (math.sqrt(2)-1)*diameter_2
			cr.move_to(-diameter_2, a_2)
			cr.line_to(-a_2, diameter_2)
			cr.line_to(a_2, diameter_2)
			cr.line_to(diameter_2, a_2)
			cr.line_to(diameter_2, -a_2)
			cr.line_to(a_2, -diameter_2)
			cr.line_to(-a_2, -diameter_2)
			cr.line_to(-diameter_2, -a_2)
			cr.line_to(-diameter_2, a_2)
		elif item.shape == 3:
			cr.move_to(-diameter_2, diameter_2)
			cr.line_to(diameter_2, diameter_2)
			cr.arc_negative(diameter_2, 0, diameter_2, math.pi/2, 3*math.pi/2)
			cr.line_to(-diameter_2, -diameter_2)
			cr.arc_negative(-diameter_2, 0, diameter_2, 3*math.pi/2, math.pi/2)
		elif item.shape == 4:
			cr.move_to(0, diameter_2)
			cr.line_to(diameter_2*2, diameter_2)
			cr.arc_negative(diameter_2*2, 0, diameter_2, math.pi/2, 3*math.pi/2)
			cr.line_to(0, -diameter_2)
			cr.arc_negative(0, 0, diameter_2, 3*math.pi/2, math.pi/2)
		cr.arc(0, 0, item.drill_2, 0, 2*math.pi)
		cr.fill()
		cr.restore()

	def draw_smd(self, cr, item, **kwargs):
		cr.save()
		cr.translate(item.x, item.y)
		cr.rotate(math.radians(360 * item.angle / 4096.))
		cr.rectangle(-item.width_2, -item.height_2, item.width_2*2, item.height_2*2)
		self.fill_with_pattern_by_layer(cr, item, **kwargs)
		cr.restore()

class EagleGTK(CairoGTK):
	ypol = -1

if __name__ == "__main__":
	import sys

	library, itemtype, name = sys.argv[1:4]

	with file(library) as f:
		eaglefile = eagle.EagleFile(f)
		root = eaglefile.root
		drc = None
		grid = [subsec for subsec in root.subsections[0] if isinstance(subsec, eagle.GridSection)][0]
		layers = dict((subsec.layer, subsec) for subsec in root.subsections[0] if isinstance(subsec, eagle.LayerSection))
		libs = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.LibrarySection)]
		if itemtype == 'schema':
			item = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.SchemaSection)][0]
			libs = item.subsections[1]
			item = item.subsections[2][0]
		elif itemtype == 'board':
			drc = [rule for rule in eaglefile.rules if isinstance(rule, eagle.DRCRules)][0]
			item = [subsec for subsec in root.subsections[1] if isinstance(subsec, eagle.BoardSection)][0]
		else:
			items = libs[0].subsections['device symbol package'.split().index(itemtype)][0]
			item = [item for item in items.subsections[0] if item.name == name][0]

	widget = EagleGTK(EagleDrawing(drc, grid, layers, libs, item))

	window = gtk.Window()
	window.connect("delete-event", gtk.main_quit)
	widget.show()
	window.add(widget)
	window.present()
	widget._reshape()

	gtk.main()

