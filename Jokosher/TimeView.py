#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	TimeView.py
#	
#	This module holds and updates the gtk.Label which displays
#	the current time position.
#
#-------------------------------------------------------------------------------

import gtk

#=========================================================================

class TimeView(gtk.EventBox):
	"""
	This class updates the time label which displays the time position of a loaded project.
	"""

	__gtype_name__ = 'TimeView'

	#_____________________________________________________________________

	def __init__(self, project):
		"""
		Creates a new instance of TimeView
		
		Parameters:
			project -- reference to Project (Project.py)
		"""
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
		"""
		This method will update the time label
		"""		
		transport = self.project.transport
		formatString = "<span font_desc='Sans Bold 15'>%s</span>"
		if transport.mode == transport.MODE_BARS_BEATS:
			bars, beats, ticks = transport.GetPositionAsBarsAndBeats()
			self.timeViewLabel.set_markup(formatString%("%05d:%d:%03d"%(bars, beats, ticks)))
			
		elif transport.mode == transport.MODE_HOURS_MINS_SECS:
			hours, mins, secs, millis = transport.GetPositionAsHoursMinutesSeconds()
			self.timeViewLabel.set_markup(formatString%("%01d:%02d:%02d:%03d"%(hours, mins, secs, millis)))
			
	#_____________________________________________________________________
	
	def OnStateChanged(self, obj, change=None, *extra):
		"""
		This method is called when there is a change to be made
		
		Parameters:
			obj -- an object to inform when this method is called.
			change -- the change which has occured.
			extra -- the extra parameters to be passed.
		"""
		self.UpdateTime()
	
	#_____________________________________________________________________

	def OnClick(self, widget, event):
		"""
		This method is called when the label is double clicked
		It will then change the time label to represent either MODE_HOURS_MINS_SECS or MODE_BARS_BEATS.
		MODE_HOURS_MINS_SECS - time in seconds, minutes and hours.
		MODE_BARS_BEATS - time in how many beats are in each bar.
		
		Parameters:
			widget -- reserved for GTK callbacks, don't use it explicitly.
			event -- reserved for GTK callbacks, don't use it explicitly.	
		"""
		if event.type == gtk.gdk._2BUTTON_PRESS:
			transport = self.project.transport
			if transport.mode == transport.MODE_BARS_BEATS:
				self.project.SetTransportMode(transport.MODE_HOURS_MINS_SECS)
			else:
				self.project.SetTransportMode(transport.MODE_BARS_BEATS)
			
	#_____________________________________________________________________
					
#=========================================================================
