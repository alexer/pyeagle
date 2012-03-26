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

	def set_color_by_layer(self, cr, item, context, mirrored, **kwargs):
		layerno = item.layer if not mirrored or context == 'schema' else self.layers[item.layer].other
		try:
			color = self.colors[self.layers[layerno].color]
		except:
			color = (1, 1, 1, 0.8)
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
		context = None
		if isinstance(item, eagle.SchemaSheetSection):
			context = 'schema'
		elif isinstance(item, eagle.BoardSection):
			context = 'board'
		self.draw_item(cr, self.module, context = context, mirrored = False, spin = False, angle = 0)

	def draw_item(self, cr, item, **kwargs):
		if isinstance(item, eagle.SchemaSheetSection):
			self.draw_schema(cr, item, **kwargs)
		elif isinstance(item, eagle.BoardSection):
			self.draw_board(cr, item, **kwargs)
		elif isinstance(item, eagle.PartSection):
			self.draw_schemadevice(cr, item, **kwargs)
		elif isinstance(item, eagle.BoardPackageSection):
			self.draw_boardpackage(cr, item, **kwargs)
		elif isinstance(item, eagle.SymbolSection):
			self.draw_symbol(cr, item, **kwargs)
		elif isinstance(item, eagle.PackageSection):
			self.draw_package(cr, item, **kwargs)
		elif isinstance(item, eagle.LineSection):
			self.draw_line(cr, item, **kwargs)
		elif isinstance(item, eagle.ArcSection):
			self.draw_arc(cr, item, **kwargs)
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
			pass
			#self.draw_text(cr, item, **kwargs)
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
		for item in sch.parts:
			self.draw_item(cr, item, **kwargs)
		cr.set_source_rgb(0.0, 0.0, 1.0)
		for bus in sch.buses:
			for path in bus.paths:
				for item in path.drawables:
					self.draw_item(cr, item, **kwargs)
		cr.set_source_rgb(0.0, 1.0, 0.0)
		for item in sch.drawables:
			self.draw_item(cr, item, **kwargs)
		for net in sch.nets:
			for path in net.paths:
				for item in path.drawables:
					self.draw_item(cr, item, **kwargs)

	def draw_board(self, cr, brd, **kwargs):
		for item in brd.packages:
			self.draw_item(cr, item, **kwargs)
		for item in brd.drawables:
			self.draw_item(cr, item, **kwargs)
		for net in brd.nets:
			for item in net.drawables:
				self.draw_item(cr, item, **kwargs)

	def draw_symbol(self, cr, sym, **kwargs):
		for item in sym.drawables:
			self.draw_item(cr, item, **kwargs)

	def draw_package(self, cr, pac, **kwargs):
		for item in pac.drawables:
			self.draw_item(cr, item, **kwargs)

	def draw_schemadevice(self, cr, schdev, mirrored, angle, **kwargs):
		for schins in schdev.instances:
			if not schins.placed:
				continue
			cr.save()
			cr.translate(schins.x, schins.y)
			if schins.mirrored:
				mirrored = not mirrored
				cr.scale(-1, 1)
			a = schins.angle
			if mirrored:
				a = -a
			cr.rotate(math.radians(360 * schins.angle / 4096.))
			lib = self.libraries[schdev.libno-1]
			dev = lib.devices.devices[schdev.devno-1]
			devgat = dev.gates[schins.gateno-1]
			sym = lib.symbols.symbols[devgat.symno-1]
			self.draw_symbol(cr, sym, mirrored = mirrored, angle = angle + a, **kwargs)
			cr.restore()

	def draw_boardpackage(self, cr, item, mirrored, spin, angle, **kwargs):
		cr.save()
		cr.translate(item.x, item.y)
		if item.mirrored:
			mirrored = not mirrored
			cr.scale(-1, 1)
		if item.spin:
			spin = not spin
		a = item.angle
		if mirrored:
			a = -a
		cr.rotate(math.radians(360 * item.angle / 4096.))
		brd = self.module
		pacs = brd.definitions[item.libno-1]
		pac = pacs.packages[item.pacno-1]
		self.draw_symbol(cr, pac, mirrored = mirrored, spin = spin, angle = angle + a, **kwargs)
		cr.restore()

	def draw_text(self, cr, item, context, mirrored, spin, angle, **kwargs):
		# XXX: Eh...
		self.set_color_by_layer(cr, item, context = context, mirrored = mirrored, spin = spin, angle = angle, **kwargs)
		cr.save()
		cr.translate(item.x, item.y)
		if item.mirrored:
			mirrored = not mirrored
			cr.scale(-1, 1)
		if item.spin:
			spin = not spin
		cr.rotate(math.radians(360 * item.angle / 4096.))
		cr.set_font_size(item.size_2*2)
		fascent, fdescent, fheight, fxadvance, fyadvance = cr.font_extents()
		xbearing, ybearing, width, height, xadvance, yadvance = cr.text_extents(item.text)
		# We have inverted y coordinates relative to cairo, so we have to invert them here to get text rendered correctly
		cr.scale(1, -1)
		a = item.angle
		if mirrored:
			a = -a
		angle += a
		if mirrored:
			if context == 'schema':
				angle = 2048 + angle
				cr.scale(1, -1)
				cr.translate(0, fascent)
		angle %= 4096
		if context == 'schema':
			if (90 < 360 * angle / 4096 <= 270):
				cr.scale(-1, -1)
				cr.translate(-width, fascent)
		elif not spin:
			if not mirrored and (90 < 360 * angle / 4096 <= 270):
				cr.scale(-1, -1)
				cr.translate(-width, fascent)
			if mirrored and (90 <= 360 * angle / 4096 < 270):
				cr.scale(-1, -1)
				cr.translate(-width, fascent)
		cr.translate(-xbearing, 0)
		cr.show_text(item.text)
		cr.fill()
		cr.restore()

	def draw_polygon(self, cr, item, **kwargs):
		for subsec in item.drawables:
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

	def draw_arc(self, cr, item, **kwargs):
		cr.save()
		cr.set_line_cap(cairo.LINE_CAP_BUTT)
		self.set_color_by_layer(cr, item, **kwargs)
		r = math.sqrt((item.x1-item.cx)**2 + (item.y1-item.cy)**2)
		start = math.atan2(item.y1-item.cy, item.x1-item.cx)
		end = math.atan2(item.y2-item.cy, item.x2-item.cx)
		cr.set_line_width(item.width_2*2)
		(cr.arc if item.clockwise else cr.arc_negative)(item.cx, item.cy, r, start, end)
		cr.stroke()
		cr.restore()

	def draw_circle(self, cr, item, **kwargs):
		self.set_color_by_layer(cr, item, **kwargs)
		cr.set_line_width(item.width_2*2)
		cr.arc(item.x1, item.y1, item.r, 0, 2*math.pi)
		cr.stroke()

	def draw_rectangle(self, cr, item, **kwargs):
		cr.save()
		cr.translate((item.x1+item.x2)/2., (item.y1+item.y2)/2.)
		cr.rotate(math.radians(360 * item.angle / 4096.))
		w, h = abs(item.x2-item.x1), abs(item.y2-item.y1)
		cr.rectangle(-w/2., -h/2., w, h)
		self.fill_with_pattern_by_layer(cr, item, **kwargs)
		cr.restore()

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

	fname = sys.argv[1]
	if len(sys.argv) > 2:
		itemtype = sys.argv[2]
	elif fname.endswith('.sch'):
		itemtype = 'schema'
	elif fname.endswith('.brd'):
		itemtype = 'board'
	else:
		print 'You have to specify the type and name of the item you want to display with libraries'
		sys.exit()
	assert itemtype in 'schema board device symbol package'.split()

	if itemtype in 'device symbol package'.split():
		name = sys.argv[3]

	with file(fname) as f:
		eaglefile = eagle.EagleFile(f)
		root = eaglefile.root
		drc = None
		grid = root.grid
		libs = []
		layers = dict((layer.layer, layer) for layer in root.layers)
		if itemtype == 'schema':
			item = root.drawing.sheets[0]
			libs = root.drawing.libraries
		elif itemtype == 'board':
			item = root.drawing
			drc = [rule for rule in eaglefile.rules if isinstance(rule, eagle.DRCRules)][0]
		else:
			if itemtype == 'device':
				items = root.drawing.devices.devices
			elif itemtype == 'symbol':
				items = root.drawing.symbols.symbols
			elif itemtype == 'package':
				items = root.drawing.packages.packages
			item = [item for item in items if item.name == name][0]

	widget = EagleGTK(EagleDrawing(drc, grid, layers, libs, item))

	window = gtk.Window()
	window.connect("delete-event", gtk.main_quit)
	widget.show()
	window.add(widget)
	window.present()
	widget._reshape()

	gtk.main()

