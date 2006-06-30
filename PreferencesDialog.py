
import gtk
import gtk.glade
import gobject
import os
from ConfigParser import SafeConfigParser
import Project
import Globals
import AlsaDevices
import gst
import pygst
pygst.require("0.10")

STARTUP_WELCOME_DIALOG = "welcome"
STARTUP_LAST_PROJECT = "lastproject"
STARTUP_NOTHING = "nothing"

class PreferencesDialog:	
	def __init__(self, project, mainwindow, icon=None):
		self.project = project
		self.mainwindow = mainwindow

		self.res = gtk.glade.XML(self.mainwindow.GLADE_PATH, "PreferencesDialog")

		self.signals = {
			"on_Setting_changed" : self.OnSettingChanged,
			"on_Close_clicked" : self.OnClose,
		}

		self.res.signal_autoconnect(self.signals)
		self.dlg = self.res.get_widget("PreferencesDialog")
		self.dlg.set_icon(icon)
		self.mixdownFormat = self.res.get_widget("mixdownFormat")
		self.sampleRate = self.res.get_widget("sampleRate")
		self.sampleFormat = self.res.get_widget("sampleFormat")
		self.recordingFileFormat = self.res.get_widget("recordingFileFormat")
		self.playingDevice = self.res.get_widget("playbackDevice")
		self.radioWelcome = self.res.get_widget("startupWelcomeDialog")
		self.radioLastProject = self.res.get_widget("startupLastProject")
		self.radioNothing = self.res.get_widget("startupNothing")

		self.devicetocardnum = {}

		#Find all ALSA devices 
		self.playbacks = AlsaDevices.GetAlsaList("playback")
		for playback in self.playbacks:
			self.playingDevice.append_text(playback)

		self.OnCheckEncoders()

		#Load settings - set to True to make sure data isn't saved to file until everything is loaded
		self.loading = True
		self.LoadSetting(self.mixdownFormat, Globals.settings.general, "mixdownformat")
		self.LoadSetting(self.sampleRate, Globals.settings.general, "samplerate")
		self.LoadSetting(self.sampleFormat, Globals.settings.general, "sampleformat")
		self.LoadSetting(self.recordingFileFormat, Globals.settings.recording, "fileformat")
		self.LoadSetting(self.playingDevice, Globals.settings.playback, "device")
		self.loading = False

		# configure the application startup radio buttons
		startupValue = Globals.settings.general["startupaction"]
		if startupValue == STARTUP_LAST_PROJECT:
			self.radioLastProject.set_active(True)
		elif startupValue == STARTUP_NOTHING:
			self.radioNothing.set_active(True)
		else: #default in case no preference is saved
			self.radioWelcome.set_active(True)
		
		
	def LoadSetting(self, widget, section, property):
		if section.has_key(property):
			model = widget.get_model()
			
			iter = model.get_iter_first()
			while iter:
				if model.get_value(iter, 0) == section[property]:
					widget.set_active_iter(iter)
					break
				else:
					widget.set_active(0)
				iter = model.iter_next(iter)

	def OnClose(self, button): 
		self.dlg.destroy()

	def OnSettingChanged(self, combobox):
		if self.loading:
			return
		
		Globals.settings.general["mixdownformat"] = self.mixdownFormat.get_active_text()
		Globals.settings.general["samplerate"] = self.sampleRate.get_active_text()
		Globals.settings.general["sampleformat"] = self.sampleFormat.get_active_text()
		Globals.settings.recording["fileformat"] = self.recordingFileFormat.get_active_text()
		
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

	def OnCheckEncoders(self):
		"""list the available encoders on the computer"""

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
		
