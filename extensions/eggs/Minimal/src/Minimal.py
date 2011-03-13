#
#	Minimal.py
#	-----------
#	This extension allows you to replace the main Jokosher window with
#	a tiny dialog with just transport buttons and time display.
#
#-------------------------------------------------------------------------------

import Jokosher.Extension
import gtk
import pkg_resources
import time
import gobject

import gettext
_ = gettext.gettext

# used for the ToggleButton wrapper
settingButtons = False

#=========================================================================

class Minimal:
	"""
	The class implements the Minimal extension. It consists of
	a small window with just the transport buttons and the time display.
	The main Jokosher window is hidden.
	"""
	EXTENSION_NAME = "Minimal"
	EXTENSION_DESCRIPTION = "Replaces the normal Jokosher window with a tiny dialog"
	EXTENSION_VERSION = "0.11"
	
	#_____________________________________________________________________
	
	def startup(self, api):
		"""
		Called by the extension manager during Jokosher startup
		or when the extension is added via ExtensionManagerDialog.
		
		Parameters:
			api -- a reference to the Extension API
		"""
		self.API = api
		self.menu_item = self.API.add_menu_item(_("Minimal Mode"), self.OnMenuItemClick)

	#_____________________________________________________________________
	
	def shutdown(self):
		"""
		Called by the extension manager when the extension is
		disabled or deleted.
		"""
		self.menu_item.destroy()

	#_____________________________________________________________________
	
	def OnMenuItemClick(self, arg):
		"""
		GTK callback when the menu item added in startup()
		is selected.
		
		Parameters:
			arg -- set by GTK
		"""
		xmlString = pkg_resources.resource_string(__name__,"Minimal.ui")
		gtkBuilder = gtk.Builder()
		gtkBuilder.add_from_string(xmlString)
		
		self.window = gtkBuilder.get_object("MinimalDialog")
		self.API.set_window_icon(self.window)
		self.timeLabel = gtkBuilder.get_object("timeLabel")
		self.hideShowButton = gtkBuilder.get_object("hideShowButton")
		self.abButton = gtkBuilder.get_object("abButton")
		self.play = gtkBuilder.get_object("playButton")
		self.stop = gtkBuilder.get_object("stopButton")
		self.record = gtkBuilder.get_object("recordButton")
		
		signals = {
			"on_stopButton_clicked" : self.OnStop,
			"on_playButton_clicked" : self.OnPlay,
			"on_recordButton_clicked" : self.OnRecord,
			"on_abButton_clicked" : self.OnAB,
			"on_hideShowButton_clicked" : self.OnHide,
			"on_closeButton_clicked" : self.OnClose,
			"on_MinimalDialog_delete_event" : self.OnClose
		}
		
		self.abStatus = self.abStart = self.abEnd = 0
		gtkBuilder.connect_signals(signals)
		self.API.hide_main_window()
		self.mainWindowHide = True
		self.currentPosition = (-1, -1, -1, -1)
		gobject.timeout_add(40, self.UpdateTime)
		gobject.timeout_add(250, self.SyncButtons)
		self.window.set_transient_for(self.API.mainapp.window)
		self.API.add_end_of_stream_handler(self.OnEndOfStream)
		self.eosFlag = False

	#_____________________________________________________________________

	def ToggleButton(func):
		"""
		Function that wraps methods that change the toggle button states.
		This is because when the button state is changed then a new 'clicked'
		signal is emitted which we want to ignore.
		"""
		def wrapper(self, *args):
			"""
			The actual wrapper function. This will set a flag for the
			duration of the method we are actually calling preventing it
			from being called a second time whilst changing the button state.
			"""
			global settingButtons
			
			if settingButtons:
				return
			
			settingButtons = True
			result = func(self, *args)
			settingButtons = False
			
			return result
	
		#____________________________________________________________________
		
		return wrapper
	
	#____________________________________________________________________
	
	def OnStop(self, widget):
		"""
		GTK callback when the "Stop" button is clicked.
			
		Parameters:
			widget -- set by GTK
		"""
		self.API.stop()
		
	#_____________________________________________________________________
	
	@ToggleButton
	def OnPlay(self, widget):
		"""
		GTK callback when the "Play" button is clicked.
			
		Parameters:
			widget -- set by GTK
		"""
		self.API.play()
		
	#_____________________________________________________________________
	
	def OnClose(self, widget, event=None):
		"""
		GTK callback when the "Close" button is clicked or
		when the dialog closed button is pressed.
			
		Parameters:
			widget -- set by GTK
		"""
		#redisplay main window if it's hidden before quitting
		if self.mainWindowHide:
			self.API.show_main_window()
			
		self.API.remove_end_of_stream_handler(self.OnEndOfStream)
		self.window.destroy()
		
	#_____________________________________________________________________
	
	def UpdateTime(self):
		"""
		Updates the time display.
		
		Returns:
			True -- continue the timer callbacks.
		"""
		#if the window is destroyed then cancel timeout
		if not self.window.has_user_ref_count:
			return False
		
		formatString = "<span font_desc='Sans Bold 12'>%01d:%02d:%02d:%03d</span>"
		pos = self.API.get_position_as_hours_minutes_seconds()
		if pos and pos != self.currentPosition:
			self.timeLabel.set_markup(formatString % pos)
			self.currentPosition = pos
			
		return True
	
	#_____________________________________________________________________

	def OnHide(self, widget):
		"""
		GTK callback when the "Hide/restore" button is clicked.

		Parameters:
			widget -- set by GTK
		"""
		if self.mainWindowHide:
			self.API.show_main_window()
			self.mainWindowHide = False
			self.hideShowButton.set_label("_Hide")
		else:
			self.API.hide_main_window()
			self.mainWindowHide = True
			self.hideShowButton.set_label("S_how")
			
	#____________________________________________________________________	

	@ToggleButton
	def OnRecord(self, widget):
		"""
		GTK callback when the "Record" button is clicked.
		
		Parameters:
			widget -- set by GTK
		"""
		gobject.idle_add(self.ResetAB)
		self.API.record()
		
	#____________________________________________________________________	

	@ToggleButton
	def OnAB(self, widget):
		"""
		GTK callback when the "A-B" button is clicked.
		"""
		if self.abStatus == 0:
			self.abStatus = 1
			self.abButton.set_label("A-")
			self.abButton.set_active(True)
			self.abButton.set_tooltip_text(_("Select the end position for looped playback"))
			self.abStart = self.API.get_position()
		elif self.abStatus ==1:
			self.abStatus = 2
			self.abButton.set_label("A-B")
			self.abButton.set_active(True)
			self.abButton.set_tooltip_text(_("End looped playback"))
			self.abEnd = self.API.get_position()
			self.API.seek(self.abStart, self.abEnd)
		else:
			gobject.idle_add(self.ResetAB)
			self.API.stop()
		
	#____________________________________________________________________	

	def OnEndOfStream(self):
		"""
		Called when there is an end of stream signal from Jokosher.
		"""
		#set flag so we know we've stopped because of
		#end of stream
		self.eosFlag = True
		#FIXME:for some reason with the version of gstreamer I
		#currently have sometimes pressing stop doesn't actually stop
		#and the pipeline continues to loop although it does stop enough
		#for SyncButtons to call ResetAB but it will come through 
		#here again on the next eos
		if self.abStart == 0 and self.abEnd ==0:
			self.eosFlag = False
			self.API.stop()
			return
		self.API.seek(self.abStart, self.abEnd)
		self.API.play()
		
	#____________________________________________________________________	

	@ToggleButton
	def ResetAB(self):
		"""
		Resets the "A-B" button to its initial state.
		"""
		self.abStatus = self.abStart = self.abEnd = 0
		self.abButton.set_label("A-B")
		self.abButton.set_active(False)
		self.abButton.set_tooltip_text(_("Select the start position for looped playback"))
		
	#____________________________________________________________________	

	@ToggleButton
	def SyncButtons(self):
		"""
		Synchronizes transport buttons with the main
		Jokosher window transport buttons as they might 
		change independently.
		"""
		#if the window is destroyed then cancel timeout
		if not self.window.has_user_ref_count:
			return False
		
		buttonStates = self.API.get_button_states()
		for buttonName in ("play", "record", "stop"):
			toggleState = buttonStates[buttonName][0]
			button = getattr(self, buttonName)
			if not toggleState is None:
				if not button.get_active() == toggleState:
					#for a change of state of play button check eosFlag
					#if it's set and the button is coming on i.e. the loop
					#is restarting then reset the flag
					#if it's not set and the button is going off then we need 
					#to reset the 'A-B' button as all looping has ceased
					#Other cases need no action
					if buttonName == "play":
						if self.eosFlag:
							if toggleState:
								self.eosFlag = False
						else:
							if not toggleState:
								gobject.idle_add(self.ResetAB)
						button.set_active(toggleState)
			if not button.get_property("sensitive") == buttonStates[buttonName][1]:
				button.set_sensitive(buttonStates[buttonName][1])
		
		if not self.play.get_active() == self.abButton.get_property("sensitive"):
			self.abButton.set_sensitive(self.play.get_active())
		
		return True
	
	#____________________________________________________________________	

#=========================================================================
