import sys, os
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

# Values are in tenths of a micrometre
u2mm = lambda val: val/10/1000
u2in = lambda val: val/2.54/100/1000

mm2u = lambda val: val*10*1000
in2u = lambda val: val*254*1000

class Section:
	sectype = None
	secname = None
	def __init__(self, eaglefile, parent, data):
		self.eaglefile = eaglefile
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

	def _get_zero16_mask(self, pos, mask):
		self.zero[pos] |= mask & 0xff
		self.zero[pos+1] |= (mask >> 8) & 0xff
		value = struct.unpack('<H', self.data[pos:pos+2])[0] & mask
		assert value == 0x00, 'Unknown bits in ' + self.secname + ': ' + hex(value)

	def _get_uint32(self, pos): return struct.unpack('<I', self._get_bytes(pos, 4))[0]
	def _get_uint24(self, pos): return struct.unpack('<I', self._get_bytes(pos, 3) + '\x00')[0]
	def _get_uint16(self, pos): return struct.unpack('<H', self._get_bytes(pos, 2))[0]
	def _get_uint8(self, pos):  return struct.unpack('<B', self._get_bytes(pos, 1))[0]

	def _get_int32(self, pos): return struct.unpack('<i', self._get_bytes(pos, 4))[0]
	def _get_int16(self, pos): return struct.unpack('<h', self._get_bytes(pos, 2))[0]
	def _get_int8(self, pos): return struct.unpack('<b', self._get_bytes(pos, 1))[0]

	def _get_double(self, pos): return struct.unpack('<d', self._get_bytes(pos, 8))[0]

	def _get_uint8_mask(self, pos, mask):
		self.known[pos] |= mask
		return ord(self.data[pos]) & mask

	def _get_uint16_mask(self, pos, mask):
		self.known[pos] |= mask & 0xff
		self.known[pos+1] |= (mask >> 8) & 0xff
		return struct.unpack('<H', self.data[pos:pos+2])[0] & mask

	def _get_name(self, pos, size): return self._parse_string(self._get_bytes(pos, size))

	def _parse_string(self, name):
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
			return '\x1b[31m' + repr(self.eaglefile._get_next_string()) + '\x1b[m'
		else:
			if name[0] != '\x7f':
				return name.rstrip('\x00')
			return self.eaglefile._get_next_string()

class UnknownSection(Section):
	secname = '???'
	def parse(self):
		self._get_unknown(2, 22)

	def __str__(self):
		return self.secname

class TextBaseSection(Section):
	def parse(self):
		self.font = self._get_uint8_mask(2, 0x03)
		self._get_zero_mask(2, 0xfc)
		self.layer = self._get_uint8(3)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.size_2 = self._get_uint16(12)
		self.ratio = self._get_uint8_mask(14, 0x7c) >> 2
		self._get_zero_mask(14, 0x03)
		self._get_unknown_mask(14, 0x80)
		self._get_unknown(15, 1)
		self.angle = self._get_uint16_mask(16, 0x0fff)
		self.mirrored = bool(self._get_uint16_mask(16, 0x1000))
		self.spin = bool(self._get_uint16_mask(16, 0x4000))
		self._get_zero16_mask(16, 0xa000)
		if self.sectype in (0x31, 0x41):
			self.text = self._get_name(18, 6)
		assert self.sectype == 0x31 or self.angle & 0x3ff == 0x000, 'Shouldn\'t angle be one of 0, 90, 180 or 270 for this section?'
		# Mostly true, but 0x01 has been spotted once
		#assert self.sectype in (0x31, 0x41) or self.data[18:24] == '\x00'*6, 'This section shouldn\'t contain any text?'
		assert self.sectype in (0x31, 0x41) or self.data[18] != '\x7f', 'This section shouldn\'t contain any text?'

	def __str__(self):
		font = 'vector proportional fixed'.split()[self.font]
		angle = 360 * self.angle / 4096.
		if self.sectype == 0x31:
			extra = ', text ' + self.text
		elif self.sectype == 0x41:
			extra = ', name ' + self.text
		else:
			extra = ''
		return '%s: at (%f", %f") size %f", angle %s, mirror %d, spin %d, layer %d, ratio %d%%, font %s%s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.size_2*2), angle, self.mirrored, self.spin, self.layer, self.ratio, font, extra)

class StartSection(Section):
	sectype = 0x10
	secname = 'Start'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.numsecs = self._get_uint32(4)
		self.major = self._get_uint8(8)
		self.minor = self._get_uint8(9)
		self.version = (self.major, self.minor)
		self._get_unknown(10, 16)
		# XXX: hack
		self.subsec_counts = [self.subsecs, self.numsecs - self.subsecs - 1]

	def __str__(self):
		return '%s: version %s, subsecs %d, numsecs %d' % (self.secname, self.version, self.subsecs, self.numsecs)

class Unknown11Section(UnknownSection):
	sectype = 0x11

# 4 bits of unit
# higher 2 bits tell which unit is used for display
# lower 2 bits tell which unit is used for saving
grid_units2 = 'mic mm mil in'.split()
grid_units4 = [save if save == disp else '%s as %s' % (save, disp) for disp in grid_units2 for save in grid_units2]
class GridSection(Section):
	sectype = 0x12
	secname = 'Grid'
	def parse(self):
		self.display = self._get_uint8_mask(2, 0x01)
		self.style = self._get_uint8_mask(2, 0x02) >> 1
		self._get_zero_mask(2, 0xfc)
		self.unit = self._get_uint8_mask(3, 0x0f)
		self.altunit = self._get_uint8_mask(3, 0xf0) >> 4
		self.multiple = self._get_uint24(4)
		self._get_zero(7, 1)
		self.size = self._get_double(8)
		self.altsize = self._get_double(16)

	def __str__(self):
		style = 'lines dots'.split()[self.style]
		unit = grid_units4[self.unit]
		altunit = grid_units4[self.altunit]
		return '%s: display %s, style %s, size %s%s, multiple %d, alt %s%s' % (self.secname, self.display, style, self.size, unit, self.multiple, self.altsize, altunit)

layer_fills = dict(enumerate('stroke fill horiz thinslash thickslash thickback thinback square diamond dither coarse fine bottomleft bottomright topright topleft'.split()))
layer_colors = dict(enumerate('black darkblue darkgreen darkcyan darkred darkpurple darkyellow grey darkgrey blue green cyan red purple yellow lightgrey'.split()))
class LayerSection(Section):
	sectype = 0x13
	secname = 'Layer'
	def parse(self):
		self.side = self._get_uint8_mask(2, 0x10)
		visible = self._get_uint8_mask(2, 0x0c) # whether objects on this layer are currently shown
		self.available = bool(self._get_uint8_mask(2, 0x02)) # not available => not visible in layer display dialog at all
		self._get_zero_mask(2, 0xe0)
		self._get_unknown_mask(2, 0x01)
		self.layer = self._get_uint8(3)
		self.other = self._get_uint8(4) # the number of the matching layer on the other side
		self.fill = self._get_uint8_mask(5, 0x0f)
		self._get_zero_mask(5, 0xf0)
		self.color = self._get_uint8_mask(6, 0x3f)
		self._get_zero_mask(6, 0xc0)
		self._get_unknown(7, 1)
		self._get_zero(8, 7)
		self.name = self._get_name(15, 9)
		# This is usually true, but on schemas some layers not used on schemas may have 0x04 here
		#assert visible in (0x00, 0x0c), 'I thought visibility always set two bits?'
		self.visible = bool(visible)
		# The ulp "visible" flag is basically "visible and not hidden", or "flags & 0x0e == 0x0e"
		self.ulpvisible = self.visible and self.available

	def __str__(self):
		side = 'bottom' if self.side else 'top'
		fill = layer_fills[self.fill]
		color = layer_colors.get(self.color, '?grey?')
		return '%s %s: layer %d, other %d, side %s, visible %d, fill %d %s, color %d %s' % (self.secname, self.name, self.layer, self.other, self.side, self.ulpvisible, self.fill, fill, self.color, color)

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
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self.airwires = not bool(self._get_uint8_mask(12, 0x02))
		self._get_zero_mask(12, 0xfd)
		self.netclass = self._get_uint8_mask(13, 0x07)
		self._get_zero_mask(13, 0xf8)
		self._get_zero(14, 2)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: limits (%dmil, %dmil), (%dmil, %dmil), netclass %d, airwires %d, subsecs %d' % (self.secname, self.name, self.minx, self.miny, self.maxx, self.maxy, self.netclass, self.airwires, self.subsecs)

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
		# Seem to always be (32767mil, 32767mil), (-32768mil, -32768mil)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self._get_zero(12, 1)
		self.netclass = self._get_uint8_mask(13, 0x07)
		self._get_zero_mask(13, 0xf8)
		self._get_zero(14, 2)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: limits (%dmil, %dmil), (%dmil, %dmil), netclass %d, subsecs %s' % (self.secname, self.name, self.minx, self.miny, self.maxx, self.maxy, self.netclass, self.subsecs)

class PathSection(Section):
	sectype = 0x20
	secname = 'Path'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self._get_zero(12, 12)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: limits (%dmil, %dmil), (%dmil, %dmil), subsecs %d' % (self.secname, self.minx, self.miny, self.maxx, self.maxy, self.subsecs)

class PolygonSection(Section):
	sectype = 0x21
	secname = 'Polygon'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.minx = self._get_int16(4)
		self.miny = self._get_int16(6)
		self.maxx = self._get_int16(8)
		self.maxy = self._get_int16(10)
		self.width_2 = self._get_uint16(12)
		self.spacing_2 = self._get_uint16(14)
		self.isolate_2 = self._get_uint16(16)
		self.layer = self._get_uint8(18)
		self.pour = 'hatch' if self._get_uint8_mask(19, 0x01) else 'solid'
		self.rank = self._get_uint8_mask(19, 0x0e) >> 1
		assert 0 <= self.rank <= 7, 'Unknown rank: %d' % (self.rank, ) # 7 for schema polygons, 0 seen in package
		self.thermals = bool(self._get_uint8_mask(19, 0x80))
		self.orphans = bool(self._get_uint8_mask(19, 0x40))
		self._get_zero_mask(19, 0x30)
		# These unknown bytes seem to somehow relate to whether the polygon is currently calculated or not (they are all zero when it's not calculated)
		self._get_unknown(20, 4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: limits (%dmil, %dmil), (%dmil, %dmil), width %f", spacing %f", isolate %f", pour %s, rank %d, thermals %d, orphans %d, layer %d, subsecs %d' % (self.secname, self.minx, self.miny, self.maxx, self.maxy, u2in(self.width_2*2), u2in(self.spacing_2*2), u2in(self.isolate_2*2), self.pour, self.rank, self.thermals, self.orphans, self.layer, self.subsecs)

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
			self._get_zero_mask(22, 0xc0)
			self._get_unknown_mask(22, 0x0c)

			# Cap style and positive curve are present on bare lines too, that's probably a bug
			self.clockwise = bool(self.stflags & 0x20)
			self.style = {0x00: 'continuous', 0x01: 'longdash', 0x02: 'shortdash', 0x03: 'dashdot'}[self.stflags & 0x03]
			self.cap = {0x00: 'round', 0x10: 'flat'}[self.stflags & 0x10]
		else:
			self._get_unknown(22, 1)

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

class ElementSection(Section):
	sectype = 0x24
	secname = 'Element'
	def parse(self):
		self._get_unknown(2, 22)

	def __str__(self):
		return self.secname

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
		self.angle = self._get_uint16_mask(20, 0x0fff)
		self._get_zero16_mask(20, 0xf000)
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

class ViaSection(Section):
	sectype = 0x29
	secname = 'Via'
	def parse(self):
		self.shape = self._get_uint8_mask(2, 0x03)
		self._get_zero_mask(2, 0xfc)
		self._get_unknown(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.drill_2 = self._get_uint16(12)
		self.diameter_2 = self._get_uint16(14)
		self.layers = self._get_uint8_mask(16, 0x0f) + 1, (self._get_uint8_mask(16, 0xf0) >> 4) + 1
		self.stop = self._get_uint8_mask(17, 0x01)
		self._get_zero_mask(17, 0xfe)
		self._get_zero(18, 6)

	def __str__(self):
		shape = 'square round octagon'.split()[self.shape]
		return '%s: at (%f", %f"), diameter %f", drill %f", shape %s, layers %d-%d, stop %d' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.diameter_2*2), u2in(self.drill_2*2), shape, self.layers[0], self.layers[1], self.stop)

class PadSection(Section):
	sectype = 0x2a
	secname = 'Pad'
	def parse(self):
		self.shape = self._get_uint8_mask(2, 0x07)
		self._get_zero_mask(2, 0xf8)
		self._get_zero(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.drill_2 = self._get_uint16(12)
		self.diameter_2 = self._get_uint16(14)
		self.angle = self._get_uint16_mask(16, 0x0fff)
		self._get_zero16_mask(16, 0xf000)
		self.stop = not bool(self._get_uint8_mask(18, 0x01))
		self.thermals = not bool(self._get_uint8_mask(18, 0x04))
		self.first = bool(self._get_uint8_mask(18, 0x08))
		self._get_zero_mask(18, 0xf2)
		self.name = self._get_name(19, 5)

	def __str__(self):
		shape = 'square round octagon long offset'.split()[self.shape]
		return '%s: at (%f", %f"), diameter %f", drill %f", angle %f, shape %s, first %d, stop %d, thermals %d, name %s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.diameter_2*2), u2in(self.drill_2*2), 360 * self.angle / 4096., shape, self.first, self.stop, self.thermals, self.name)

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
		self.angle = self._get_uint16_mask(16, 0x0fff)
		self._get_zero16_mask(16, 0xf000)
		self.stop = not bool(self._get_uint8_mask(18, 0x01))
		self.cream = not bool(self._get_uint8_mask(18, 0x02))
		self.thermals = not bool(self._get_uint8_mask(18, 0x04))
		self._get_zero_mask(18, 0xf8)
		self.name = self._get_name(19, 5)

	def __str__(self):
		return '%s: at (%f", %f"), size %f" x %f", angle %f, layer %d, roundness %d%%, stop %d, cream %d, thermals %d, name %s' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.width_2*2), u2in(self.height_2*2), 360 * self.angle / 4096., self.layer, self.roundness, self.stop, self.cream, self.thermals, self.name)

class PinSection(Section):
	sectype = 0x2c
	secname = 'Pin'
	def parse(self):
		self.function = self._get_uint8_mask(2, 0x03)
		self.visible = self._get_uint8_mask(2, 0xc0) >> 6
		self._get_zero_mask(2, 0x3c)
		self._get_zero(3, 1)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.direction = self._get_uint8_mask(12, 0x0f)
		self.length = self._get_uint8_mask(12, 0x30) >> 4
		self.angle = self._get_uint8_mask(12, 0xc0) << 4
		self.swaplevel = self._get_uint8(13)
		self.name = self._get_name(14, 10)

	def __str__(self):
		func = 'None Dot Clk DotClk'.split()[self.function]
		vis = 'Off Pad Pin Both'.split()[self.visible]
		dir_ = 'Nc In Out I/O OC Pwr Pas Hiz Sup'.split()[self.direction]
		len_ = 'Point Short Middle Long'.split()[self.length]
		angle = 360 * self.angle / 4096.
		return '%s: at (%f", %f"), name %s, angle %s, direction %s, swaplevel %s, length %s, function %s, visible %s' % (self.secname, u2in(self.x), u2in(self.y), self.name, angle, dir_, self.swaplevel, len_, func, vis)

class DeviceSymbolSection(Section):
	sectype = 0x2d
	secname = 'Device/symbol'
	def parse(self):
		self._get_zero(2, 2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.addlevel = self._get_uint8(12)
		self.swap = self._get_uint8(13)
		self.symno = self._get_uint16(14)
		self.name = self._get_name(16, 8)

	def __str__(self):
		addlevel = 'Must Can Next Request Always'.split()[self.addlevel]
		return '%s %d: at (%f", %f"), name %s, swap %d, addlevel %s' % (self.secname, self.symno, u2in(self.x), u2in(self.y), self.name, self.swap, addlevel)

class BoardPackageSection(Section):
	sectype = 0x2e
	secname = 'Board/package'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.libno = self._get_uint16(12)
		self.pacno = self._get_uint16(14)
		self.angle = self._get_uint16_mask(16, 0x0fff)
		self.mirrored = bool(self._get_uint16_mask(16, 0x1000))
		self._get_zero16_mask(16, 0xe000)
		self._get_unknown(18, 1)
		self._get_zero(19, 1)
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

class SchemaSymbolSection(Section):
	sectype = 0x30
	secname = 'Schema/symbol'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		placed = self._get_int16(12)
		assert placed in (0, -1), 'What\'s this?'
		self.placed = placed == -1
		self.symno = self._get_uint16(14)
		self.angle = self._get_uint16_mask(16, 0x0c00)
		self.mirrored = bool(self._get_uint16_mask(16, 0x1000))
		self._get_zero16_mask(16, 0xe3ff)
		self.smashed = bool(self._get_uint8_mask(18, 0x01))
		self._get_zero_mask(18, 0xfe)
		self._get_zero(19, 1)
		self._get_unknown(20, 4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d: at (%f", %f"), angle %f, mirror %d, smashed %d, placed %d' % (self.secname, self.symno, u2in(self.x), u2in(self.y), 360 * self.angle / 4096., self.mirrored, self.smashed, self.placed)

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
		self.subsecs = self._get_uint16(2)
		self.pacno = self._get_uint16(4)
		self.variant = self._get_name(19, 5)
		self.table = self._get_name(6, 13)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d: variant %s, table %s, subsecs %d' % (self.secname, self.pacno, self.variant, self.table, self.subsecs)

class DeviceSection(Section):
	sectype = 0x37
	secname = 'Device'
	def parse(self):
		self.symsubsecs = self._get_uint16(2)
		self.pacsubsecs = self._get_uint16(4)
		self.value_on = bool(self._get_uint8_mask(6, 0x01))
		self._get_unknown_mask(6, 0x02)
		self._get_zero_mask(6, 0xfc)
		self.con_byte = self._get_uint8_mask(7, 0x80) >> 7
		self.pin_bits = self._get_uint8_mask(7, 0x0f)
		self._get_zero_mask(7, 0x70)
		self.name = self._get_name(18, 6)
		self.desc = self._get_name(13, 5)
		self.prefix = self._get_name(8, 5)
		self.subsec_counts = [self.pacsubsecs, self.symsubsecs]

	def __str__(self):
		return '%s %s: prefix %s, desc %s, con_byte %d, pin_bits %d, value_on %d, pacsubsecs %d, symsubsecs %d' % (self.secname, self.name, self.prefix, self.desc, self.con_byte, self.pin_bits, self.value_on, self.pacsubsecs, self.symsubsecs)

class SchemaDeviceSection(Section):
	sectype = 0x38
	secname = 'Schema/device'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.libno = self._get_uint16(4)
		self.devno = self._get_uint16(6)
		self.pacno = self._get_uint8(8)
		self._get_unknown(9, 2)
		self.value = self._get_name(16, 8)
		self.name = self._get_name(11, 5)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d@%d, name %s, value %s, subsecs %d' % (self.secname, self.devno, self.libno, self.name, self.value, self.subsecs)

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
		fmt = '<' + ('22B' if self.parent.parent.con_byte else '11H')
		slots = struct.unpack(fmt, self._get_bytes(2, 22))
		# connections[padno] = (symno, pinno)
		self.connections = [(slot >> self.parent.parent.pin_bits, slot & ((1 << self.parent.parent.pin_bits) - 1)) for slot in slots]

	def __str__(self):
		return '%s: %s' % (self.secname, self.connections)

class SchemaConnectionSection(Section):
	sectype = 0x3d
	secname = 'Schema/connection'
	def parse(self):
		self._get_zero(2, 2)
		self.devno = self._get_uint16(4)
		self.symno = self._get_uint16(6)
		self.pin = self._get_uint16(8)
		self._get_zero(10, 14)

	def __str__(self):
		return '%s: device %d, symbol %d, pin %d' % (self.secname, self.devno, self.symno, self.pin)

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

class SmashedPartSection(TextBaseSection):
	sectype = 0x3f
	secname = 'Smashed part'

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

class FrameSection(Section):
	sectype = 0x43
	secname = 'Frame'
	def parse(self):
		self._get_unknown(2, 1)
		self.layer = self._get_uint8(3)
		self.x1 = self._get_int32(4)
		self.y1 = self._get_int32(8)
		self.x2 = self._get_int32(12)
		self.y2 = self._get_int32(16)
		self.cols = self._get_int8(20)
		self.rows = self._get_int8(21)
		self.borders = self._get_uint8_mask(22, 0x0f)
		self._get_zero_mask(22, 0xf0)
		self._get_zero(23, 1)

	def __str__(self):
		borders = ' '.join(border for border in ['bottom' if self.borders & 0x01 else None, 'right' if self.borders & 0x02 else None, 'top' if self.borders & 0x04 else None, 'left' if self.borders & 0x08 else None] if border) or 'none'
		return '%s: from (%f", %f") to (%f", %f"), size %dx%d, layer %d, border %s' % (self.secname, u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), self.cols, self.rows, self.layer, borders)

sections = {}
for section in [StartSection, Unknown11Section, GridSection, LayerSection, SchemaSection, LibrarySection, DevicesSection,
		SymbolsSection, PackagesSection, SchemaSheetSection, BoardSection, BoardNetSection, SymbolSection, PackageSection, SchemaNetSection,
		PathSection, PolygonSection, LineSection, ElementSection, CircleSection, RectangleSection, JunctionSection,
		HoleSection, ViaSection, PadSection, SmdSection, PinSection, DeviceSymbolSection, BoardPackageSection, BoardPackage2Section,
		SchemaSymbolSection, TextSection, NetBusLabelSection, SmashedNameSection, SmashedValueSection, DevicePackageSection, DeviceSection,
		SchemaDeviceSection, SchemaBusSection, DeviceConnectionsSection, SchemaConnectionSection, BoardConnectionSection, SmashedPartSection,
		AttributeSection, AttributeValueSection, FrameSection]:
	sections[section.sectype] = section

def _cut(fmt, data, size, onlyone = False):
	if not onlyone:
		return struct.unpack(fmt, data[:size]), data[size:]
	return struct.unpack(fmt, data[:size])[0], data[size:]

class DRCRules:
	def __init__(self, eaglefile, data):
		self.version = eaglefile.root.major
		ind = data.index('\x00')
		self.name, data = data[:ind], data[ind+1:]
		ind = data.index('\x00')
		self.desc, data = data[:ind], data[ind+1:]
		if struct.unpack('<I', data[:4])[0] != 0x12345678:
			ind = data.index('\x00')
			self.stackup, data = data[:ind], data[ind+1:]
		else:
			self.stackup = 'xxx'
		# XXX: Does not handle design rules from older versions
		assert (self.version, len(data)) in [(5, 426), (4, 319)]
		magic, data = _cut('<I', data, 4, True)
		assert magic == 0x12345678
		# wire2wire wire2pad wire2via pad2pad pad2via via2via pad2smd via2smd smd2smd
		self.clearances, data = _cut('<9I', data, 36)
		const, data = _cut('<2I', data, 8)
		assert const == (2032, 2)
		(self.copper2dimension, zero, self.drill2hole), data = _cut('<3I', data, 12)
		assert zero == 0
		const, data = _cut('<2I', data, 8)
		assert const == (0, 0)
		(self.min_width, self.min_drill), data = _cut('<2I', data, 8)
		if self.version >= 5:
			(self.min_micro_via, self.blind_via_ratio), data = _cut('<Id', data, 12)
		# restring order: padtop padinner padbottom viaouter viainner (microviaouter microviainner)
		if self.version >= 5:
			self.restring_percentages, data = _cut('<7d', data, 56)
			restring_limits, data = _cut('<14I', data, 56)
		else:
			self.restring_percentages, data = _cut('<5d', data, 40)
			restring_limits, data = _cut('<10I', data, 40)
		self.restring_mins = restring_limits[0::2]
		self.restring_maxs = restring_limits[1::2]
		# top bottom first, -1=As in library, 0=square, 1=round, 2=octagon
		# XXX: check first for older
		self.pad_shapes, data = _cut('<3i', data, 12)
		# mask order: stop cream
		self.mask_percentages, data = _cut('<2d', data, 16)
		mask_limits, data = _cut('<5I', data, 20)
		self.mask_mins = mask_limits[0:4:2]
		self.mask_maxs = mask_limits[1:4:2]
		self.mask_limit = mask_limits[4]
		# XXX: Too lazy to do other shape data
		# percentage min max
		self.smd_roundness, data = _cut('<dII', data, 16)
		self.supply_gap, data = _cut('<dII', data, 16)
		(self.supply_annulus, self.supply_thermal), data = _cut('<II', data, 8)
		(self.restring_annulus, self.restring_thermal, self.via_thermals), data = _cut('<3B', data, 3)
		(self.check_grid, self.check_angle, xxx), data = _cut('<BBI', data, 6)
		assert xxx == 50
		if self.version < 5:
			xxx, data = _cut('<34s', data, 34, True)
			print repr(xxx)
			assert xxx == '\xff\xff\xf0\x00' + 30*'\x00'
		(self.check_font, self.check_restrict), data = _cut('<BB', data, 2)
		xxx, data = _cut('<B', data, 1, True)
		assert xxx == 13
		if self.version >= 5:
			(self.long_elongation, self.offset_elongation), data = _cut('<2B', data, 2)
			self.layer_coppers, data = _cut('<16I', data, 64)
			self.layer_isolations, data = _cut('<15I', data, 60)
		else:
			xxx, data = _cut('<29s', data, 29, True)
			assert xxx == 29*'\x00'
		assert data == ''

	def dump(self):
		print (self.name, self.desc, self.stackup)
		print 'Clearances:', self.clearances
		print 'Copper/dimension / drill/hole:', self.copper2dimension, self.drill2hole
		print 'Minimum width/drill:', self.min_width, self.min_drill
		if self.version >= 5:
			print 'Minimum micro via/blind via ratio:', self.min_micro_via, self.blind_via_ratio
		print 'Restring perc/min/max:', self.restring_percentages, self.restring_mins, self.restring_maxs
		print 'Pad shapes top/bottom/first:', self.pad_shapes
		print 'Mask perc/min/max / limit:', self.mask_percentages, self.mask_mins, self.mask_maxs, self.mask_limit
		print 'SMD roundness:', self.smd_roundness
		print 'Supply gap:', self.supply_gap
		print 'Supply thermal/annulus:', self.supply_thermal, self.supply_annulus
		print 'Supply restring annulus/thermal / via thermals:', self.restring_annulus, self.restring_thermal, self.via_thermals
		print 'Check grid/angle/font/restrict:', self.check_grid, self.check_angle, self.check_font, self.check_restrict
		if self.version >= 5:
			print 'Elongation for long/offset pad:', self.long_elongation, self.offset_elongation
			print 'Layer coppers/isolations:', self.layer_coppers, self.layer_isolations

class NetClass:
	def __init__(self, eaglefile, data):
		self.version = eaglefile.root.major
		length = {5: 48, 4: 20}[self.version]
		if len(data) > length:
			ind = data.index('\x00')
			self.name, data = data[:ind], data[ind+1:]
		else:
			self.name = ''
		assert (self.version, len(data)) in [(5, 48), (4, 20)]
		self.netclassno, magic, self.width, self.drill = struct.unpack('<IIII', data[0:16])
		assert magic == 0x87654321
		if self.version >= 5:
			self.clearances = struct.unpack('<8I', data[16:48])
			assert self.clearances[self.netclassno+1:] == (7-self.netclassno)*(0,), 'I thought clearances outside the triangle were supposed to always be zero?'
		else:
			self.clearances = self.netclassno * (0, ) + struct.unpack('<I', data[16:20])

	def dump(self):
		print 'Netclass %d, %s: width %f", drill %f", clearance %f", others %r' % (self.netclassno, self.name, u2in(self.width), u2in(self.drill), u2in(self.clearances[self.netclassno]), self.clearances[:self.netclassno])

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

class UnknownRule:
	def __init__(self, eaglefile, data):
		self.data = data

	def dump(self):
		print repr(self.data)

sentinels = {
	'\x25\x04\x00\x20': (['\xef\xcd\xab\x89'], NetClass),
	'\x10\x04\x00\x20': (['\x98\xba\xdc\xfe'], DRCRules),
	'\x23\x05\x00\x20': (['\x30\x01\x09\x20', '\x64\x00\x00\x00', '\xf4\x01\x00\x00'], UnknownRule),
}

class EagleFile:
	def __init__(self, f):
		self.string_index = 0
		self._read_sections(f)
		assert self.string_index == len(self.strings)
		self._skip_strings(f)
		self._read_rules(f)

	def _read_rules(self, f):
		self.rules = []
		while True:
			start_sentinel = f.read(4)
			if not start_sentinel:
				raise Exception, 'EOF'
			if start_sentinel == '\x99\x99\x99\x99':
				assert f.read(4) == '\x00\x00\x00\x00'
				break
			end_sentinels, parser = sentinels[start_sentinel]
			length = struct.unpack('<I', f.read(4))[0] - 4
			data = f.read(length)
			section = parser(self, data)
			self.rules.append(section)
			section.dump()
			sentinel = f.read(4)
			assert sentinel in end_sentinels, 'Wrong end sentinel: ' + repr(sentinel)
			checksum = f.read(4)

		rest = f.read()
		if rest:
			print 'Extra data:'
			dump_hex_ascii(rest)

	def _init_strings(self, f, offset):
		pos = f.tell()
		f.seek(offset)
		assert f.read(4) == '\x13\x12\x99\x19'
		size = struct.unpack('<I', f.read(4))[0]
		self.strings = f.read(size).split('\x00')
		f.seek(pos)
		assert self.strings[-2:] == ['', '']
		self.strings.pop()
		self.strings.pop()

	def _skip_strings(self, f):
		size = struct.unpack('<I', f.read(4))[0]
		# Skip strings and checksum
		f.seek(size + 4, os.SEEK_CUR)

	def _get_next_string(self):
		name = self.strings[self.string_index]
		self.string_index += 1
		return name

	def _read_sections(self, f):
		# The sections/whatever are 24 bytes long.
		# First byte is section type. Absolutely no idea what the second byte is, it seemed to be some kind of
		# further-sections-present-bit (0x00 = not present, 0x80 = is present) at first, but it clearly isn't.

		# Read first section and initialize strings
		data = f.read(24)
		assert len(data) == 24
		sectype = ord(data[0])
		assert sectype == 0x10
		self.root = sections[sectype](self, None, data)
		end_offset = self.root.numsecs * 24
		self._init_strings(f, end_offset)

		self.root.hexdump()
		print '- ' + str(self.root)

		indents = [Indenter(self.root)]
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
					section = section_cls(self, parent.section, data)
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

if __name__ == '__main__':
	fname = sys.argv[1]

	with file(fname) as f:
		EagleFile(f)

