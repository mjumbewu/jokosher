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
import gettext
_ = gettext.gettext

#=========================================================================

class TimeView(gtk.EventBox):
	"""
	This class updates the time label which displays the time position of a loaded project.
	"""

	""" GTK widget name """
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
		# Listen for bpm and time sig changes
		self.project.connect("bpm", self.OnProjectTime)
		self.project.connect("time-signature", self.OnProjectTime)
		# Listen for playback position and mode changes
		self.project.transport.connect("transport-mode", self.OnTransportMode)
		self.project.transport.connect("position", self.OnTransportPosition)
		
		self.UpdateTime()
		self.set_tooltip_text(_("Double click to change the time format"))
		
	#_____________________________________________________________________
		
	def UpdateTime(self):
		"""
		Updates the time label.
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
	
	def OnProjectTime(self, project):
		"""
		Callback for when the project's time related properties
		(bpm and time signature) change.
		
		Parameters:
			project -- The project instance that send the signal.
		"""
		self.UpdateTime()
	
	#_____________________________________________________________________
	
	def OnTransportMode(self, transportManager, mode):
		"""
		Callback for signal when the transport mode changes.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			mode -- the mode type that the transport changed to.
		"""
		self.UpdateTime()
	
	#_____________________________________________________________________
	
	def OnTransportPosition(self, transportManager, extraString):
		"""
		Callback for signal when the transport position changes.
		
		Parameters:
			transportManager -- the TransportManager instance that send the signal.
			extraString -- a string specifying the extra action details. i.e. "stop-action"
					means that the position changed because the user hit stop.
		"""
		self.UpdateTime()
	
	#_____________________________________________________________________

	def OnClick(self, widget, event):
		"""
		Called when the label is double clicked.
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
