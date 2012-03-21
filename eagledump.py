import sys
import eagle

if __name__ == '__main__':
	fname = sys.argv[1]

	with file(fname) as f:
		eagle.EagleFile(f, ['hexdump', 'dump'])

