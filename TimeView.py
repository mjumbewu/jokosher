
import gtk
import pango

#=========================================================================

class TimeView(gtk.EventBox):

	__gtype_name__ = 'TimeView'

	#_____________________________________________________________________

	def __init__(self, project):
		gtk.EventBox.__init__(self)
		self.set_events(gtk.gdk.BUTTON_PRESS_MASK)
		self.connect("button_press_event", self.OnClick)
		self.timeViewLabel = gtk.Label()
		self.add(self.timeViewLabel)
		self.project = project
		self.project.transport.AddListener(self)
		self.UpdateTime()
		
	#_____________________________________________________________________
		
	def UpdateTime(self):		
		transport = self.project.transport
		formatString = "<span font_desc='Sans Bold 15'>%s</span>"
		if transport.mode == transport.MODE_BARS_BEATS:
			bars, beats, ticks = transport.GetPositionAsBarsAndBeats()
			self.timeViewLabel.set_markup(formatString%("%05d:%d:%03d"%(bars, beats, ticks)))
			
		elif transport.mode == transport.MODE_HOURS_MINS_SECS:
			hours, mins, secs, millis = transport.GetPositionAsHoursMinutesSeconds()
			self.timeViewLabel.set_markup(formatString%("%01d:%02d:%02d:%03d"%(hours, mins, secs, millis)))
			
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj):
		self.UpdateTime()
	
	#_____________________________________________________________________

	def OnClick(self, widget, event):
		if event.type == gtk.gdk._2BUTTON_PRESS:
			transport = self.project.transport
			if transport.mode == transport.MODE_BARS_BEATS:
				transport.SetMode(transport.MODE_HOURS_MINS_SECS)
			else:
				transport.SetMode(transport.MODE_BARS_BEATS)
			
	#_____________________________________________________________________
					
#=========================================================================
