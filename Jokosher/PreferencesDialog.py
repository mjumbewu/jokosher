#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       PreferencesDialog.py
#       
#       This dialog handles the setting of preferences
#
#-------------------------------------------------------------------------------

import gtk.glade
import Globals
import AlsaDevices
import pygst
pygst.require("0.10")
import gst

STARTUP_WELCOME_DIALOG = "welcome"
STARTUP_LAST_PROJECT = "lastproject"
STARTUP_NOTHING = "nothing"

#=========================================================================

class PreferencesDialog:	
	"""This class creates a dialog for selecting and saving global preferences."""

	def __init__(self, project, mainwindow, icon=None):
		"""Keyword arguments:
		project -- The jokosher project currently loaded.
		mainwindow -- A reference to the main Jokosher window
		icon -- The icon for the window manager to display for this window (optional)."""

		self.project = project
		self.mainwindow = mainwindow

		#Initialize GTK resources from glade file
		self.res = gtk.glade.XML(Globals.GLADE_PATH, "PreferencesDialog")

		self.signals = {
			"on_Setting_changed" : self.OnSettingChanged,
			"on_Close_clicked" : self.OnClose,
		}

		self.res.signal_autoconnect(self.signals)
		self.dlg = self.res.get_widget("PreferencesDialog")
		self.dlg.set_icon(icon)
		self.recordingFileFormat = self.res.get_widget("recordingFileFormat")
		self.samplingRate = self.res.get_widget("samplingRate")
		self.playingDevice = self.res.get_widget("playbackDevice")
		self.radioWelcome = self.res.get_widget("startupWelcomeDialog")
		self.radioLastProject = self.res.get_widget("startupLastProject")
		self.radioNothing = self.res.get_widget("startupNothing")

		#Find all ALSA devices 
		self.playbacks = AlsaDevices.GetAlsaList("playback")
		for playback in self.playbacks:
			print playback
			self.playingDevice.append_text(playback)
			
		#Get available sample rates from ALSA
		min_sample_rate, max_sample_rate = AlsaDevices.GetRecordingSampleRate()
		for rate in Globals.SAMPLE_RATES:
			if rate >= min_sample_rate and rate <= max_sample_rate:
				self.samplingRate.append_text(str(rate)+" Hz")
		
		fileFormatSetting = Globals.settings.recording["fileformat"]
		fileFormatSettingIndex = 0
		#get all the encoders from Globals
		for i in Globals.EXPORT_FORMATS:
			self.recordingFileFormat.append_text("%s (.%s)" % (i["description"], i["extension"]))
			if fileFormatSetting == i["pipeline"]:
				fileFormatSettingIndex = Globals.EXPORT_FORMATS.index(i)

		#Load settings - set to True to make sure data isn't saved to file until everything is loaded
		self.loading = True
		self.recordingFileFormat.set_active(fileFormatSettingIndex)
		self.LoadSetting(self.playingDevice, Globals.settings.playback, "device")
		self.LoadSetting(self.samplingRate, Globals.settings.recording, "samplerate")
		self.loading = False

		# configure the application startup radio buttons
		startupValue = Globals.settings.general["startupaction"]
		if startupValue == STARTUP_LAST_PROJECT:
			self.radioLastProject.set_active(True)
		elif startupValue == STARTUP_NOTHING:
			self.radioNothing.set_active(True)
		else: #default in case no preference is saved
			self.radioWelcome.set_active(True)
		
	#_____________________________________________________________________
		
	def LoadSetting(self, widget, section, property):
		"""Sets the selected value in a combobox to that specified by a configuration object
		
		Keyword arguments:
		widget -- The combobox to select the value in.
		section -- The configuration section object to find the property in.
		property -- The property of the configuration section to use when selecting the combobox value."""

		if section.has_key(property):
			model = widget.get_model()
			if not model:
				return
			
			iter = model.get_iter_first()
			while iter:
				#Iterate through all entries in the combobox until we find one matching the value saved in property
				if model.get_value(iter, 0) == section[property]:
					widget.set_active_iter(iter)
					break
				else:
					#Default to having the first item in the combobox selected
					widget.set_active(0)
				iter = model.iter_next(iter)
				
	#_____________________________________________________________________

	def OnClose(self, button=None): 
		"""Called when the user closes the preferences dialog.
		
		Keyword arguments:
		button -- The button widget that was clicked (unused, automatically specified by gtk)."""

		self.dlg.destroy()

	#_____________________________________________________________________

	def OnSettingChanged(self, combobox=None):
		"""Called when a setting is changed to update the currently used settings and write an updated settings file
		
		Keyword arguments:
		combobox -- The combobox widget that has changed (unused, automatically specified by gtk)."""

		if self.loading:
			return
		
		exportDict = Globals.EXPORT_FORMATS[self.recordingFileFormat.get_active()]
		Globals.settings.recording["fileformat"] = exportDict["pipeline"]
		Globals.settings.recording["samplerate"] = self.samplingRate.get_active_text()
		Globals.settings.playback["device"] = self.playingDevice.get_active_text()
		Globals.settings.playback["devicecardnum"] = self.playbacks[self.playingDevice.get_active_text()]		
		
		if self.radioWelcome.get_active():
			Globals.settings.general["startupaction"] = STARTUP_WELCOME_DIALOG
		elif self.radioLastProject.get_active():	
			Globals.settings.general["startupaction"] = STARTUP_LAST_PROJECT
		elif self.radioNothing.get_active():
			Globals.settings.general["startupaction"] = STARTUP_NOTHING
			
		Globals.settings.write()
		
		self.mainwindow.UpdateDisplay()

	#_____________________________________________________________________

	def OnCheckEncoders(self):
		"""List the available encoders installed on the computer
		   This code is not currently used, but is still here as it may
		   be useful in the future.
		"""

		thelist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		encoders = []
		for f in thelist:
			if "Codec/Encoder/Audio" in f.get_klass():
				encoders.append(f)
		gst.log(str(encoders))

		# these encoders are not actually hooked up yet - we will most likely
		# need to use enc.get_short_name() to return the element to include in
		# the pipeline
		
		for enc in encoders:
			self.mixdownFormat.append_text(enc.get_longname())
		
