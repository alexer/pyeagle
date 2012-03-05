import sys
import struct

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
	First byte is section type.
	Second byte is some kind of further-sections-present-bit: (0x00 = not present, 0x80 = is present)
	- 10/15: any symbols/packages/devices present at all?
	- 17: devices present
	- 18: symbols present
	- 19: packages present

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
		elif data[0] == '\x22':
			layer, x1, y1, x2, y2, hw = struct.unpack('<bIIIII', data[3:])
			c = struct.unpack('<I', data[7:20:4])[0]
			x1, y1, x2, y2 = [val & 0xffffff for val in (x1, y1, x2, y2)]
			print '- Line from (%f", %f") to (%f", %f"), width %f", layer %d' % (u2in(x1), u2in(y1), u2in(x2), u2in(y2), u2in(hw*2), layer)
			x3, y3 = (x1+x2)/2., (y1+y2)/2.
			if x2-x1 < y2-y1:
				cx = c
				cy = (x3-cx)*(x2-x1)/float(y2-y1)+y3
			else:
				cy = c
				cx = (y3-cy)*(y2-y1)/float(x2-x1)+x3
			print 'Arc center at:', cx/2.54, cy/2.54
			dump_hex_ascii(data[7::4])
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

