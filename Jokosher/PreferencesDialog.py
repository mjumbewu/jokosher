#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       PreferencesDialog.py
#       
#       This dialog handles the setting of preferences
#
#-------------------------------------------------------------------------------

import gtk
import Globals
import AudioBackend
import pygst
pygst.require("0.10")
import gst
import gettext
_ = gettext.gettext

STARTUP_NEW_PROJECT = "newproject"
STARTUP_LAST_PROJECT = "lastproject"
STARTUP_NOTHING = "nothing"

#=========================================================================

class PreferencesDialog:	
	"""
	Creates a dialog for selecting and saving global preferences.
	"""

	def __init__(self, project, mainwindow, icon=None):
		"""
		Creates a new instance of PreferencesDialog.
		
		Parameters:
			project -- the currently active Project.
			mainwindow -- the main Jokosher window (MainApp).
			icon -- the icon for the window manager to display for this window (optional).
		"""

		self.project = project
		self.mainwindow = mainwindow

		#Initialize GTK resources from gtk builder file
		self.gtk_builder = Globals.LoadGtkBuilderFilename("PreferencesDialog.ui")

		self.signals = {
			"on_Setting_changed" : self.OnSettingChanged,
			"on_playbackSink_changed" : self.OnPlaybackSinkChanged,
			"on_recordingSoundSystem_changed" : self.OnRecordingSystemChanged,
			"on_Close_clicked" : self.OnClose,
		}
		self.gtk_builder.connect_signals(self.signals)
		
		self.dlg = self.gtk_builder.get_object("PreferencesDialog")
		self.dlg.set_icon(icon)
		self.recordingFileFormat = self.gtk_builder.get_object("recordingFileFormat")
		self.recordingCustomPipeline = self.gtk_builder.get_object("recordingCustomPipeline")
		self.recordingSoundSystem = self.gtk_builder.get_object("recordingSoundSystem")
		self.samplingRate = self.gtk_builder.get_object("samplingRate")
		self.bitRateCombo = self.gtk_builder.get_object("bitRate")
		self.bitRateLabel = self.gtk_builder.get_object("bitRateLabel")
		self.playbackDevice = self.gtk_builder.get_object("playbackDevice")
		self.playbackSink = self.gtk_builder.get_object("playbackSink")
		self.customSink = self.gtk_builder.get_object("customSink")
		self.radioNewProject = self.gtk_builder.get_object("startupNewProject")
		self.radioLastProject = self.gtk_builder.get_object("startupLastProject")
		self.radioNothing = self.gtk_builder.get_object("startupNothing")
		
		#Load settings - set to True to make sure data isn't saved to file until everything is loaded
		self.loadingSettings = True
		
		## Load recording sound system
		audioSrcSetting = Globals.settings.recording["audiosrc"]
		self.recordingCustomPipeline.set_text(audioSrcSetting)
		
		self.recordingSoundSystem.append_text(_("Custom"))
		self.recordingSoundSystem.set_active(0)
		
		for name, element in Globals.CAPTURE_BACKENDS:
			self.recordingSoundSystem.append_text(name)
			if audioSrcSetting == element:
				index = len(self.recordingSoundSystem.get_model()) - 1
				self.recordingSoundSystem.set_active(index)
				
		if self.recordingSoundSystem.get_active() == 0:
			self.recordingCustomPipeline.set_sensitive(True)
		else:
			self.recordingCustomPipeline.set_sensitive(False)
		
		## Load playback sound system
		audioSinkSetting = Globals.settings.playback["audiosink"]
		self.customSink.set_text(audioSinkSetting)
		
		self.playbackSink.append_text(_("Custom"))
		self.playbackSink.set_active(0)
		
		for name, element in Globals.PLAYBACK_BACKENDS:
			self.playbackSink.append_text(name)
			if audioSinkSetting == element:
				index = len(self.playbackSink.get_model()) - 1
				self.playbackSink.set_active(index)
				
		if self.playbackSink.get_active() == 0:
			self.customSink.set_sensitive(True)
		else:
			self.customSink.set_sensitive(False)
		
		self.ProbeBackendDevices()
			
		#Get available sample rates from ALSA
		sample_values = AudioBackend.GetRecordingSampleRate()
		i18nText = "%(sample rate)d Hz"
		#add tuple of (display string, rate value)
		self.sampleRateList = [( _("Autodetect"), 0)]
		if type(sample_values) == int:
			text = i18nText % {"sample rate" : sample_values}
			self.sampleRateList.append( (text, sample_values) )
		elif type(sample_values) == list:
			for i, rate in enumerate (sample_values):
				text = i18nText % {"sample rate" : rate}
				self.sampleRateList.append( (text, rate) )
		#check if it is an IntRange
		elif hasattr(sample_values, "low") and hasattr(sample_values, "high"):
			#add the default sample rates if they are within the supported range
			for rate in Globals.SAMPLE_RATES:
				if sample_values.low <= rate <= sample_values.high:
					text = i18nText % {"sample rate" : rate}
					self.sampleRateList.append( (text, rate) )
					
		sampleRateSetting = 0
		sampleRateSettingIndex = 0
		try:
			#try to convert the setting string to an int
			sampleRateSetting = int( Globals.settings.recording["samplerate"] )
		except ValueError:
			pass
		else:
			#if they have put in a custom preference which is not ordinarily detected, add it to the list
			if sampleRateSetting not in [y for x,y in self.sampleRateList]:
				text = i18nText % {"sample rate" : sampleRateSetting}
				self.sampleRateList.append( (text, sampleRateSetting) )
		
		for text, value in self.sampleRateList:
			self.samplingRate.append_text(text)
			if value == sampleRateSetting:
				sampleRateSettingIndex = self.sampleRateList.index( (text, value) )
		self.samplingRate.set_active(sampleRateSettingIndex)
		
		#Bit rate settings for lossy file formats
		try:
			bitRateSetting = int(Globals.settings.recording["bitrate"])
			if Globals.settings.recording["file_extension"] == "ogg":
				# vorbisenc uses bps instead of kbps
				bitRateSetting /= 1024
		except KeyError:
			bitRateSetting = int(Globals.DEFAULT_BIT_RATE)
		if bitRateSetting == 0:
			bitRateSetting = int(Globals.DEFAULT_BIT_RATE)

		for index, bitrate in enumerate(Globals.BIT_RATES):
			self.bitRateCombo.append_text("%d kbps" % bitrate)
			if bitrate == bitRateSetting:
				self.bitRateCombo.set_active(index)
		
		fileFormatSetting = Globals.settings.recording["fileformat"]
		fileFormatSettingIndex = 0
		setBitRate = False
		#get all the encoders from Globals
		for exportFormat in Globals.EXPORT_FORMATS:
			self.recordingFileFormat.append_text("%s (.%s)" % (exportFormat["description"], exportFormat["extension"]))
			if fileFormatSetting == exportFormat["pipeline"]:
				fileFormatSettingIndex = Globals.EXPORT_FORMATS.index(exportFormat)
				setBitRate = exportFormat["setBitRate"]
		
		self.recordingFileFormat.set_active(fileFormatSettingIndex)
		
		# configure the application startup radio buttons
		startupValue = Globals.settings.general["startupaction"]
		if startupValue == STARTUP_LAST_PROJECT:
			self.radioLastProject.set_active(True)
		elif startupValue == STARTUP_NEW_PROJECT:
			self.radioNewProject.set_active(True)
		else: #default in case no preference is saved
			self.radioNothing.set_active(True)
			
		self.loadingSettings = False

		self.dlg.show_all()
		self.ShowBitRate(setBitRate)
		
	#_____________________________________________________________________
		
	def LoadSetting(self, widget, section, property):
		"""
		Sets the selected value in a combobox, to that specified by a configuration object.
		
		Parameters:
			widget -- the combobox to select the value in.
			section -- the configuration section object to find the property in.
			property -- the property of the configuration section to use when 
						selecting the combobox value.
		"""
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
		"""
		Called when the user closes the preferences dialog.
		
		Parameters:
			button -- reserved for GTK callbacks, don't use it explicitly.
		"""
		self.dlg.destroy()

	#_____________________________________________________________________

	def OnSettingChanged(self, combobox=None):
		"""
		Called when a setting is changed, to update the currently used settings.
		It then writes an updated settings file.
		
		Parameters:
			combobox -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.loadingSettings:
			return
		
		exportDict = Globals.EXPORT_FORMATS[self.recordingFileFormat.get_active()]
		self.ShowBitRate(exportDict["setBitRate"])
		if exportDict["setBitRate"]:
			bitrate = Globals.BIT_RATES[self.bitRateCombo.get_active()]
			if exportDict["extension"] == "ogg":
				# vorbisenc takes bit rate in bps instead of kbps
				bitrate *= 1024
		else:
			# Indicates that this encoder doesn't take a bitrate parameter
			bitrate = 0
		Globals.settings.recording["bitrate"] = bitrate
		Globals.settings.recording["fileformat"] = exportDict["pipeline"]
		Globals.settings.recording["file_extension"] = exportDict["extension"]
		#only get the number from "44100 Hz", not the whole string
		sampleRateIndex = self.samplingRate.get_active()
		Globals.settings.recording["samplerate"] = self.sampleRateList[sampleRateIndex][1]
		if self.playbackDevice.get_active() >= 0:
			old_device = Globals.settings.playback["device"]
			new_device = self.playbacks[self.playbackDevice.get_active()]
			Globals.settings.playback["devicename"] = self.playbackDevice.get_active_text()
			Globals.settings.playback["device"] = new_device
			
			if old_device != new_device and self.project:
				self.project.SetProjectSinkDevice()
		else:
			Globals.settings.playback["devicename"] = ""
			Globals.settings.playback["device"] = ""
		
		if self.radioNewProject.get_active():
			Globals.settings.general["startupaction"] = STARTUP_NEW_PROJECT
		elif self.radioLastProject.get_active():	
			Globals.settings.general["startupaction"] = STARTUP_LAST_PROJECT
		elif self.radioNothing.get_active():
			Globals.settings.general["startupaction"] = STARTUP_NOTHING
			
		Globals.settings.write()

	#_____________________________________________________________________

	def OnPlaybackSinkChanged(self, widget=None, event=None):
		"""
		Updates the selected playback audio device from the comboBox selection.
		It then writes an updated settings file.
		
		Parameters:
			comboBox -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.loadingSettings:
			return
	
		if self.playbackSink.get_active() == 0:
			self.customSink.set_sensitive(True)
			Globals.settings.playback["audiosink"] = self.customSink.get_text()
		else:
			self.customSink.set_sensitive(False)
			index = self.playbackSink.get_active() - 1
			name, element = Globals.PLAYBACK_BACKENDS[index]
			Globals.settings.playback["audiosink"] = element
			self.customSink.set_text(element)
			
		self.ProbeBackendDevices()
			
		Globals.settings.write()
		if self.project:
			self.project.SetProjectSink()
	
	#_____________________________________________________________________
	
	def OnRecordingSystemChanged(self, widget=None, event=None):
		"""
		Updates the selected playback audio device from the comboBox selection.
		It then writes an updated settings file.
		
		Parameters:
			comboBox -- reserved for GTK callbacks, don't use it explicitly.
		"""
		if self.loadingSettings:
			return
	
		if self.recordingSoundSystem.get_active() == 0:
			self.recordingCustomPipeline.set_sensitive(True)
			Globals.settings.recording["audiosrc"] = self.recordingCustomPipeline.get_text()
		else:
			self.recordingCustomPipeline.set_sensitive(False)
			index = self.recordingSoundSystem.get_active() - 1
			name, element = Globals.CAPTURE_BACKENDS[index]
			Globals.settings.recording["audiosrc"] = element
			self.recordingCustomPipeline.set_text(element)
			
		Globals.settings.write()
		if self.project:
			self.project.OnCaptureBackendChange()
	
	#_____________________________________________________________________
	
	def OnCheckEncoders(self):
		"""
		List the available encoders installed on the computer.
		This code is not currently used, but is still here as it may 
		be useful in the future.
		"""

		gstfeatures = gst.registry_get_default().get_feature_list(gst.ElementFactory)
		encoders = []
		for feature in gstfeatures:
			if "Codec/Encoder/Audio" in feature.get_klass():
				encoders.append(feature)
		gst.log(str(encoders))

		# these encoders are not actually hooked up yet - we will most likely
		# need to use enc.get_short_name() to return the element to include in
		# the pipeline
		
		for enc in encoders:
			self.mixdownFormat.append_text(enc.get_longname())
	
	#_____________________________________________________________________

	def ProbeBackendDevices(self):
		#Find all playback devices
		self.playbacks = [] # Map combobox entries to property names instead of human readable names).
		self.playbackDevice.get_model().clear() # clear combo box
		for index, (device, deviceName) in enumerate(AudioBackend.ListPlaybackDevices()):
			if len(self.playbacks) == 0 and not deviceName:
				deviceName = _("Default")
			self.playbacks.append(device)
			if deviceName and device:
				s = _("%(device)s (%(id)s)") % {"device":deviceName, "id":device}
				self.playbackDevice.append_text(s)
			elif device:
				self.playbackDevice.append_text(device)
			else:
				self.playbackDevice.append_text(_("Device %d") % index)
			
		if not self.playbacks:
			self.playbackDevice.set_sensitive(False)
		else:
			self.playbackDevice.set_sensitive(True)
			self.LoadSetting(self.playbackDevice, Globals.settings.playback, "devicename")
	
	#_____________________________________________________________________

	def ShowBitRate(self, show):
		"""
		Shows or hides the bit rate combo box.

		Parameters:
			show -- Boolean indicating whether to show the bit rate combo box or not.
		"""
		self.bitRateCombo.set_visible(show)
		self.bitRateLabel.set_visible(show)

	#_____________________________________________________________________
