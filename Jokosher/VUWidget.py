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

import gettext, locale
_ = gettext.gettext

#=========================================================================

class VUWidget(gtk.DrawingArea):
	"""
	Draws the gradient volume levels and is used by MixerStrip.py
	to show the volume levels in Jokosher's mix view.
	"""
	
	""" GTK widget name """
	__gtype_name__ = 'VUWidget'
	
	""" Height, in pixels, for the volume handle """
	_VH_HEIGHT = 25
	""" Space between the edge of the volume handle and the edge of the VU meter"""
	_VH_PADDING = 20
	_VH_BORDER_WIDTH = 5
	""" the highest value allowed to be set for the volume (lowest is always zero)"""
	_MAX_VOLUME = 2
	
	""" Both text height and width below depend on the font size. 
	If you change the font size, figure out the new pixel sizes and update these values."""
	_FONT_SIZE = 18
	_TEXT_HEIGHT = 13
	_TEXT_WIDTH = 37
	
	"""
	Various color configurations:
	   ORGBA = Offset, Red, Green, Blue, Alpha
	   RGBA = Red, Green, Blue, Alpha
	   RGB = Red, Green, Blue
	"""
	_VH_ACTIVE_RGBA = (1., 1., 1., 1.)
	_VH_INACTIVE_RGBA = (1., 1., 1., 0.75)
	_VH_BORDER_RGBA = (0.5, 0., 0., 0.75)
	_BACKGROUND_RGB = (0., 0., 0.)
	_LEVEL_GRADIENT_BOTTOM_ORGBA = (1, 0, 1, 0, 1)
	_LEVEL_GRADIENT_TOP_ORGBA = (0, 1, 0, 0, 1)
	_TEXT_RGBA = (0., 0., 0., 1.)
	
	#_____________________________________________________________________
	
	def __init__(self, mixerstrip, mainview):
		"""
		Creates a new instance of VUWidget.
		
		Parameters:
			mixerstrip -- TODO
			mainview -- the main Jokosher window (JokosherApp).
		"""
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
		"""
		If the fader widget is clicked, activates it.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.__YPosOverVolumeHandle(mouse.y):
			self.fader_active = True
	
	#_____________________________________________________________________
	
	def OnMouseMove(self, widget, mouse):
		"""
		Displays a helper message in the StatusBar and sets the volume
		according to the position of the fader widget.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if not self.message_id:
			self.message_id = self.mainview.SetStatusBar(_("<b>Drag</b> the <b>slider</b> to alter volume levels"))
		
		self.fader_hover = self.__YPosOverVolumeHandle(mouse.y)
			
		if self.fader_active:
			rect = self.get_allocation()
			volume = 1. - ((mouse.y - self._VH_HEIGHT/2) /  (rect.height-self._VH_HEIGHT))
			volume  = max(volume, 0.)
			volume  = min(volume, 1.)
			self.mixerstrip.SetVolume(volume * self._MAX_VOLUME)
			self.queue_draw()
	
	#_____________________________________________________________________
	
	def OnMouseUp(self, widget, mouse):
		"""
		Deactivates the fader widget.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.fader_active = False
		
	#_____________________________________________________________________
	
	def OnMouseLeave(self, widget, mouse):
		"""
		Clears the StatusBar helper message.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			mouse -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.message_id:
			self.mainview.ClearStatusBar(self.message_id)
			self.message_id = None

	#_____________________________________________________________________

	def OnSizeChanged(self, obj, evt):
		"""
		Toggles a redraw of the VUWidget if needed.
		
		Parameters:
			obj -- reserved for Cairo callbacks, don't use it explicitly. *CHECK*
			evt --reserved for Cairo callbacks, don't use it explicitly. *CHECK*
		"""
		if self.allocation.width != self.source.get_width() or self.allocation.height != self.source.get_height():
			self.source = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.allocation.width, self.allocation.height)
			self.GenerateBackground()

	#_____________________________________________________________________

	def GenerateBackground(self):
		"""
		Renders the gradient strip for the VU meter background to speed up drawing.
		"""
		
		rect = self.get_allocation()

		ctx = cairo.Context(self.source)
		ctx.set_line_width(2)
		ctx.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
		
		# Create our green to red gradient
		pat = cairo.LinearGradient(0.0, 0.0, 0, rect.height)
		pat.add_color_stop_rgba(*self._LEVEL_GRADIENT_BOTTOM_ORGBA)
		pat.add_color_stop_rgba(*self._LEVEL_GRADIENT_TOP_ORGBA)

		# Fill the volume bar
		ctx.rectangle(0, 0, rect.width, rect.height)
		ctx.set_source(pat)
		ctx.fill()
	#_____________________________________________________________________

	def OnDraw(self, widget, event):
		"""
		Handles the GTK paint event.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.
			
		Returns:
			False -- TODO
		"""
		
		ctx = widget.window.cairo_create()
		
		rect = self.get_allocation()

		# Fill a black background		
		ctx.rectangle(0, 0, rect.width, rect.height)
		ctx.set_source_rgb(*self._BACKGROUND_RGB)
		ctx.fill()

		# Blit across the cached gradient backgound
		ctx.rectangle(0, rect.height * (1. - self.mixerstrip.GetLevel()), rect.width, rect.height)
		ctx.clip()
		ctx.set_source_surface(self.source, 0, 0)	
		ctx.paint()

		# Reset the clip region
		ctx.reset_clip()
		
		# Draw the current volume level bar, with highlight if appropriate
		vpos = self.__GetVolumeHandleYPos()
		if self.fader_active:
			ctx.set_source_rgba(*self._VH_BORDER_RGBA)
			ctx.set_line_width(self._VH_HEIGHT + self._VH_BORDER_WIDTH)
			ctx.set_line_cap(cairo.LINE_CAP_ROUND)
			ctx.move_to(self._VH_PADDING, vpos)
			ctx.line_to(rect.width - self._VH_PADDING, vpos)
			ctx.stroke()
			ctx.set_source_rgba(*self._VH_ACTIVE_RGBA)
		elif self.fader_hover:
			ctx.set_source_rgba(*self._VH_ACTIVE_RGBA)
		else:
			ctx.set_source_rgba(*self._VH_INACTIVE_RGBA)

		ctx.set_line_cap(cairo.LINE_CAP_ROUND)
		ctx.set_line_width(self._VH_HEIGHT)
		ctx.move_to(self._VH_PADDING, vpos)
		ctx.line_to(rect.width - self._VH_PADDING, vpos)
		ctx.stroke()

		# Draw the volume level in the bar
		ctx.set_source_rgba(*self._TEXT_RGBA)
		textYOffset = (self._VH_HEIGHT - self._TEXT_HEIGHT) / 2
		textXOffset = ((rect.width - (2 * self._VH_PADDING) - self._TEXT_WIDTH) / 2) + self._VH_PADDING
		ctx.move_to(textXOffset, vpos + textYOffset)
		ctx.set_font_size(self._FONT_SIZE)
		localizedText = locale.format("%.2f", self.mixerstrip.GetVolume())
		ctx.show_text(localizedText)

		return False
		
	#_____________________________________________________________________
	
	def do_size_request(self, requisition):
		"""
		TODO
		
		Parameters:
			requisition -- TODO
		"""
		requisition.width = 100
		requisition.height = -1
		
	#_____________________________________________________________________
	
	def Destroy(self):
		"""
		Deletes the cairo.ImageSurface and then calls the class destructor.
		"""
		del self.source
		self.destroy()
	
	#_____________________________________________________________________
	
	def __GetVolumeHandleYPos(self):
		"""
		Calculates the verical position of the *center* of the volume handle
		based on the instrument's current volume, and the size of the volume
		handle itself (so that is doesn't go off the screen at the top or bottom.
		
		Returns:
			the Y value in pixels of the center of the volume handle.
		"""
		height = self.get_allocation().height
		totalPixelHeight = height - self._VH_HEIGHT
		inverseVolume = (self._MAX_VOLUME - self.mixerstrip.GetVolume()) / self._MAX_VOLUME
		offset = self._VH_HEIGHT / 2
		
		return totalPixelHeight * inverseVolume + offset
	
	#_____________________________________________________________________
	
	def __YPosOverVolumeHandle(self, yPos):
		"""
		Calculates if the given vertical position is located over top of the volume handle.
		
		Parameters:
			yPos -- the vertical position in pixels
		
		Returns:
			True if the value is over the volume handle; False otherwise.
		"""
		handleYPos = self.__GetVolumeHandleYPos()
		halfHandle = self._VH_HEIGHT / 2
		return handleYPos - halfHandle < yPos < handleYPos + halfHandle
	
	#_____________________________________________________________________
#=========================================================================
