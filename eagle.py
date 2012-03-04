import sys
import struct

def dump_hex_ascii(data):
	print ' '.join('%02x' % (ord(byte),) for byte in data), ''.join((byte if 32 <= ord(byte) < 127 else '.') for byte in data)

def dump_dec_hex_ascii(data):
		print ' '.join('%03d' % (ord(byte),) for byte in data)
		print ' '.join(' %02x' % (ord(byte),) for byte in data)
		print ' '.join(' %s ' % (byte if 32 <= ord(byte) <= 127 else '.',) for byte in data)
		print

with file(sys.argv[1]) as f:
	f.read(6*16)

	while True:
		data = f.read(4)
		if not data:
			break
		# Some kind of sentinel?
		if data == '\x13\x12\x99\x19':
			break
		# All values before the sentinel have zero in the second byte (except untiled, it has 128)
		if data[1] != '\x00' and (data[0] not in '\x15\x18' or data[1] != '\x80'):
			break
		data += f.read(20)
		if data[0] in '\x15\x18' and data[1] == '\x80':
			assert data[15:] == '\x00untitled'

		if data[0] == '\x13':
			c1, c2, flags, layer, opposite_layer, xxx2, xxx3 = struct.unpack('BBBBBBB', data[:7])
			assert c1 == 0x13
			assert c2 == 0x00
			assert data[7:15] == 8*'\x00'
			side = 'bottom' if flags & 0x10 else 'top'
			flags &= ~0x10
			print 'Layer: side=%s, layer=%d, other=%d, xxx1=%d, xxx2=%d, xxx3=%d, name=%s' % (side, layer, opposite_layer, flags, xxx2, xxx3, data[15:].strip('\x00'))
		else:
			dump_hex_ascii(data)

	assert data == '\x13\x12\x99\x19'
	size = struct.unpack('<I', f.read(4))[0]
	print size, f.read(size).split('\x00')
	dump_hex_ascii(f.read())

