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

# Values are in tenths of a micrometre
u2mm = lambda val: val/10/1000
u2in = lambda val: val/2.54/100/1000

def read_layers(f):
	"""
	The sections/whatever are 24 bytes long.
	First byte is section type. Absolutely no idea what the second byte is, it seemed to be some kind of
	further-sections-present-bit (0x00 = not present, 0x80 = is present) at first, but it clearly isn't.

	Type 15: devices/symbols/packages
	- contains 3 4-byte fields, each of which contains the number of entries in the next sections
	Type 17: devices
	- contains 2 4-byte fields, first is total number of descendants, second is number of direct children (i guess)
	Type 18: symbols
	- contains 2 4-byte fields, which are probably the same as above
	Type 19: packages
	"""
	while True:
		data = f.read(4)
		if not data:
			break
		# Some kind of sentinel?
		if data == '\x13\x12\x99\x19':
			break
		# All values before the sentinel have zero in the second byte (except untiled, it has 128)
		#if data[1] not in ('\x00', '\x80', '\x08'):
		#	break
		data += f.read(20)
		#if data[0] in '\x15\x17\x18\x19' and data[1] == '\x80':
		#	assert data[15:] == '\x00untitled'

		dump_hex_ascii(data)

		#0x13 = layer
		#0x1d = symbol
		#0x1e = package
		#0x37 = device
		#0x36 = ???
		if False:#data[0] == '\x13':
			c1, c2, flags, layer, opposite_layer, fill, color = struct.unpack('BBBBBBB', data[:7])
			name = data[15:].strip('\x00')
			assert c1 == 0x13
			assert c2 == 0x00
			assert data[7:15] == 8*'\x00'
			side = 'bottom' if flags & 0x10 else 'top'
			visible = {3: 0, 13: 0, 14: 1, 15: 1}[flags & (~0x10)]
			print '- Layer: fill=%d, color=%d, name=%s, layer=%d, other=%d, side=%s, unknown_flags=%d, visible=%d' % (fill, color, name, layer, opposite_layer, side, flags, visible)
		elif data[0] == '\x22': # Line or arc
			# 4th byte is layer
			# next 4 4-byte fields each contain 3 bytes of x1, y1, x2, y2 respectively
			# for arcs, the 4th bytes of these fields combine to a 4-byte field whichs contains 3 bytes of c
			# c is the x or y coordinate of the arc center point, depending on the slope of the line
			# the 4th byte of c (or the 20th byte) contains flags which tell which of the fields are negative (two's complement)
			# then comes two bytes, which contain the width of the line divided by two
			# next (second to last) byte contains some flags about the style of the arc

			layer, hw, stflags, arctype = struct.unpack('<bHBB', data[3] + data[20:24])

			assert stflags & 0xcc == 0, 'Unknown bits set in style flags: ' + hex(stflags & 0xcc)
			assert arctype in (0x00, 0x81, 0x7e, 0x7f), 'Unknown arc type: ' + hex(arctype)

			# Status flags; 0x20 == positive curve value
			# Cap style and positive curve are present on bare lines too, that's probably a bug
			style = {0x00: 'continuous', 0x01: 'longdash', 0x02: 'shortdash', 0x03: 'dashdot'}[stflags & 0x03]
			cap = {0x00: 'round', 0x10: 'flat'}[stflags & 0x10]

			if not arctype:
				x1, y1, x2, y2 = struct.unpack('<iiii', data[4:20])
				print '- Line from (%f", %f") to (%f", %f"), width %f", layer %d, style %s' % (u2in(x1), u2in(y1), u2in(x2), u2in(y2), u2in(hw*2), layer, style)
			else:
				# Extend 3-byte coordinate fields to 4 bytes, taking the negative-flags into account
				negflags = ord(data[19])
				ext = ['\xff' if negflags & (1 << i) else '\x00' for i in range(5)]
				xydata = data[7:16:4] + ext[0] + data[4:7] + ext[1] + data[8:11] + ext[2] + data[12:15] + ext[3] + data[16:19] + ext[4]
				c, x1, y1, x2, y2 = struct.unpack('<iiiii', xydata)

				assert negflags & 0xe0 == 0, 'Unknown bits set in negation flags: ' + hex(negflags & 0xe0)

				x3, y3 = (x1+x2)/2., (y1+y2)/2.
				if abs(x2-x1) < abs(y2-y1):
					cx = c
					cy = (x3-cx)*(x2-x1)/float(y2-y1)+y3
					xst, yst = '', '?'
				else:
					cy = c
					cx = (y3-cy)*(y2-y1)/float(x2-x1)+x3
					xst, yst = '?', ''
				print '- Arc from (%f", %f") to (%f", %f"), center at (%f"%s, %f"%s), width %f", layer %d, style %s, cap %s' % (u2in(x1), u2in(y1), u2in(x2), u2in(y2), u2in(cx), xst, u2in(cy), yst, u2in(hw*2), layer, style, cap)
			dump_hex(data[1:3])
			dump_hex(data[7::4])
		elif data[0] == '\x25':
			layer, x1, y1, r1, r2, hw = struct.unpack('<biiiiI', data[3:])
			assert r1 == r2
			print '- Circle at (%f", %f"), radius %f", width %f", layer %d' % (u2in(x1), u2in(y1), u2in(r1), u2in(hw*2), layer)

	dump_hex_ascii(data)
	assert data == '\x13\x12\x99\x19'

def read_name_array(f):
	size = struct.unpack('<I', f.read(4))[0]
	print size, f.read(size).split('\x00')

with file(sys.argv[1]) as f:
	#data = f.read(6*16)
	#print ''.join('%02x' % (ord(byte),) for byte in data)

	read_layers(f)
	read_name_array(f)
	dump_hex_ascii(f.read())

