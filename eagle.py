import sys
import struct

def dump_hex_ascii(data):
	print ' '.join('%02x' % (ord(byte),) for byte in data), ''.join((byte if 32 <= ord(byte) < 127 else '.') for byte in data)

def dump_dec_hex_ascii(data):
		print ' '.join('%03d' % (ord(byte),) for byte in data)
		print ' '.join(' %02x' % (ord(byte),) for byte in data)
		print ' '.join(' %s ' % (byte if 32 <= ord(byte) <= 127 else '.',) for byte in data)
		print

def read_layers(f):
	while True:
		data = f.read(4)
		if not data:
			break
		# Some kind of sentinel?
		if data == '\x13\x12\x99\x19':
			break
		# All values before the sentinel have zero in the second byte (except untiled, it has 128)
		if data[1] != '\x00' and (data[0] not in '\x15\x17\x18\x19\x37' or data[1] != '\x80'):
			break
		data += f.read(20)
		if data[0] in '\x15\x17\x18\x19' and data[1] == '\x80':
			assert data[15:] == '\x00untitled'

		#0x13 = layer
		#0x1d = symbol
		#0x1e = package
		#0x37 = device
		#0x36 = ???
		if data[0] == '\x13':
			c1, c2, flags, layer, opposite_layer, fill, color = struct.unpack('BBBBBBB', data[:7])
			name = data[15:].strip('\x00')
			assert c1 == 0x13
			assert c2 == 0x00
			assert data[7:15] == 8*'\x00'
			side = 'bottom' if flags & 0x10 else 'top'
			visible = {3: 0, 13: 0, 14: 1, 15: 1}[flags & (~0x10)]
			print 'Layer: fill=%d, color=%d, name=%s, layer=%d, other=%d, side=%s, unknown_flags=%d, visible=%d' % (fill, color, name, layer, opposite_layer, side, flags, visible)
		else:
			dump_hex_ascii(data)

	dump_hex_ascii(data)
	assert data == '\x13\x12\x99\x19'

def read_name_array(f):
	size = struct.unpack('<I', f.read(4))[0]
	print size, f.read(size).split('\x00')

with file(sys.argv[1]) as f:
	data = f.read(6*16)
	#print ''.join('%02x' % (ord(byte),) for byte in data)

	read_layers(f)
	read_name_array(f)
	dump_hex_ascii(f.read())

