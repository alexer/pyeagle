import sys
import struct

def dump_hex(data):
	print ' '.join('%02x' % (ord(byte),) for byte in data)

def dump_hex_ascii(data):
	print ' '.join('%02x' % (ord(byte),) for byte in data), ''.join((byte if 32 <= ord(byte) < 127 else '.') for byte in data)

def dump_dec_hex_ascii(data):
		print ' '.join('%03d' % (ord(byte),) for byte in data)
		print ' '.join(' %02x' % (ord(byte),) for byte in data)
		print ' '.join(' %s ' % (byte if 32 <= ord(byte) <= 127 else '.',) for byte in data)
		print

pth_pad_flags = [
	(0x01, None, 'stop'),
	(0x04, None, 'thermals'),
	(0x08, 'first', None),
]

smd_pad_flags = [
	(0x01, None, 'stop'),
	(0x02, None, 'cream'),
	(0x04, None, 'thermals'),
]

def get_flags(value, flagdata):
	result = []
	for mask, true, false in flagdata:
		if value & mask == mask:
			value &= ~mask
			name = true
		else:
			name = false
		if name is not None:
			result.append(name)
	return result

# Values are in tenths of a micrometre
u2mm = lambda val: val/10/1000
u2in = lambda val: val/2.54/100/1000

class Section:
	sectype = None
	secname = None
	def __init__(self, parent, data):
		self.parent = parent
		self.data = data
		# Default is unknown, but self.unknown lists known unknowns
		self.unknown = [0x00] * 24
		self.known = [0x00] * 24
		self.zero = [0x00] * 24
		self.subsec_counts = []
		self._get_uint8(0)
		self._get_unknown(1, 1)
		self.parse()

	def _get_color(self, known, zero = 0, unknown = 0):
		assert known & zero == 0x00, "Bit can't be known and zero at the same time! (known = %s, zero = %s, known & zero = %s)" % (hex(known), hex(zero), hex(known & zero))
		assert known & unknown == 0x00, "Bit can't be known and unknown at the same time! (known = %s, unknown = %s, known & unknown = %s)" % (hex(known), hex(unknown), hex(known & unknown))
		assert unknown & zero == 0x00, "Bit can't be unknown and zero at the same time! (unknown = %s, zero = %s, unknown & zero = %s)" % (hex(unknown), hex(zero), hex(unknown & zero))
		if unknown == 0xff:
			color = '1;31' # unknown, red
		elif known == 0xff:
			color = '1;32' # known, green
		elif zero == 0xff:
			color = '1;34' # zero, blue
		elif known and unknown and not zero:
			color = '1;33' # known/unknown, yellow
		elif unknown and zero and not known:
			color = '1;35' # unknown/zero, purple
		elif known and zero and not unknown:
			color = '1;36' # known/zero, cyan
		elif known and unknown and zero:
			color = '1;37' # known/unknown/zero, white
		else:
			color = '30'
		if known | unknown | zero != 0xff:
			# Unknown unknown, red background, but not red on red
			if color == '1;31':
				color = '30;41'
			else:
				color += ';41'
		return color

	def hexdump(self):
		colorhex = ' '.join('\x1b[%sm%02x\x1b[m' % (self._get_color(known, zero, unknown), ord(byte)) for byte, known, zero, unknown in zip(self.data, self.known, self.zero, self.unknown))
		colorascii = ''.join('\x1b[%sm%s\x1b[m' % (self._get_color(known, zero, unknown), byte if 32 <= ord(byte) < 127 else '.') for byte, known, zero, unknown in zip(self.data, self.known, self.zero, self.unknown))
		print colorhex, colorascii

	def _get_bytes(self, pos, size):
		self.known[pos:pos+size] = [0xff] * size
		return self.data[pos:pos+size]

	def _get_unknown(self, pos, size):
		self.unknown[pos:pos+size] = [0xff] * size

	def _get_unknown_mask(self, pos, mask):
		self.unknown[pos] |= mask

	def _get_zero(self, pos, size):
		self.zero[pos:pos+size] = [0xff] * size
		assert self.data[pos:pos+size] == '\x00' * size, 'Unknown data in ' + self.secname + ': ' + repr(self.data[pos:pos+size])

	def _get_zero_mask(self, pos, mask):
		self.zero[pos] |= mask
		assert ord(self.data[pos]) & mask == 0x00, 'Unknown bits in ' + self.secname + ': ' + hex(ord(self.data[pos]) & mask)

	def _get_uint32(self, pos): return struct.unpack('<I', self._get_bytes(pos, 4))[0]
	def _get_uint24(self, pos): return struct.unpack('<I', self._get_bytes(pos, 3) + '\x00')[0]
	def _get_uint16(self, pos): return struct.unpack('<H', self._get_bytes(pos, 2))[0]
	def _get_uint8(self, pos):  return struct.unpack('<B', self._get_bytes(pos, 1))[0]

	def _get_int32(self, pos): return struct.unpack('<i', self._get_bytes(pos, 4))[0]
	def _get_int16(self, pos): return struct.unpack('<h', self._get_bytes(pos, 2))[0]

	def _get_double(self, pos): return struct.unpack('<d', self._get_bytes(pos, 8))[0]

	def _get_uint8_mask(self, pos, mask):
		self.known[pos] |= mask
		return ord(self.data[pos]) & mask

	def _get_name(self, pos, size): return get_name(self._get_bytes(pos, size))

class UnknownSection(Section):
	secname = '???'
	def parse(self):
		self._get_unknown(2, 22)

	def __str__(self):
		return self.secname

class TextBaseSection(Section):
	def parse(self):
		# XXX: Clean these up
		self.font = self._get_uint8(2)
		self.layer = self._get_uint8(3)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.size_2 = self._get_uint16(12)
		self.ratio = (self._get_uint16(14) >> 2) & 0x1f
		self.angle = self._get_uint16(16)
		text = self._get_name(18, 6)
		if self.sectype == 0x31:
			self.text = text
		elif self.sectype == 0x41:
			self.name = text
		else:
			assert self.data[18:24] == '\x00'*6

	def __str__(self):
		font = 'vector proportional fixed'.split()[self.font]
		# angle & 0x4000 => spin, no idea what that does though..
		if self.sectype == 0x31:
			angle = 360 * (self.angle & 0xfff) / 4096.
		else:
			angle = [0, 90, 180, 270][(self.angle & 0x0c00) >> 10]
		if self.sectype == 0x31:
			extra = ', text ' + self.text
		elif self.sectype == 0x41:
			extra = ', name ' + self.name
		else:
			extra = ''
		return '%s: at (%f", %f") size %f", angle %s, layer %d, ratio %d%%, font %s%s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.size_2*2), angle, self.layer, self.ratio, font, extra)

class StartSection(Section):
	sectype = 0x10
	secname = 'Start'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.numsecs = self._get_uint32(4)
		self._get_unknown(8, 4)
		self._get_zero(12, 1)
		self._get_unknown(13, 1)
		self._get_unknown(14, 10)
		# XXX: hack
		self.subsec_counts = [self.subsecs, self.numsecs - self.subsecs - 1]

	def __str__(self):
		return '%s: subsecs %d, numsecs %d' % (self.secname, self.subsecs, self.numsecs)

class Unknown11Section(UnknownSection):
	sectype = 0x11

grid_units2 = 'mic mm mil in'.split()
grid_units4 = [save if save == disp else '%s as %s' % (save, disp) for disp in grid_units2 for save in grid_units2]
class GridSection(Section):
	sectype = 0x12
	secname = 'Grid'
	def parse(self):
		self.display = self._get_uint8_mask(2, 0x1)
		self.style = 'lines dots'.split()[self._get_uint8_mask(2, 0x2) >> 1]
		self._get_zero_mask(2, 0xfc)
		# 4 bits of unit
		# higher 2 bits tell which unit is used for display
		# lower 2 bits tell which unit is used for saving
		self.unit = grid_units4[self._get_uint8_mask(3, 0x0f)]
		self.altunit = grid_units4[self._get_uint8_mask(3, 0xf0) >> 4]
		self.multiple = self._get_uint24(4)
		self._get_zero(7, 1)
		self.size = self._get_double(8)
		self.altsize = self._get_double(16)

	def __str__(self):
		return '%s: display %s, style %s, size %s%s, multiple %d, alt %s%s' % (self.secname, self.display, self.style, self.size, self.unit, self.multiple, self.altsize, self.altunit)

class LayerSection(Section):
	sectype = 0x13
	secname = 'Layer'
	def parse(self):
		self.flags = self._get_uint8_mask(2, 0x1e)
		self._get_zero_mask(2, 0xe0)
		self._get_unknown_mask(2, 0x01)
		self.layer = self._get_uint8(3)
		self.other = self._get_uint8(4)
		self.fill = self._get_uint8(5)
		self.color = self._get_uint8(6)
		self._get_unknown(7, 1)
		self._get_zero(8, 7)
		self.name = self._get_name(15, 9)
		self.side = 'bottom' if self.flags & 0x10 else 'top'
		assert self.flags & 0x0c in (0x00, 0x0c), 'I thought visibility always set two bits?'
		self.visible = self.flags & 0x0c == 0x0c # whether objects on this layer are currently shown
		self.available = self.flags & 0x02 == 0x02 # not available => not visible in layer display dialog at all
		# The ulp "visible" flag is basically "visible and not hidden", or "flags & 0x0e == 0x0e"
		self.ulpvisible = self.visible and self.available

	def __str__(self):
		return '%s %s: layer %d, other %d, side %s, visible %d, fill %d, color %d' % (self.secname, self.name, self.layer, self.other, self.side, self.ulpvisible, self.fill, self.color)

class SchemaSection(Section):
	sectype = 0x14
	secname = 'Schema'
	def parse(self):
		self._get_unknown(2, 1)
		self._get_zero(3, 1)
		self.libsubsecs = self._get_uint32(4)
		self.shtsubsecs = self._get_uint32(8)
		self.atrsubsecs = self._get_uint32(12)
		self._get_zero(16, 3)
		self.xref_format = self._get_name(19, 5)
		self.subsec_counts = [self.atrsubsecs, self.libsubsecs, self.shtsubsecs]

	def __str__(self):
		return '%s: xref format %s, attrsubsecs %d, libsubsecs %d, sheetsubsecs %d' % (self.secname, self.xref_format, self.atrsubsecs, self.libsubsecs, self.shtsubsecs)

class LibrarySection(Section):
	sectype = 0x15
	secname = 'Library'
	def parse(self):
		self._get_zero(2, 2)
		self.devsubsecs = self._get_uint32(4)
		self.symsubsecs = self._get_uint32(8)
		self.pacsubsecs = self._get_uint32(12)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.devsubsecs, self.symsubsecs, self.pacsubsecs]

	def __str__(self):
		return '%s %s: devsubsecs %d, symsubsecs %d, pacsubsecs %d' % (self.secname, self.name, self.devsubsecs, self.symsubsecs, self.pacsubsecs)

class DevicesSection(Section):
	sectype = 0x17
	secname = 'Devices'
	def parse(self):
		self._get_zero(2, 2)
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint32(8)
		self._get_zero(12, 4)
		self.libname = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, subsecs %d, children %d' % (self.secname, self.libname, self.subsecs, self.children)

class SymbolsSection(Section):
	sectype = 0x18
	secname = 'Symbols'
	def parse(self):
		self._get_zero(2, 2)
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint32(8)
		self._get_zero(12, 4)
		self.libname = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, subsecs %d, children %d' % (self.secname, self.libname, self.subsecs, self.children)

class PackagesSection(Section):
	sectype = 0x19
	secname = 'Packages'
	def parse(self):
		self._get_zero(2, 2)
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint16(8)
		self.libname = self._get_name(16, 8)
		self.desc = self._get_name(10, 6)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, desc %s, subsecs %d, children %d' % (self.secname, self.libname, self.desc, self.subsecs, self.children)

class SchemaSheetSection(Section):
	sectype = 0x1a
	secname = 'Schema/sheet'
	def parse(self):
		self.drawsubsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self.symsubsecs = self._get_uint32(12)
		self.bussubsecs = self._get_uint32(16)
		self.netsubsecs = self._get_uint32(20)
		self.subsec_counts = [self.drawsubsecs, self.symsubsecs, self.bussubsecs, self.netsubsecs]

	def __str__(self):
		return '%s: limits (%dmil, %dmil), (%dmil, %dmil), drawsubsecs %d, symsubsecs %d, bussubsecs %d, netsubsecs %d' % (self.secname, self.minx, self.miny, self.maxx, self.maxy, self.drawsubsecs, self.symsubsecs, self.bussubsecs, self.netsubsecs)

class BoardSection(Section):
	sectype = 0x1b
	secname = 'Board'
	def parse(self):
		self.drawsubsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self.defsubsecs = self._get_uint32(12)
		self.pacsubsecs = self._get_uint32(16)
		self.netsubsecs = self._get_uint32(20)
		self.subsec_counts = [self.defsubsecs, self.drawsubsecs, self.pacsubsecs, self.netsubsecs]

	def __str__(self):
		return '%s: limits (%dmil, %dmil), (%dmil, %dmil), defsubsecs %d, drawsubsecs %d, pacsubsecs %d, netsubsecs %d' % (self.secname, self.minx, self.miny, self.maxx, self.maxy, self.defsubsecs, self.drawsubsecs, self.pacsubsecs, self.netsubsecs)

class BoardNetSection(Section):
	sectype = 0x1c
	secname = 'Board/net'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self._get_unknown(4, 8) # limits?
		self._get_zero(12, 4)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %d' % (self.secname, self.name, self.subsecs)

class SymbolSection(Section):
	sectype = 0x1d
	secname = 'Symbol'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self._get_zero(12, 4)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: limits (%dmil, %dmil), (%dmil, %dmil), subsecs %d' % (self.secname, self.name, self.minx, self.miny, self.maxx, self.maxy, self.subsecs)

class PackageSection(Section):
	sectype = 0x1e
	secname = 'Package'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self._get_zero(12, 1)
		self.name = self._get_name(18, 6)
		self.desc = self._get_name(13, 5)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: limits (%dmil, %dmil), (%dmil, %dmil), desc %s, subsecs %d' % (self.secname, self.name, self.minx, self.miny, self.maxx, self.maxy, self.desc, self.subsecs)

class SchemaNetSection(Section):
	sectype = 0x1f
	secname = 'Schema/net'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self._get_unknown(4, 8) # limits?
		self._get_zero(12, 4)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %s' % (self.secname, self.name, self.subsecs)

class PathSection(Section):
	sectype = 0x20
	secname = 'Path'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self._get_unknown(4, 8) # limits?
		self._get_zero(12, 12)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: subsecs %d' % (self.secname, self.subsecs)

class PolygonSection(Section):
	sectype = 0x21
	secname = 'Polygon'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self._get_unknown(4, 8) # limits?
		self.width_2 = self._get_uint16(12)
		self.spacing_2 = self._get_uint16(14)
		self._get_unknown(16, 2)
		self.layer = self._get_uint8(18)
		self.pour = 'hatch' if self._get_uint8_mask(19, 0x01) else 'solid'
		self._get_unknown_mask(19, 0xfe)
		self._get_zero(20, 4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: width %f", spacing %f", pour %s, layer %d, subsecs %d' % (self.secname, u2in(self.width_2*2), u2in(self.spacing_2*2), self.pour, self.layer, self.subsecs)

class LineSection(Section):
	sectype = 0x22
	secname = 'Line'
	def parse(self):
		self._get_unknown(2, 1)
		self.layer = self._get_uint8(3)
		self.width_2 = self._get_uint16(20)
		self.linetype = self._get_uint8(23)

		assert self.linetype in (0x00, 0x01, 0x81, 0x7e, 0x7f, 0x7b, 0x79, 0x78, 0x7a, 0x7d, 0x7c, 0x77), 'Unknown line type: ' + hex(self.linetype)

		if self.linetype != 0x01:
			self.stflags = self._get_uint8_mask(22, 0x33)
			self._get_zero_mask(22, 0xcc)

			# Cap style and positive curve are present on bare lines too, that's probably a bug
			self.clockwise = bool(self.stflags & 0x20)
			self.style = {0x00: 'continuous', 0x01: 'longdash', 0x02: 'shortdash', 0x03: 'dashdot'}[self.stflags & 0x03]
			self.cap = {0x00: 'round', 0x10: 'flat'}[self.stflags & 0x10]
		else:
			self._get_zero(22, 1)

		if self.linetype == 0x81:
			# 4 4-byte fields each contain 3 bytes of x1, y1, x2, y2 respectively.
			# The 4th bytes of these fields combine to a 4-byte field whichs contains 3 bytes of c,
			# which is the x or y coordinate of the arc center point, depending on the slope of the line.
			# The 4th byte of c contains flags which tell which of the fields are negative (two's complement)
			self._get_bytes(4, 15)

			# Extend 3-byte coordinate fields to 4 bytes, taking the negative-flags into account
			negflags = self._get_uint8_mask(19, 0x1f)
			self._get_zero_mask(19, 0xe0)
			ext = ['\xff' if negflags & (1 << i) else '\x00' for i in range(5)]
			xydata = self.data[7:16:4] + ext[0] + self.data[4:7] + ext[1] + self.data[8:11] + ext[2] + self.data[12:15] + ext[3] + self.data[16:19] + ext[4]
			c, x1, y1, x2, y2 = struct.unpack('<iiiii', xydata)

			self.x1 = x1
			self.y1 = y1
			self.x2 = x2
			self.y2 = y2

			x3, y3 = (x1+x2)/2., (y1+y2)/2.
			if abs(x2-x1) < abs(y2-y1):
				self.cx = cx = c
				self.cy = (x3-cx)*(x2-x1)/float(y2-y1)+y3
				xst, yst = '', '?'
			else:
				self.cy = cy = c
				self.cx = (y3-cy)*(y2-y1)/float(x2-x1)+x3
				xst, yst = '?', ''
		else:
			self.x1 = self._get_int32(4)
			self.y1 = self._get_int32(8)
			self.x2 = self._get_int32(12)
			self.y2 = self._get_int32(16)

			if self.linetype == 0x78:
				self.cx = min(self.x1, self.x2)
				self.cy = min(self.y1, self.y2)
			elif self.linetype == 0x79:
				self.cx = max(self.x1, self.x2)
				self.cy = min(self.y1, self.y2)
			elif self.linetype == 0x7a:
				self.cx = max(self.x1, self.x2)
				self.cy = max(self.y1, self.y2)
			elif self.linetype == 0x7b:
				self.cx = min(self.x1, self.x2)
				self.cy = max(self.y1, self.y2)
			elif self.linetype in (0x7c, 0x7d, 0x7e, 0x7f):
				self.cx = (self.x1 + self.x2) / 2.
				self.cy = (self.y1 + self.y2) / 2.

	def __str__(self):
		coords = 'from (%f", %f") to (%f", %f")' % (u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2))
		if self.linetype == 0x00:
			return 'Line: %s, width %f", layer %d, style %s' % (coords, u2in(self.width_2*2), self.layer, self.style)
		elif self.linetype == 0x01:
			return 'Airwire: %s, width %f", layer %d' % (coords, u2in(self.width_2*2), self.layer)
		elif self.linetype == 0x77:
			return '??Line??: %s, width %f", layer %d, style %s' % (coords, u2in(self.width_2*2), self.layer, self.style)
		else:
			center = 'center at (%f", %f")' % (u2in(self.cx), u2in(self.cy))
			arctype = {0x78: '90 downleft', 0x79: '90 downright', 0x7a: '90 upright', 0x7b: '90 upleft', 0x7c: '180 left', 0x7d: '180 right', 0x7e: '180 down', 0x7f: '180 up', 0x81: ''}[self.linetype]
			arctype = (' ' if arctype else '') + arctype
			return 'Arc%s: %s, %s, width %f", layer %d, style %s, cap %s' % (arctype, coords, center, u2in(self.width_2*2), self.layer, self.style, self.cap)

class CircleSection(Section):
	sectype = 0x25
	secname = 'Circle'
	def parse(self):
		self._get_unknown(2, 1)
		self.layer = self._get_uint8(3)
		self.x1 = self._get_int32(4)
		self.y1 = self._get_int32(8)
		self.r = self._get_int32(12)
		self._get_unknown(16, 4) # Almost always the same as bytes 12-15
		self.width_2 = self._get_uint32(20)
		#assert r == _get_int32(16) # Almost always the same...

	def __str__(self):
		return '%s: at (%f", %f"), radius %f", width %f", layer %d' % (self.secname, u2in(self.x1), u2in(self.y1), u2in(self.r), u2in(self.width_2*2), self.layer)

class RectangleSection(Section):
	sectype = 0x26
	secname = 'Rectangle'
	def parse(self):
		self._get_unknown(2, 1)
		self.layer = self._get_uint8(3)
		self.x1 = self._get_int32(4)
		self.y1 = self._get_int32(8)
		self.x2 = self._get_int32(12)
		self.y2 = self._get_int32(16)
		self.angle = self._get_uint16(20)
		self._get_zero(22, 2)

	def __str__(self):
		return '%s: from (%f", %f") to (%f", %f"), angle %f, layer %d' % (self.secname, u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), 360 * self.angle / 4096., self.layer)

class JunctionSection(Section):
	sectype = 0x27
	secname = 'Junction'
	def parse(self):
		self._get_zero(2, 1)
		self._get_unknown(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self._get_unknown(12, 2)
		self._get_zero(14, 10)

	def __str__(self):
		return '%s: at (%f", %f")' % (self.secname, u2in(self.x), u2in(self.y))

class HoleSection(Section):
	sectype = 0x28
	secname = 'Hole'
	def parse(self):
		self._get_zero(2, 2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.width_2 = self._get_uint32(12)
		self._get_zero(16, 2) # Unknown?
		self._get_zero(18, 6)

	def __str__(self):
		return '%s: at (%f", %f") drill %f"' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.width_2*2))

class PadSection(Section):
	sectype = 0x2a
	secname = 'Pad'
	def parse(self):
		self._get_unknown(2, 1)
		self._get_zero(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.drill_2 = self._get_uint16(12)
		self.diameter_2 = self._get_uint16(14)
		self.angle = self._get_uint16(16)
		self.flags = self._get_uint8(18)
		self.name = self._get_name(19, 5)

	def __str__(self):
		return '%s: at (%f", %f"), diameter %f", drill %f", angle %f, flags: %s, name %s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.diameter_2*2), u2in(self.drill_2*2), 360 * self.angle / 4096., ', '.join(get_flags(self.flags, pth_pad_flags)), self.name)

class SmdSection(Section):
	sectype = 0x2b
	secname = 'SMD pad'
	def parse(self):
		self.roundness = self._get_uint8(2)
		self.layer = self._get_uint8(3)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.width_2 = self._get_uint16(12)
		self.height_2 = self._get_uint16(14)
		self.angle = self._get_uint16(16)
		self.flags = self._get_uint8(18)
		self.name = self._get_name(19, 5)

	def __str__(self):
		return '%s: at (%f", %f"), size %f" x %f", angle %f, layer %d, roundness %d%%, flags: %s, name %s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.width_2*2), u2in(self.height_2*2), 360 * self.angle / 4096., self.layer, self.roundness, ', '.join(get_flags(self.flags, smd_pad_flags)), self.name)

class PinSection(Section):
	sectype = 0x2c
	secname = 'Pin'
	def parse(self):
		self.flags1 = self._get_uint8_mask(2, 0xc3)
		self._get_zero_mask(2, 0x3c)
		self._get_zero(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.flags2 = self._get_uint8(12)
		self.swaplevel = self._get_uint8(13)
		self.name = self._get_name(14, 10)

		self.function = 'None Dot Clk DotClk'.split()[self.flags1 & 0x03]
		self.visible = 'Off Pad Pin Both'.split()[(self.flags1 & 0xc0) >> 6]
		self.direction = 'Nc In Out I/O OC Pwr Pas Hiz Sup'.split()[self.flags2 & 0x0f]
		self.length = 'Point Short Middle Long'.split()[(self.flags2 & 0x30) >> 4]
		self.angle = [0, 90, 180, 270][(self.flags2 & 0xc0) >> 6]

	def __str__(self):
		return '%s: at (%f", %f"), name %s, angle %s, direction %s, swaplevel %s, length %s, function %s, visible %s' % (self.secname, u2in(self.x), u2in(self.y), self.name, self.angle, self.direction, self.swaplevel, self.length, self.function, self.visible)

class DeviceSymbolSection(Section):
	sectype = 0x2d
	secname = 'Device/symbol'
	def parse(self):
		self._get_zero(2, 2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self._get_unknown(12, 2)
		self.symno = self._get_uint16(14)
		self.name = self._get_name(16, 8)

	def __str__(self):
		return '%s %d: at (%f", %f"), name %s' % (self.secname, self.symno, u2in(self.x), u2in(self.y), self.name)

class BoardPackageSection(Section):
	sectype = 0x2e
	secname = 'Board/package'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.libno = self._get_uint16(12)
		self.pacno = self._get_uint16(14)
		self.angle = self._get_uint16(16)
		self.mirrored = bool(self.angle & 0x1000)
		self.angle &= 0x0fff
		self._get_zero(18, 2)
		self._get_unknown(20, 4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d@%d: at (%f", %f"), angle %f, mirror %d, subsecs %d' % (self.secname, self.pacno, self.libno, u2in(self.x), u2in(self.y), 360 * self.angle / 4096., self.mirrored, self.subsecs)

class BoardPackage2Section(Section):
	sectype = 0x2f
	secname = 'Board/package'
	def parse(self):
		self.value = self._get_name(10, 14)
		self.name = self._get_name(2, 8)

	def __str__(self):
		return '%s: name %s, value %s' % (self.secname, self.name, self.value)

class SchemaSymbol2Section(Section):
	sectype = 0x30
	secname = 'Schema/symbol'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self._get_unknown(12, 3)
		self._get_zero(15, 2)
		self.angle = [0, 90, 180, 270][self._get_uint8_mask(17, 0x0c) >> 2]
		self.mirrored = bool(self._get_uint8_mask(17, 0x10))
		self._get_zero_mask(17, 0xe3)
		self.smashed = self._get_uint8_mask(18, 0x01) == 0x01
		self._get_zero_mask(18, 0xfe)
		self._get_zero(19, 1)
		self._get_unknown(20, 4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: at (%f", %f"), angle %d, mirror %d, smashed %d' % (self.secname, u2in(self.x), u2in(self.y), self.angle, self.mirrored, self.smashed)

class TextSection(TextBaseSection):
	sectype = 0x31
	secname = 'Text'

class NetBusLabelSection(TextBaseSection):
	sectype = 0x33
	secname = 'Net/bus label'

class SmashedNameSection(TextBaseSection):
	sectype = 0x34
	secname = 'Smashed name'

class SmashedValueSection(TextBaseSection):
	sectype = 0x35
	secname = 'Smashed value'

class DevicePackageSection(Section):
	sectype = 0x36
	secname = 'Device/package'
	def parse(self):
		self._get_unknown(2, 1)
		self._get_zero(3, 1)
		self.pacno = self._get_uint16(4)
		self.variant = self._get_name(19, 5)
		self.table = self._get_name(6, 13)

	def __str__(self):
		return '%s %d: variant %s, table %s' % (self.secname, self.pacno, self.variant, self.table)

class DeviceSection(Section):
	sectype = 0x37
	secname = 'Device'
	def parse(self):
		self.symsubsecs = self._get_uint16(2)
		self.pacsubsecs = self._get_uint16(4)
		self._get_unknown(6, 1)
		self.con_byte = self._get_uint8_mask(7, 0x80) >> 7
		self.pin_bits = self._get_uint8_mask(7, 0x0f)
		self._get_zero_mask(7, 0x70)
		self.name = self._get_name(18, 6)
		self.desc = self._get_name(13, 5)
		self.prefix = self._get_name(8, 5)
		self.subsec_counts = [self.symsubsecs, self.pacsubsecs]

	def __str__(self):
		return '%s %s: prefix %s, desc %s, con_byte %d, pin_bits %d, symsubsecs %d, pacsubsecs %d' % (self.secname, self.name, self.prefix, self.desc, self.con_byte, self.pin_bits, self.symsubsecs, self.pacsubsecs)

class SchemaSymbolSection(Section):
	sectype = 0x38
	secname = 'Schema/symbol'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.libno = self._get_uint16(4)
		self.symno = self._get_uint16(6)
		self._get_unknown(8, 2)
		self._get_zero(10, 1)
		self.value = self._get_name(16, 8)
		self.name = self._get_name(11, 5)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d@%d, name %s, value %s, subsecs %d' % (self.secname, self.symno, self.libno, self.name, self.value, self.subsecs)

class SchemaBusSection(Section):
	sectype = 0x3a
	secname = 'Schema/bus'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.name = self._get_name(4, 20)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %d' % (self.secname, self.name, self.subsecs)

class DeviceConnectionsSection(Section):
	sectype = 0x3c
	secname = 'Device/connections'
	def parse(self):
		fmt = '<' + ('22B' if self.parent.con_byte else '11H')
		slots = struct.unpack(fmt, self._get_bytes(2, 22))
		# connections[padno] = (symno, pinno)
		self.connections = [(slot >> self.parent.pin_bits, slot & ((1 << self.parent.pin_bits) - 1)) for slot in slots]

	def __str__(self):
		return '%s: %s' % (self.secname, self.connections)

class SchemaConnectionSection(Section):
	sectype = 0x3d
	secname = 'Schema/connection'
	def parse(self):
		self._get_zero(2, 2)
		self.symno = self._get_uint16(4)
		self._get_unknown(6, 1)
		self._get_zero(7, 1)
		self.pin = self._get_uint16(8)
		self._get_zero(10, 14)

	def __str__(self):
		return '%s: symbol %d, pin %d' % (self.secname, self.symno, self.pin)

class BoardConnectionSection(Section):
	sectype = 0x3e
	secname = 'Board/connection'
	def parse(self):
		self.pacno = self._get_uint16(4)
		self.pin = self._get_uint16(6)
		self._get_zero(2, 2)
		self._get_zero(8, 16)

	def __str__(self):
		return '%s: package %d, pin %d' % (self.secname, self.pacno, self.pin)

class AttributeSection(TextBaseSection):
	sectype = 0x41
	secname = 'Attribute'

class AttributeValueSection(Section):
	sectype = 0x42
	secname = 'Attribute value'
	def parse(self):
		self.attribute = self._get_name(7, 17)
		self.symbol = self._get_name(2, 5)

	def __str__(self):
		return '%s %s on symbol %s' % (self.secname, self.attribute, self.symbol)

sections = {}
for section in [StartSection, Unknown11Section, GridSection, LayerSection, SchemaSection, LibrarySection, DevicesSection,
		SymbolsSection, PackagesSection, SchemaSheetSection, BoardSection, BoardNetSection, SymbolSection, PackageSection, SchemaNetSection,
		PathSection, PolygonSection, LineSection, CircleSection, RectangleSection, JunctionSection,
		HoleSection, PadSection, SmdSection, PinSection, DeviceSymbolSection, BoardPackageSection, BoardPackage2Section,
		SchemaSymbol2Section, TextSection, NetBusLabelSection, SmashedNameSection, SmashedValueSection, DevicePackageSection, DeviceSection,
		SchemaSymbolSection, SchemaBusSection, DeviceConnectionsSection, SchemaConnectionSection, BoardConnectionSection,
		AttributeSection, AttributeValueSection]:
	sections[section.sectype] = section

class Indenter:
	def __init__(self, section):
		self.section = section
		self.counts = section.subsec_counts[:]
		self.subsecs = [[] for count in self.counts]
		section.subsections = self.subsecs[:]

	def next_section(self):
		while self.counts and self.counts[0] == 0:
			self.counts.pop(0)
			self.subsecs.pop(0)
		if self.counts:
			self.counts[0] -= 1

	def add_subsection(self, subsec):
		self.subsecs[0].append(subsec)

	def __repr__(self):
		return 'Indenter(%r, %r)' % (self.counts, self.section.secname)

def read_layers(f):
	"""
	The sections/whatever are 24 bytes long.
	First byte is section type. Absolutely no idea what the second byte is, it seemed to be some kind of
	further-sections-present-bit (0x00 = not present, 0x80 = is present) at first, but it clearly isn't.
	"""

	data = f.read(24)
	assert len(data) == 24
	sectype = ord(data[0])
	assert sectype == 0x10
	root = sections[sectype](None, data)
	end_offset = root.numsecs * 24
	init_names(f, end_offset)

	root.hexdump()
	print '- ' + str(root)

	indents = [Indenter(root)]
	while True:
		data = f.read(4)
		if not data:
			break
		# Some kind of sentinel?
		if data == '\x13\x12\x99\x19':
			break
		data += f.read(20)

		indents = [indent for indent in indents if sum(indent.counts) > 0]
		for indent in indents:
			indent.next_section()
		#indentstr = ' '.join(indent.section.secname + str(indent.counts) for indent in indents)
		indent = '  ' * len(indents)

		parent = indents[-1]

		sectype = ord(data[0])
		section_cls = sections.get(sectype)
		if section_cls:
			try:
				section = section_cls(parent.section, data)
				assert sum(section.subsec_counts) <= sum(parent.counts)
			except:
				dump_hex_ascii(data)
				raise
			parent.add_subsection(section)
			indents.append(Indenter(section))
			section.hexdump()
			#print indentstr
			print indent + '- ' + str(section)
		else:
			dump_hex_ascii(data)
			raise ValueError, 'Unknown section type'

	assert sum(sum(indent.counts) for indent in indents) == 0

	dump_hex_ascii(data)
	assert data == '\x13\x12\x99\x19'

	return root

_names = None
def init_names(f, end_offset):
	global _names
	pos = f.tell()
	f.seek(end_offset)
	assert f.read(4) == '\x13\x12\x99\x19'
	size = struct.unpack('<I', f.read(4))[0]
	_names = f.read(size).split('\x00')
	f.seek(pos)
	assert _names[-2:] == ['', '']
	_names.pop()
	_names.pop()

_nameind = 0
def get_next_name():
	global _names, _nameind
	name = _names[_nameind]
	_nameind += 1
	return name

def get_name(name):
	# Apparently there is no better way to do this..
	# There are some random bytes after 0x7f, but that's just what they are - random
	# Making a text longer, then shorter again does not result in the same random bytes
	# Making a text from the beginning longer does not affect the random bytes of the following entries
	# Deleting a text from the beginning does not affect the random bytes of the following entries
	# Thus, there really can't be any position information there
	# Thus, we'd just better handle every possible text field...
	if __name__ == '__main__':
		if name[0] != '\x7f':
			return '\x1b[32m' + repr(name.rstrip('\x00')) + '\x1b[m'
		return '\x1b[31m' + repr(get_next_name()) + '\x1b[m'
	else:
		if name[0] != '\x7f':
			return name.rstrip('\x00')
		return get_next_name()

def read_name_array(f):
	size = struct.unpack('<I', f.read(4))[0]
	strings = f.read(size).split('\x00')
	for i, value in enumerate(strings):
		print i, repr(value)
	checksum = f.read(4)

sentinels = {
	'\x25\x04\x00\x20': '\xef\xcd\xab\x89',
	'\x10\x04\x00\x20': '\x98\xba\xdc\xfe',
}

if __name__ == '__main__':
	fname = sys.argv[1]

	with file(fname) as f:
		#data = f.read(6*16)
		#print ''.join('%02x' % (ord(byte),) for byte in data)

		root = read_layers(f)
		read_name_array(f)
		while True:
			start_sentinel = f.read(4)
			if not start_sentinel:
				raise Exception, 'EOF'
			if start_sentinel == '\x99\x99\x99\x99':
				assert f.read(4) == '\x00\x00\x00\x00'
				break
			end_sentinel = sentinels[start_sentinel]
			length = struct.unpack('<I', f.read(4))[0] - 4
			data = f.read(length)
			print 'Extra:', repr(data)
			assert f.read(4) == end_sentinel
			checksum = f.read(4)

		rest = f.read()
		if rest:
			print 'Extra data:'
			dump_hex_ascii(rest)

	assert _nameind == len(_names)

