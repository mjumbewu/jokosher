
import gtk
import gobject
import cairo

#=========================================================================

class EventLaneHSeparator(gtk.HSeparator):
	def __init__(self, project, transport):
		gtk.HSeparator.__init__(self)
		
		self.x_pos = 0
		self.prev_x_pos = 0
		transport.connect("position", self.OnTransportPosition)
		project.connect("view-start", self.OnProjectViewStart)
	
	def OnProjectViewStart(self, project):
		self.OnTransportPosition(project.transport)
	
	def OnTransportPosition(self, transportManager, extraString=None):
		self.x_pos = transportManager.GetPixelPosition()
		
		a = self.get_allocation()
		
		self.queue_draw_area(a.x + self.prev_x_pos, a.y, 1, a.height)
		self.queue_draw_area(a.x + self.x_pos     , a.y, 1, a.height)
		
		self.prev_x_pos = self.x_pos
		
	def do_expose_event(self, event):
		retval = gtk.HSeparator.do_expose_event(self, event)
		
		context = self.window.cairo_create()
		
		context.set_antialias(cairo.ANTIALIAS_NONE)
		context.set_line_width(1)
		context.set_source_rgb(1, 0, 0)
		
		a = self.get_allocation()
		x = self.x_pos + a.x
		
		context.move_to(x + 0.5, a.y - 0.5)
		context.line_to(x + 0.5, a.y + a.height + 0.5)
		context.stroke()
		
		return retval
	
#=========================================================================

gobject.type_register(EventLaneHSeparator)
