#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	VUWidget.py
#	
#	This module draws the gradient volume levels and is used by
#	MixerStrip.py to show the volume levels in Jokosher's mix view.
#
#-------------------------------------------------------------------------------

import pygtk
pygtk.require("2.0")
import gtk
import cairo

import gettext
_ = gettext.gettext

#=========================================================================

class VUWidget(gtk.DrawingArea):
	
	__gtype_name__ = 'VUWidget'
	
	BAR_WIDTH = 20
	
	#_____________________________________________________________________
	
	def __init__(self, mixerstrip, mainview):
		gtk.DrawingArea.__init__(self)
		self.mixerstrip = mixerstrip
		self.mainview = mainview
		
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
		self.message_id = None
		
		self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
		
		
	#_____________________________________________________________________
		
	def OnMouseDown(self, widget, mouse):
		rect = self.get_allocation()
		pos = (rect.height-self.BAR_WIDTH) * (1. - self.mixerstrip.GetVolume()) + (self.BAR_WIDTH/2)
		if mouse.y > pos - (self.BAR_WIDTH / 2) and mouse.y < pos + (self.BAR_WIDTH / 2):
			self.fader_active = True
	
	#_____________________________________________________________________
	
	def OnMouseMove(self, widget, mouse):
		if not self.message_id:
			self.message_id = self.mainview.SetStatusBar(_("<b>Drag</b> the <b>slider</b> to alter volume levels"))
		rect = self.get_allocation()
		pos = (rect.height-self.BAR_WIDTH) * (1. - self.mixerstrip.GetVolume()) + (self.BAR_WIDTH/2)
		if mouse.y > pos - (self.BAR_WIDTH / 2) and mouse.y < pos + (self.BAR_WIDTH / 2):
			self.fader_hover = True
		else:
			self.fader_hover = False
			
		if self.fader_active:
			v = 1. - ((mouse.y - self.BAR_WIDTH/2)
						   /  (rect.height-self.BAR_WIDTH))
			v  = max(v, 0.)
			v  = min(v, 1.)
			self.mixerstrip.SetVolume(v)
			self.queue_draw()
	
	#_____________________________________________________________________
	
	def OnMouseUp(self, widget, mouse):
		self.fader_active = False
		
	#_____________________________________________________________________
	
	def OnMouseLeave(self, widget, mouse):
		if self.message_id:
			self.mainview.ClearStatusBar(self.message_id)
			self.message_id = None

	#_____________________________________________________________________

	def OnSizeChanged(self, obj, evt):
		""" Called when the widget's size changes
		"""
		if self.allocation.width != self.source.get_width() or self.allocation.height != self.source.get_height():
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
		ctx.rectangle(0, rect.height * (1. - self.mixerstrip.GetLevel()), rect.width, rect.height)
		ctx.clip()
		ctx.set_source_surface(self.source, 0, 0)	
		ctx.paint()

		# Reset the clip region
		ctx.reset_clip()
		
		# Draw the current volume level bar, with highlight if appropriate
		vpos = (rect.height-self.BAR_WIDTH) * (1. - self.mixerstrip.GetVolume()) + (self.BAR_WIDTH/2)
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
		#HACK: workaround because strings are frozen
		#make sure the string does not exceed 12 characters
		vol_string = _("Volume: %.2f")
		vol_word = vol_string[:-5]
		if len(vol_word) > 7:
			#we can cut at 5 here because "..." takes less than other characters
			vol_word = vol_word[:5] + "..."
		ctx.show_text("%s %.2f" % (vol_word, self.mixerstrip.GetVolume()))

		return False
		
	#_____________________________________________________________________
	
	def do_size_request(self, requisition):
		requisition.width = 100
		requisition.height = -1
		
	#_____________________________________________________________________
	
	
#=========================================================================

	
