import pygtk
pygtk.require('2.0')
import gtk, gobject, cairo
from gtk import gdk

class CairoGTK(gtk.DrawingArea):
	# Draw in response to an expose-event
	__gsignals__ = {'expose-event': 'override'}
	xpol = 1
	ypol = 1
	def __init__(self, model):
		gtk.DrawingArea.__init__(self)

		self.set_model(model)

		self.connect("button_press_event", self._mouseButton)
		self.connect("button_release_event", self._mouseButton)
		#self.connect("motion_notify_event", self._mouseMotion)
		self.connect("scroll_event", self._mouseScroll)

		self.set_events(self.get_events() | gdk.BUTTON_PRESS_MASK | gdk.BUTTON_RELEASE_MASK)#|gdk.POINTER_MOTION_MASK|gdk.POINTER_MOTION_HINT_MASK)

	def set_model(self, model):
		self.model = model

		self.modelbounds = self.model.get_size()
		(self.minx, self.miny), (self.maxx, self.maxy) = self.modelbounds

		self.modelsize = (self.maxx - self.minx, self.maxy - self.miny)
		self.modelwidth, self.modelheight = self.modelsize

		self.xpos = -(self.minx if self.xpol > 0 else self.maxx)
		self.ypos = -(self.miny if self.ypol > 0 else self.maxy)
		self.zoomscale = 1

	def zoom(self, zamt, center):
		cr = self.window.cairo_create()

		self.zoomscale *= zamt

		self._reset_ctm(cr)
		old_pos = cr.device_to_user(*center)
		self._rescale()
		self._reset_ctm(cr)
		new_pos = cr.device_to_user(*center)

		self.xpos += new_pos[0] - old_pos[0]
		self.ypos += new_pos[1] - old_pos[1]

		self.redraw()

	def pan(self, (xamt, yamt)):
		cr = self.window.cairo_create()
		self._reset_ctm(cr)
		xamt2, yamt2 = cr.device_to_user_distance(xamt, yamt)
		self.xpos, self.ypos = (self.xpos + xamt2, self.ypos + yamt2)

		self.redraw()

	def _mouseButton(self, widget, event):
		if event.button == 1:
			if event.type == gdk.BUTTON_PRESS:
				self.click = event.x, event.y
			elif event.type == gdk.BUTTON_RELEASE:
				rel = (event.x - self.click[0], event.y - self.click[1])
				self.click = None
				self.pan(rel)

	def _mouseScroll(self, widget, event):
		zamt = 0.5 if (event.direction == gdk.SCROLL_UP) else 2

		self.zoom(zamt, (event.x, event.y))

	def _reshape(self):
		self.size = self.window.get_size()
		self.width, self.height = self.size

		self._rescale()

	def _get_scale(self, src, dst):
		(sw, sh) = src
		(dw, dh) = dst
		return min(float(dw) / sw, float(dh) / sh)

	def _rescale(self):
		self.modelscale = self._get_scale(self.modelsize, self.size)
		self.scale = self.modelscale * self.zoomscale

	def _reset_ctm(self, cr):
		cr.identity_matrix()
		cr.scale(self.xpol * self.scale, self.ypol * self.scale)
		cr.translate(self.xpos, self.ypos)

	def do_expose_event(self, event):
		if self.window.get_size() != self.size:
			self._reshape()

		self.draw(event.area.x, event.area.y, event.area.width, event.area.height)

	def redraw(self):
		self.draw(0, 0, *self.size)

	def draw(self, x, y, w, h):
		cr = self.window.cairo_create()

		# Restrict Cairo to the exposed area; avoid extra work
		cr.rectangle(x, y, w, h)
		cr.clip()

		# Fill the background with black
		cr.set_source_rgb(0.0, 0.0, 0.0)
		cr.rectangle(x, y, w, h)
		cr.fill()

		# Initialize coordinate transformations (panning, zooming)
		self._reset_ctm(cr)

		self.model.draw(cr)

class BaseDrawing:
	def get_size(self): pass
	#def init_ctm(self, cr): pass
	def draw(self, cr): pass

