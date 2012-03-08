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
	def __init__(self, data):
		self.data = data
		self.known = [0x00] * 24
		self.zero = [0x00] * 24
		self.subsec_counts = []
		self._get_uint8(0)
		self.parse()

	def _get_color(self, known, zero = 0):
		assert known & zero == 0x00, "Bit can't be known and zero at the same time! (known = %s, zero = %s, known & zero = %s)" % (hex(known), hex(zero), hex(known & zero))
		if known == 0x00 and zero == 0x00:
			return '1;31' # unknown, red
		elif known == 0xff and zero == 0x00:
			return '1;32' # known, green
		elif known == 0x00 and zero == 0xff:
			return '1;34' # zero, blue
		elif zero == 0x00:
			return '1;33' # known/unknown, yellow
		elif known == 0x00:
			return '1;35' # unknown/zero, purple
		elif known | zero == 0xff:
			return '1;36' # known/zero, cyan
		else:
			return '1;37' # known/unknown/zero, white

	def hexdump(self):
		colorhex = ' '.join('\x1b[%sm%02x\x1b[m' % (self._get_color(known, zero), ord(byte)) for byte, known, zero in zip(self.data, self.known, self.zero))
		colorascii = ''.join('\x1b[%sm%s\x1b[m' % (self._get_color(known, zero), byte if 32 <= ord(byte) < 127 else '.') for byte, known, zero in zip(self.data, self.known, self.zero))
		print colorhex, colorascii

	def _get_bytes(self, pos, size):
		self.known[pos:pos+size] = [0xff] * size
		return self.data[pos:pos+size]

	def _get_zero(self, pos, size):
		self.zero[pos:pos+size] = [0xff] * size
		assert self.data[pos:pos+size] == '\x00' * size, 'Unknown data: ' + repr(self.data[pos:pos+size])

	def _get_zero_mask(self, pos, mask):
		self.zero[pos] |= mask
		assert ord(self.data[pos]) & mask == 0x00, 'Unknown bits: ' + hex(ord(self.data[pos]) & mask)

	def _get_uint32(self, pos): return struct.unpack('<I', self._get_bytes(pos, 4))[0]
	def _get_uint24(self, pos): return struct.unpack('<I', self._get_bytes(pos, 3) + '\x00')[0]
	def _get_uint16(self, pos): return struct.unpack('<H', self._get_bytes(pos, 2))[0]
	def _get_uint8(self, pos):  return struct.unpack('<B', self._get_bytes(pos, 1))[0]

	def _get_int32(self, pos): return struct.unpack('<i', self._get_bytes(pos, 4))[0]

	def _get_uint8_mask(self, pos, mask):
		self.known[pos] |= mask
		return ord(self.data[pos]) & mask

	def _get_name(self, pos, size): return get_name(self._get_bytes(pos, size))

class UnknownSection(Section):
	secname = '???'
	def parse(self): pass
	def __str__(self): return self.secname

class StartSection(Section):
	sectype = 0x10
	secname = 'Start'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.numsecs = self._get_uint32(4)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: subsecs %d, numsecs %d' % (self.secname, self.subsecs, self.numsecs)

class Unknown11Section(UnknownSection):
	sectype = 0x11

class Unknown12Section(UnknownSection):
	sectype = 0x12

class LayerSection(Section):
	sectype = 0x13
	secname = 'Layer'
	def parse(self):
		self.flags = self._get_uint8_mask(2, 0x1e)
		self._get_zero_mask(2, 0xe0)
		self.layer = self._get_uint8(3)
		self.other = self._get_uint8(4)
		self.fill = self._get_uint8(5)
		self.color = self._get_uint8(6)
		self._get_zero(7, 8)
		self.name = self._get_name(15, 9)
		self.side = 'bottom' if self.flags & 0x10 else 'top'
		assert self.flags & 0x0c in (0x00, 0x0c), 'I thought visibility always set two bits?'
		self.visible = self.flags & 0x0c == 0x0c # whether objects on this layer are currently shown
		self.available = self.flags & 0x02 == 0x02 # not available => not visible in layer display dialog at all
		# The ulp "visible" flag is basically "visible and not hidden", or "flags & 0x0e == 0x0e"
		self.ulpvisible = self.visible and self.available

	def __str__(self):
		return '%s %s: layer %d, other %d, side %s, visible %d, fill %d, color %d' % (self.secname, self.name, self.layer, self.other, self.side, self.ulpvisible, self.fill, self.color)

class XrefFormatSection(Section):
	sectype = 0x14
	secname = 'Xref format'
	def parse(self):
		self.format = self._get_name(19, 5)

	def __str__(self):
		return '%s: %s' % (self.secname, self.format)

class LibrarySection(Section):
	sectype = 0x15
	secname = 'Library'
	def parse(self):
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
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint32(8)
		self.libname = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, subsecs %d, children %d' % (self.secname, self.libname, self.subsecs, self.children)

class SymbolsSection(Section):
	sectype = 0x18
	secname = 'Symbols'
	def parse(self):
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint32(8)
		self.libname = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, subsecs %d, children %d' % (self.secname, self.libname, self.subsecs, self.children)

class PackagesSection(Section):
	sectype = 0x19
	secname = 'Packages'
	def parse(self):
		self.subsecs = self._get_uint32(4)
		self.children = self._get_uint16(8)
		self.libname = self._get_name(16, 8)
		self.desc = self._get_name(10, 6)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: libname %s, desc %s, subsecs %d, children %d' % (self.secname, self.libname, self.desc, self.subsecs, self.children)

class SchemaSection(Section):
	sectype = 0x1a
	secname = 'Schema'
	def parse(self):
		self.symsubsecs = self._get_uint32(12)
		self.bussubsecs = self._get_uint32(16)
		self.netsubsecs = self._get_uint32(20)
		self.subsec_counts = [self.symsubsecs, self.bussubsecs, self.netsubsecs]

	def __str__(self):
		return '%s: symsubsecs %d, bussubsecs %d, netsubsecs %d' % (self.secname, self.symsubsecs, self.bussubsecs, self.netsubsecs)

class BoardSection(Section):
	sectype = 0x1b
	secname = 'Board'
	def parse(self):
		self.defsubsecs = self._get_uint32(12)
		self.pacsubsecs = self._get_uint32(16)
		self.netsubsecs = self._get_uint32(20)
		self.subsec_counts = [self.defsubsecs, self.pacsubsecs, self.netsubsecs]

	def __str__(self):
		return '%s: defsubsecs %d, pacsubsecs %d, netsubsecs %d' % (self.secname, self.defsubsecs, self.pacsubsecs, self.netsubsecs)

class BoardNetSection(Section):
	sectype = 0x1c
	secname = 'Board/net'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %d' % (self.secname, self.name, self.subsecs)

class SymbolSection(Section):
	sectype = 0x1d
	secname = 'Symbol'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %d' % (self.secname, self.name, self.subsecs)

class PackageSection(Section):
	sectype = 0x1e
	secname = 'Package'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.name = self._get_name(18, 6)
		self.desc = self._get_name(13, 5)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: desc %s, subsecs %d' % (self.secname, self.name, self.desc, self.subsecs)

class SchemaNetSection(Section):
	sectype = 0x1f
	secname = 'Schema/net'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.name = self._get_name(16, 8)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %s: subsecs %s' % (self.secname, self.name, self.subsecs)

class PathSection(Section):
	sectype = 0x20
	secname = 'Path'
	def parse(self):
		self.subsecs = self._get_uint16(2)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: subsecs %d' % (self.secname, self.subsecs)

class PolygonSection(Section):
	sectype = 0x21
	secname = 'Polygon'
	def parse(self):
		self.width_2 = self._get_uint16(12)
		self.spacing_2 = self._get_uint16(14)
		self.layer = self._get_uint8(18)
		self.pour = 'hatch' if self._get_uint8_mask(19, 0x01) else 'solid'

	def __str__(self):
		return '%s: width %f", spacing %f", pour %s, layer %d' % (self.secname, u2in(self.width_2*2), u2in(self.spacing_2*2), self.pour, self.layer)

class LineSection(Section):
	sectype = 0x22
	secname = 'Line'
	def parse(self):
		self.layer = self._get_uint8(3)
		self.width_2 = self._get_uint16(20)
		self.linetype = self._get_uint8(23)

		assert self.linetype in (0x00, 0x01, 0x81, 0x7e, 0x7f, 0x7b, 0x79, 0x78, 0x7a, 0x7d, 0x7c), 'Unknown line type: ' + hex(arctype)

		if self.linetype != 0x01:
			self.stflags = self._get_uint8_mask(22, 0x33)
			self._get_zero_mask(22, 0xcc)

			# Status flags; 0x20 == positive curve value
			# Cap style and positive curve are present on bare lines too, that's probably a bug
			self.style = {0x00: 'continuous', 0x01: 'longdash', 0x02: 'shortdash', 0x03: 'dashdot'}[self.stflags & 0x03]
			self.cap = {0x00: 'round', 0x10: 'flat'}[self.stflags & 0x10]

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

	def __str__(self):
		if self.linetype == 0x00:
			return 'Line: from (%f", %f") to (%f", %f"), width %f", layer %d, style %s' % (u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), u2in(self.width_2*2), self.layer, self.style)
		elif self.linetype == 0x01:
			return 'Airwire: from (%f", %f") to (%f", %f"), width %f", layer %d' % (u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), u2in(self.width_2*2), self.layer)
		elif self.linetype == 0x81:
			return 'Arc: from (%f", %f") to (%f", %f"), center at (%f", %f"), width %f", layer %d, style %s, cap %s' % (u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), u2in(self.cx), u2in(self.cy), u2in(self.width_2*2), self.layer, self.style, self.cap)
		else:
			arctype = {0x78: '90 downleft', 0x79: '90 downright', 0x7a: '90 upright', 0x7b: '90 upleft', 0x7c: '180 left', 0x7d: '180 right', 0x7e: '180 down', 0x7f: '180 up'}[self.linetype]
			return 'Arc: from (%f", %f") to (%f", %f"), type %s, width %f", layer %d, style %s, cap %s' % (u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), arctype, u2in(self.width_2*2), self.layer, self.style, self.cap)

class CircleSection(Section):
	sectype = 0x25
	secname = 'Circle'
	def parse(self):
		self.layer = self._get_uint8(3)
		self.x1 = self._get_int32(4)
		self.y1 = self._get_int32(8)
		self.r = self._get_int32(12)
		self.width_2 = self._get_uint32(20)
		#assert r == _get_int32(16) # Almost always the same...

	def __str__(self):
		return '%s: at (%f", %f"), radius %f", width %f", layer %d' % (self.secname, u2in(self.x1), u2in(self.y1), u2in(self.r), u2in(self.width_2*2), self.layer)

class RectangleSection(Section):
	sectype = 0x26
	secname = 'Rectangle'
	def parse(self):
		self.layer = self._get_uint8(3)
		self.x1 = self._get_int32(4)
		self.y1 = self._get_int32(8)
		self.x2 = self._get_int32(12)
		self.y2 = self._get_int32(16)
		self.angle = self._get_uint16(20)

	def __str__(self):
		return '%s: from (%f", %f") to (%f", %f"), angle %f, layer %d' % (self.secname, u2in(self.x1), u2in(self.y1), u2in(self.x2), u2in(self.y2), 360 * self.angle / 4096., self.layer)

class JunctionSection(Section):
	sectype = 0x27
	secname = 'Junction'
	def parse(self):
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)

	def __str__(self):
		return '%s: at (%f", %f")' % (self.secname, u2in(self.x), u2in(self.y))

class HoleSection(Section):
	sectype = 0x28
	secname = 'Hole'
	def parse(self):
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
		self.width_2 = self._get_uint32(12)

	def __str__(self):
		return '%s: at (%f", %f") drill %f"' % (self.secname, u2in(self.x), u2in(self.y), u2in(self.width_2*2))

class PadSection(Section):
	sectype = 0x2a
	secname = 'Pad'
	def parse(self):
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
		self.x = self._get_int32(4)
		self.y = self._get_int32(8)
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
		self.pacno = self._get_uint16(14)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d: at (%f", %f"), subsecs %d' % (self.secname, self.pacno, u2in(self.x), u2in(self.y), self.subsecs)

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
		self.angle = [0, 90, 180, 270][self._get_uint8_mask(17, 0x0c) >> 2]
		self._get_zero_mask(17, 0xf3)
		self.smashed = self._get_uint8_mask(18, 0x01) == 0x01
		self._get_zero_mask(18, 0xfe)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s: at (%f", %f"), angle %d, smashed %d' % (self.secname, u2in(self.x), u2in(self.y), self.angle, self.smashed)

class DevicePackageSection(Section):
	sectype = 0x36
	secname = 'Device/package'
	def parse(self):
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
		self.symno = self._get_uint16(6)
		self.value = self._get_name(16, 8)
		self.name = self._get_name(11, 5)
		self.subsec_counts = [self.subsecs]

	def __str__(self):
		return '%s %d, name %s, value %s, subsecs %d' % (self.secname, self.symno, self.name, self.value, self.subsecs)

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
		# XXX: change to parent.con_byte when we have parents
		fmt = '<' + ('22B' if con_byte else '11H')
		slots = struct.unpack(fmt, self._get_bytes(2, 22))
		# connections[padno] = (symno, pinno)
		self.connections = [(slot >> pin_bits, slot & ((1 << pin_bits) - 1)) for slot in slots]

	def __str__(self):
		return '%s: %s' % (self.secname, self.connections)

class SchemaConnectionSection(Section):
	sectype = 0x3d
	secname = 'Schema/connection'
	def parse(self):
		self.symno = self._get_uint16(4)
		self.pin = self._get_uint16(8)

	def __str__(self):
		return '%s: symbol %d, pin %d' % (self.secname, self.symno, self.pin)

class BoardConnectionSection(Section):
	sectype = 0x3e
	secname = 'Board/connection'
	def parse(self):
		self.pacno = self._get_uint16(4)
		self.pin = self._get_uint16(6)

	def __str__(self):
		return '%s: package %d, pin %d' % (self.secname, self.pacno, self.pin)

class AttributeSection(Section):
	sectype = 0x42
	secname = 'Attribute'
	def parse(self):
		self.attribute = self._get_name(7, 17)
		self.symbol = self._get_name(2, 5)

	def __str__(self):
		return '%s %s on symbol %s' % (self.secname, self.attribute, self.symbol)

sections = {}
for section in [StartSection, Unknown11Section, Unknown12Section, LayerSection, XrefFormatSection, LibrarySection, DevicesSection,
		SymbolsSection, PackagesSection, SchemaSection, BoardSection, BoardNetSection, SymbolSection, PackageSection, SchemaNetSection,
		PathSection, PolygonSection, LineSection, CircleSection, RectangleSection, JunctionSection,
		HoleSection, PadSection, SmdSection, PinSection, DeviceSymbolSection, BoardPackageSection, BoardPackage2Section,
		SchemaSymbol2Section, DevicePackageSection, DeviceSection,
		SchemaSymbolSection, SchemaBusSection, DeviceConnectionsSection, SchemaConnectionSection, BoardConnectionSection,
		AttributeSection]:
	sections[section.sectype] = section

def read_layers(f):
	global con_byte, pin_bits
	"""
	The sections/whatever are 24 bytes long.
	First byte is section type. Absolutely no idea what the second byte is, it seemed to be some kind of
	further-sections-present-bit (0x00 = not present, 0x80 = is present) at first, but it clearly isn't.
	"""
	indents = []
	con_byte = None
	pin_bits = None
	while True:
		data = f.read(4)
		if not data:
			break
		# Some kind of sentinel?
		if data == '\x13\x12\x99\x19':
			break
		data += f.read(20)

		indents = [indent - 1 for indent in indents if indent > 0]
		indent = '  ' * len(indents)

		sectype = ord(data[0])
		section_cls = sections.get(sectype)
		if not section_cls:
			dump_hex_ascii(data)

		if section_cls:
			section = section_cls(data)
			indents.append(sum(section.subsec_counts))
			if sectype == 0x10:
				end_offset = section.numsecs * 24
				init_names(f, end_offset)
			elif sectype == 0x37:
				con_byte = section.con_byte
				pin_bits = section.pin_bits
			section.hexdump()
			print indent + '- ' + str(section)
		elif data[0] in ('\x31', '\x35', '\x34', '\x33', '\x41'):
			font, layer, x, y, hs, xxx, angle = struct.unpack('<BBiiHHH', data[2:18])
			font = 'vector proportional fixed'.split()[font]
			ratio = (xxx >> 2) & 0x1f
			# angle & 0x4000 => spin, no idea what that does though..
			if data[0] == '\x31':
				angle = 360 * (angle & 0xfff) / 4096.
			else:
				angle = '0 90 180 270'.split()[(angle & 0x0c00) >> 10]
			if data[0] == '\x31':
				extra = ', text ' + get_name(data[18:])
			elif data[0] == '\x41':
				extra = ', name ' + get_name(data[18:])
			else:
				extra = ''
			title = {'\x31': 'Text', '\x35': 'Smashed value', '\x34': 'Smashed name', '\x33': 'Net/bus label', '\x41': 'Attribute'}[data[0]]
			print indent + '- %s at (%f", %f") size %f", angle %s, layer %d, ratio %d%%, font %s%s' % (title, u2in(x), u2in(y), u2in(hs*2), angle, layer, ratio, font, extra)
		else:
			raise ValueError, 'Unknown section type'

	dump_hex_ascii(data)
	assert data == '\x13\x12\x99\x19'

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
	if name[0] != '\x7f':
		return '\x1b[32m' + repr(name.rstrip('\x00')) + '\x1b[m'
	return '\x1b[31m' + repr(get_next_name()) + '\x1b[m'

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

with file(sys.argv[1]) as f:
	#data = f.read(6*16)
	#print ''.join('%02x' % (ord(byte),) for byte in data)

	read_layers(f)
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

