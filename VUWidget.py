import pygtk
pygtk.require("2.0")
import gtk
import cairo

#=========================================================================

class VUWidget(gtk.DrawingArea):
	
	__gtype_name__ = 'VUWidget'
	
	BAR_WIDTH = 20
	
	#_____________________________________________________________________
	
	def __init__(self, instrument):
		gtk.DrawingArea.__init__(self)
		self.instrument = instrument
		
		self.set_events(	gtk.gdk.POINTER_MOTION_MASK |
							gtk.gdk.BUTTON_RELEASE_MASK |
							gtk.gdk.BUTTON_PRESS_MASK |
							gtk.gdk.LEAVE_NOTIFY_MASK )
		
		self.connect("button-press-event", self.OnMouseDown)
		self.connect("button-release-event", self.OnMouseUp)
		self.connect("motion_notify_event", self.OnMouseMove)
		self.connect("leave_notify_event", self.OnMouseLeave)
		self.connect("configure_event", self.OnSizeChanged)
		self.connect("expose-event", self.OnDraw)
		
		self.fader_active = False
		self.fader_hover = False
		
		self.RedrawCount = 6

		self.instrument.AddListener(self)
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
		
		
	#_____________________________________________________________________
		
	def OnMouseDown(self, widget, mouse):
		rect = self.get_allocation()
		pos = (rect.height-self.BAR_WIDTH) * (1. - self.instrument.volume) + (self.BAR_WIDTH/2)
		if mouse.y > pos - (self.BAR_WIDTH / 2) and mouse.y < pos + (self.BAR_WIDTH / 2):
			self.fader_active = True
	
	#_____________________________________________________________________
	
	def OnMouseMove(self, widget, mouse):
		rect = self.get_allocation()
		pos = (rect.height-self.BAR_WIDTH) * (1. - self.instrument.volume) + (self.BAR_WIDTH/2)
		if mouse.y > pos - (self.BAR_WIDTH / 2) and mouse.y < pos + (self.BAR_WIDTH / 2):
			self.fader_hover = True
		else:
			self.fader_hover = False
			
		if self.fader_active:
			v = 1. - ((mouse.y - self.BAR_WIDTH/2)
						   /  (rect.height-self.BAR_WIDTH))
			v  = max(v, 0.)
			v  = min(v, 1.)
			self.instrument.SetVolume(v)
			self.queue_draw()
	
	#_____________________________________________________________________
	
	def OnMouseUp(self, widget, mouse):
		self.fader_active = False
		
	#_____________________________________________________________________
	
	def OnMouseLeave(self, widget, mouse):
		pass

	#_____________________________________________________________________

	def OnSizeChanged(self, obj, evt):
		""" Called when the widget's size changes
		"""
		if self.allocation.width != self.source.get_width() or self.allocation.height != self.source.get_height():
			#print self.allocation.width, self.allocation.height
			self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
			self.GenerateBackground()

	#_____________________________________________________________________

	def GenerateBackground(self):
		""" Renders the gradient strip for the VU meter background to speed up
			drawing.
		"""
		
		rect = self.get_allocation()

		ctx = cairo.Context(self.source)
		ctx.set_line_width(2)
		ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
		
		# Create our green to red gradient
		pat = cairo.LinearGradient(0.0, 0.0, 0, rect.height)
		pat.add_color_stop_rgba(1, 0, 1, 0, 1)
		pat.add_color_stop_rgba(0, 1, 0, 0, 1)

		# Fill the volume bar
		ctx.rectangle(0, 0, rect.width, rect.height)
		ctx.set_source(pat)
		ctx.fill()
	#_____________________________________________________________________

	def OnDraw(self, widget, event):
		""" Handles the GTK paint event.
		"""

		ctx = widget.window.cairo_create()
		
		rect = self.get_allocation()

		# Fill a black background		
		ctx.rectangle(0, 0, rect.width, rect.height)
		ctx.set_source_rgb(0., 0., 0.)
		ctx.fill()

		# Blit across the cached gradient backgound
		ctx.rectangle(0, rect.height * (1. - self.instrument.level), rect.width, rect.height)
		ctx.clip()
		ctx.set_source_surface(self.source, 0, 0)	
		ctx.paint()

		# Reset the clip region
		ctx.reset_clip()
		
		# Draw the current volume level bar, with highlight if appropriate
		vpos = (rect.height-self.BAR_WIDTH) * (1. - self.instrument.volume) + (self.BAR_WIDTH/2)
		if self.fader_active:
			ctx.set_source_rgba(0.5, 0., 0., 0.75)
			ctx.set_line_width(self.BAR_WIDTH + 5)
			ctx.set_line_cap(cairo.LINE_CAP_ROUND)
			ctx.move_to(20, vpos)
			ctx.line_to(rect.width - 20, vpos)
			ctx.stroke()
			ctx.set_source_rgba(1., 1., 1., 1.)
		elif self.fader_hover:
			ctx.set_source_rgba(1., 1., 1., 1.)
		else:
			ctx.set_source_rgba(1., 1., 1., 0.75)

		ctx.set_line_cap(cairo.LINE_CAP_ROUND)
		ctx.set_line_width(self.BAR_WIDTH)
		ctx.move_to(20, vpos)
		ctx.line_to(rect.width - 20, vpos)
		ctx.stroke()

		# Draw the volume level in the bar
		ctx.set_source_rgba(0., 0., 0., 1.)
		ctx.move_to(18, vpos + 3)
		ctx.show_text("Volume: %.2f"%self.instrument.volume)

		return False
		
	#_____________________________________________________________________
	
	def do_size_request(self, requisition):
		requisition.width = 100
		requisition.height = -1
		
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj):
		self.RedrawCount += 1
		if self.RedrawCount > 6:
			self.queue_draw()
			self.RedrawCount = 0
		
	#_____________________________________________________________________
	
#=========================================================================

	
