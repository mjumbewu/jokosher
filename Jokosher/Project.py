#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Project.py
#	
#	This module is the central non-gui class for Jokosher. It saves and loads
#	project files, and handles any project wide functionality including;
#	settings, instruments, recording, playing, exporint, zooming, scrolling, 
#	undo, redo, volume, etc.
#
#-------------------------------------------------------------------------------

import pygst
pygst.require("0.10")
import gst
import gobject
import os, os.path
import gzip
import re

import TransportManager
import UndoSystem, IncrementalSave
import Globals
import xml.dom.minidom as xml
import Instrument, Event
import Utils
import AudioBackend
import ProjectManager
import PlatformUtils

#=========================================================================

class Project(gobject.GObject):
	"""
	This class maintains all of the information required about single Project. It also
	saves and loads Project files.
	"""
	
	""" The Project structure version. Will be useful for handling old save files. """
	Globals.VERSION = "0.11.1"
	
	""" The audio playback state enum values """
	AUDIO_STOPPED, AUDIO_RECORDING, AUDIO_PLAYING, AUDIO_PAUSED, AUDIO_EXPORTING = range(5)
	
	""" String constants for incremental save """
	INCREMENTAL_SAVE_EXT = ".incremental"
	INCREMENTAL_SAVE_DELIMITER = "\n<<delimiter>>\n"
	
	"""
	Signals:
		"audio-state" -- The status of the audio system has changed. See below:
			"audio-state::play" -- The audio started playing.
			"audio-state::pause" -- The audio is paused.
			"audio-state::record" -- The audio started recording.
			"audio-state::stop" -- The playback or recording was stopped.
			"audio-state::export-start" -- The audio is being played to a file.
			"audio-state::export-stop" -- The export to a file has completed.
		"bpm" -- The beats per minute value was changed.
		"click-track" -- The volume of the click track changed.
		"gst-bus-error" -- An error message was posted to the pipeline. Two strings are also send with the error details.
		"incremental-save" -- An action was logged to the .incremental file.
		"instrument" -- The instruments for this project have changed. The instrument instance will be passed as a parameter. See below:
			"instrument::added" -- An instrument was added to this project.
			"instrument::removed" -- An instrument was removed from this project.
			"instrument::reordered" -- The order of the instruments for this project changed.
		"time-signature" -- The time signature values were changed.
		"undo" -- The undo or redo stacks for this project have been changed.
		"view-start" -- The starting position of the view of this project's timeline has changed.
		"volume" -- This master volume value for this project has changed.
		"zoom" -- The zoom level of this project's timeline has changed.
	"""
	
	__gsignals__ = {
		"audio-state"		: ( gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_DETAILED, gobject.TYPE_NONE, () ),
		"bpm"			: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"click-track"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_DOUBLE,) ),
		"gst-bus-error"	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING) ),
		"incremental-save" : ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"instrument"		: ( gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_DETAILED, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,) ),
		"name"			: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,) ),
		"time-signature"	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"undo"			: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"view-start"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"volume"			: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"zoom"			: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}

	#_____________________________________________________________________

	def __init__(self):
		"""
		Creates a new instance of Project with default values.
		"""
		gobject.GObject.__init__(self)
		
		self.author = ""			#user specified author of this project
		self.name = ""				#the name of this project
		self.name_is_unset = True		#True if the user has not manually changed the name
		self.notes = ""				#user specified notes for the project
		self.projectfile = ""		#the name of the project file, complete with path
		self.audio_path = ""
		self.levels_path = ""
		self.___id_list = []		#the list of IDs that have already been used, to avoid collisions
		self.instruments = []		#the list of instruments held by this project
		self.graveyard = []			# The place where deleted instruments are kept, to later be retrieved by undo functions
		#used to delete copied audio files if the event that uses them is not saved in the project file
		#also contains paths to levels_data files corresponding to those audio files
		self.deleteOnCloseAudioFiles = []	# WARNING: any paths in this list will be deleted on exit!
		self.clipboardList = []		#The list containing the events to cut/copy
		self.viewScale = 25.0		#View scale as pixels per second
		self.viewStart= 0.0			#View offset in seconds
		self.soloInstrCount = 0		#number of solo instruments (to know if others must be muted)
		self.audioState = self.AUDIO_STOPPED	#which audio state we are currently in
		self.exportPending = False	# True if we are waiting to start an export
		self.exportFilename = ""
		self.bpm = 120
		self.meter_nom = 4		# time signature numerator
		self.meter_denom = 4		# time signature denominator
		self.clickbpm = 120			#the number of beats per minute that the click track will play
		self.clickVolumeValue = 0	#The value of the click track volume between 0.0 and 1.0
		#Keys are instruments which are recording; values are 3-tuples of the event being recorded, the recording bin and bus handler id
		self.recordingEvents = {}	#Dict containing recording information for each recording instrument
		self.volume = 1.0			#The volume setting for the entire project
		self.level = 0.0			#The level of the entire project as reported by the gstreamer element
		self.currentSinkString = None	#to keep track if the sink changes or not
		
		self.newly_created_project = False	#if the project was newly created this session (set by ProjectManager.CreateNewProject())

		self.hasDoneIncrementalSave = False	# True if we have already written to the .incremental file from this project.
		self.isDoingIncrementalRestore = False # If we are currently restoring incremental save actions

		# Variables for the undo/redo command system
		self.__unsavedChanges = False	#This boolean is to indicate if something which is not on the undo/redo stack needs to be saved
		self.__undoStack = []			#not yet saved undo commands
		self.__redoStack = []			#not yet saved actions that we're undone
		self.__savedUndoStack = []		#undo commands that have already been saved in the project file
		self.__savedRedoStack = []		#redo commands that have already been saved in the project file
		self.__performingUndo = False	#True if we are currently in the process of performing an undo command
		self.__performingRedo = False	#True if we are currently in the process of performing a redo command
		self.__savedUndo = False		#True if we are performing an undo/redo command that was previously saved
	
		
		# CREATE GSTREAMER ELEMENTS AND SET PROPERTIES #
		self.mainpipeline = gst.Pipeline("timeline")
		self.playbackbin = gst.Bin("playbackbin")
		self.adder = gst.element_factory_make("adder")
		self.postAdderConvert = gst.element_factory_make("audioconvert")
		self.masterSink = self.MakeProjectSink()
		
		self.levelElement = gst.element_factory_make("level", "MasterLevel")
		self.levelElement.set_property("interval", gst.SECOND / 50)
		self.levelElement.set_property("message", True)
		
		#Restrict adder's output caps due to adder bug 341431
		self.levelElementCaps = gst.element_factory_make("capsfilter", "levelcaps")
		capsString = "audio/x-raw-float,rate=44100,channels=2,width=32,endianness=(int)BYTE_ORDER"
		caps = gst.caps_from_string(capsString)
		self.levelElementCaps.set_property("caps", caps)
		
		# ADD ELEMENTS TO THE PIPELINE AND/OR THEIR BINS #
		self.mainpipeline.add(self.playbackbin)
		Globals.debug("added project playback bin to the pipeline")
		for element in [self.adder, self.levelElementCaps, self.postAdderConvert, self.levelElement, self.masterSink]:
			self.playbackbin.add(element)
			Globals.debug("added %s to project playbackbin" % element.get_name())

		# LINK GSTREAMER ELEMENTS #
		self.adder.link(self.levelElementCaps)
		self.levelElementCaps.link(self.postAdderConvert)
		self.postAdderConvert.link(self.levelElement)
		self.levelElement.link(self.masterSink)
		
		# CONSTRUCT CLICK TRACK BIN #
		self.clickTrackBin = gst.Bin("Click_Track_Bin")
		self.clickTrackAudioSrc = gst.element_factory_make("audiotestsrc", "Click_Track_AudioSource")
		self.clickTrackAudioSrc.set_property("wave", 3)
		self.clickTrackVolume = gst.element_factory_make("volume", "Click_Track_Volume")
		self.clickTrackVolume.set_property("mute", True)
		self.clickTrackConvert = gst.element_factory_make("audioconvert", "Click_Track_Audioconvert")
		
		self.playbackbin.add(self.clickTrackBin)
		for element in [self.clickTrackAudioSrc, self.clickTrackVolume, self.clickTrackConvert]:
			self.clickTrackBin.add(element)
		
		clickTrackSrc = gst.GhostPad("src", self.clickTrackConvert.get_pad("src"))
		self.clickTrackBin.add_pad(clickTrackSrc)
		self.clickTrackController = gst.Controller(self.clickTrackAudioSrc, "volume")
		
		self.clickTrackAudioSrc.link(self.clickTrackVolume)
		self.clickTrackVolume.link(self.clickTrackConvert)
		self.clickTrackBin.link(self.adder)
		# /END OF GSTREAMER BITS #
		
		# set up the bus message callbacks
		self.bus = self.mainpipeline.get_bus()
		self.bus.add_signal_watch()
		self.Mhandler = self.bus.connect("message::element", self.__PipelineBusLevelCb)
		self.EOShandler = self.bus.connect("message::eos", self.Stop)
		self.Errorhandler = self.bus.connect("message::error", self.__PipelineBusErrorCb)
		
		#initialize the transport mode
		self.transportMode = TransportManager.TransportManager.MODE_BARS_BEATS
		self.transport = TransportManager.TransportManager(self.transportMode, self)

		self.PrepareClick()
	
	#_____________________________________________________________________
	
	def Play(self, newAudioState=None):
		"""
		Start playback or recording.
		
		Parameters:
			newAudioState -- determines the Project audio state to set when playback commences:
							AUDIO_PAUSED or AUDIO_PLAYING = move the graphical indicator along playback.
							AUDIO_EXPORTING = perform playback without moving the graphical bar.
			recording -- determines if the Project should only playback or playback and record:
						True = playback and record.
						False = playback only.
		"""
		if not newAudioState:
			newAudioState = self.AUDIO_PLAYING
		
		Globals.debug("play() in Project.py")
		Globals.debug("current state:", self.mainpipeline.get_state(0)[1].value_name)

		for ins in self.instruments:
			ins.PrepareController()
		
		if not self.GetIsPlaying():
			# Connect the state changed handler
			self.state_id = self.bus.connect("message::state-changed", self.__PlaybackStateChangedCb, newAudioState)
			#set to PAUSED so the transport manager can seek first (if needed)
			#the pipeline will be set to PLAY by self.state_changed()
			self.mainpipeline.set_state(gst.STATE_PAUSED)
		else:
			# we are already paused or playing, so just start the transport manager
			self.transport.Play(newAudioState)
		
		Globals.debug("just set state to PAUSED")
		
	#_____________________________________________________________________

	def Pause(self):
		self.transport.Pause()
	
	#_____________________________________________________________________
	
	def Stop(self, bus=None, message=None):
		"""
		Stop playback or recording
		
		Parameters:
			bus -- reserved for GStreamer callbacks, don't use it explicitly.
			message -- reserved for GStreamer callbacks, don't use it explicitly.
		"""

		Globals.debug("Stop pressed, about to set state to READY")
		Globals.debug("current state:", self.mainpipeline.get_state(0)[1].value_name)
		
		#If we've been recording then add new events to instruments
		for instr, (event, bin, handle) in self.recordingEvents.iteritems():
			instr.FinalizeRecording(event)
			self.bus.disconnect(handle)

		self.TerminateRecording()
		
	#_____________________________________________________________________

	def TerminateRecording(self):
		"""
		Terminate all instruments. Disregards recording when an 
		error occurs after instruments have started.
		"""
		Globals.debug("Terminating recording.")
		self.transport.Stop()
		Globals.debug("State just set to READY")
		
		#Relink instruments and stop their recording bins
		for instr, (event, bin, handle) in self.recordingEvents.iteritems():
			try:
				Globals.debug("Removing recordingEvents bin")
				self.mainpipeline.remove(bin)
			except:
				pass #Already removed from another instrument
			Globals.debug("set state to NULL")
			bin.set_state(gst.STATE_NULL)
			instr.AddAndLinkPlaybackbin()

		self.recordingEvents = {}

	#_____________________________________________________________________
	
	def Record(self):
		"""
		Start recording all selected instruments.
		"""

		Globals.debug("pre-record state:", self.mainpipeline.get_state(0)[1].value_name)
		
		#Add all instruments to the pipeline
		self.recordingEvents = {}
		devices = {}
		capture_devices = AudioBackend.ListCaptureDevices(probe_name=False)
		if not capture_devices:
			capture_devices = ((None,None),)
		
		default_device = capture_devices[0][0]
		
		for device, deviceName in capture_devices:
			devices[device] = []
			for instr in self.instruments:
				if instr.isArmed and (instr.input == device or device is None):
					instr.RemoveAndUnlinkPlaybackbin()
					devices[device].append(instr)
				elif instr.isArmed and instr.input is None:
					instr.RemoveAndUnlinkPlaybackbin()
					devices[default_device].append(instr)
		

		recbin = 0
		for device, recInstruments in devices.iteritems():
			if len(recInstruments) == 0:
				#Nothing to record on this device
				continue

			if device is None:
				# assume we are using a backend like JACK which does not allow
				#us to do device selection.
				channelsNeeded = len(recInstruments)
			else:
				channelsNeeded = AudioBackend.GetChannelsOffered(device)

			
			if channelsNeeded > 1: #We're recording from a multi-input device
				#Need multiple recording bins with unique names when we're
				#recording from multiple devices
				recordingbin = gst.Bin("recordingbin_%d" % recbin)
				recordString = Globals.settings.recording["audiosrc"]
				srcBin = gst.parse_bin_from_description(recordString, True)
				try:
					src_element = srcBin.iterate_sources().next()
				except StopIteration:
					pass
				else:
					if hasattr(src_element.props, "device"):
						src_element.set_property("device", device)
				
				caps = gst.caps_from_string("audio/x-raw-int;audio/x-raw-float")

				sampleRate = Globals.settings.recording["samplerate"]
				try:
					sampleRate = int(sampleRate)
				except ValueError:
					sampleRate = 0
				# 0 means for "autodetect", or more technically "don't use any rate caps".
				if sampleRate > 0:
					for struct in caps:
						struct.set_value("rate", sampleRate)

				for struct in caps:
					struct.set_value("channels", channelsNeeded)

				Globals.debug("recording with capsfilter:", caps.to_string())
				capsfilter = gst.element_factory_make("capsfilter")
				capsfilter.set_property("caps", caps)
				
				split = gst.element_factory_make("deinterleave")
				convert = gst.element_factory_make("audioconvert")
				
				recordingbin.add(srcBin, split, convert, capsfilter)
				
				srcBin.link(convert) 
				convert.link(capsfilter)
				capsfilter.link(split)
				
				split.connect("pad-added", self.__RecordingPadAddedCb, recInstruments, recordingbin)
				Globals.debug("Recording in multi-input mode")
				Globals.debug("adding recordingbin_%d" % recbin)
				self.mainpipeline.add(recordingbin)
				recbin += 1
			else:
				instr = recInstruments[0]
				event = instr.GetRecordingEvent()
			
				encodeString = Globals.settings.recording["fileformat"]
				recordString = Globals.settings.recording["audiosrc"]

				# 0 means this encoder doesn't take a bitrate
				if Globals.settings.recording["bitrate"] > 0:
					encodeString %= {'bitrate' : int(Globals.settings.recording["bitrate"])}
				
				sampleRate = 0
				try:
					sampleRate = int( Globals.settings.recording["samplerate"] )
				except ValueError:
					pass
				# 0 means "autodetect", or more technically "don't use any caps".
				if sampleRate > 0:
					capsString = "audio/x-raw-int,rate=%s ! audioconvert" % sampleRate
				else:
					capsString = "audioconvert"
					
				# TODO: get rid of this entire string; do it manually
				pipe = "%s ! %s ! level name=recordlevel ! audioconvert ! %s ! filesink name=sink"
				pipe %= (recordString, capsString, encodeString)
				
				Globals.debug("Using pipeline: %s" % pipe)
				
				recordingbin = gst.parse_bin_from_description(pipe, False)
				
				filesink = recordingbin.get_by_name("sink")
				level = recordingbin.get_by_name("recordlevel")
				
				filesink.set_property("location", event.GetAbsFile())
				level.set_property("interval", int(event.LEVEL_INTERVAL * gst.SECOND))
				
				#update the levels in real time
				handle = self.bus.connect("message::element", event.recording_bus_level)
				
				try:
					src_element = recordingbin.iterate_sources().next()
				except StopIteration:
					pass
				else:
					if hasattr(src_element.props, "device"):
						src_element.set_property("device", device)
				
				self.recordingEvents[instr] = (event, recordingbin, handle)
				
				Globals.debug("Recording in single-input mode")
				Globals.debug("Using input track: %s" % instr.inTrack)
				
				Globals.debug("adding recordingbin")
				self.mainpipeline.add(recordingbin)
		
		#start the pipeline!
		self.Play(newAudioState=self.AUDIO_RECORDING)
		
	#_____________________________________________________________________

	def Export(self, filename, encodeBin, samplerate=None, bitrate=None):
		"""
		Export to location filename with format specified by format variable.
		
		Parameters:
			filename -- filename where the exported audio will be saved.
			encodeBin -- the gst-launch syntax string of the encoder as used in Globals.EXPORT_FORMATS:
					for ogg: "vorbisenc ! oggmux"
					for mp3: "lame"
					for wav: "wavenc"
			samplerate -- the sample rate to output (optional, uses project default if blank).
			bitrate -- the target bit rate to encode at (optional, uses encoder default if blank).
		"""
		
		if samplerate:
			encodeBin = "audioresample ! audio/x-raw-float,rate=%d ! audioconvert ! %s" % (samplerate, encodeBin)
		if bitrate:
			encodeBin %= {'bitrate' : bitrate}
			
		#try to create encoder/muxer first, before modifying the main pipeline.
		try:
			self.encodebin = gst.parse_bin_from_description(encodeBin, True)
		except gobject.GError, e:
			if e.code == gst.PARSE_ERROR_NO_SUCH_ELEMENT:
				error_no = ProjectManager.ProjectExportException.MISSING_ELEMENT
			else:
				error_no = ProjectManager.ProjectExportException.INVALID_ENCODE_BIN
			raise ProjectManager.ProjectExportException(error_no, e.message)

		#stop playback because some elements will be removed from the pipeline
		self.Stop()
		
		#remove and unlink the alsasink
		self.playbackbin.remove(self.masterSink, self.levelElement)
		self.postAdderConvert.unlink(self.levelElement)
		self.levelElement.unlink(self.masterSink)
		
		#create filesink
		self.outfile = gst.element_factory_make("filesink", "export_file")
		self.outfile.set_property("location", filename)
		self.playbackbin.add(self.outfile)

		self.playbackbin.add(self.encodebin)
		self.postAdderConvert.link(self.encodebin)
		self.encodebin.link(self.outfile)
			
		#disconnect the bus message handler so the levels don't change
		self.bus.disconnect(self.Mhandler)
		self.bus.disconnect(self.EOShandler)
		self.EOShandler = self.bus.connect("message::eos", self.TerminateExport)
		
		self.exportPending = True
		self.exportFilename = filename
		#start the pipeline!
		self.Play(newAudioState=self.AUDIO_EXPORTING)
		self.emit("audio-state::export-start")

	#_____________________________________________________________________
	
	def TerminateExport(self, bus=None, message=None):
		"""
		GStreamer End Of Stream handler. It is connected to eos on 
		mainpipeline while export is taking place.
		
		Parameters:
			bus -- reserved for GStreamer callbacks, don't use it explicitly.
			message -- reserved for GStreamer callbacks, don't use it explicitly.
		"""
		
		if not self.GetIsExporting():
			return
	
		#stop playback because some elements will be removed from the pipeline
		self.Stop()
	
		self.bus.disconnect(self.EOShandler)
		self.Mhandler = self.bus.connect("message::element", self.__PipelineBusLevelCb)
		self.EOShandler = self.bus.connect("message::eos", self.Stop)
		
		#remove the filesink and encoder
		self.playbackbin.remove(self.outfile, self.encodebin)		
		self.postAdderConvert.unlink(self.encodebin)
			
		#dispose of the elements
		self.outfile.set_state(gst.STATE_NULL)
		self.encodebin.set_state(gst.STATE_NULL)
		del self.outfile, self.encodebin
		
		#re-add all the alsa playback elements
		self.playbackbin.add(self.masterSink, self.levelElement)
		self.postAdderConvert.link(self.levelElement)
		self.levelElement.link(self.masterSink)
		
		self.emit("audio-state::export-stop")
	
	#_____________________________________________________________________
	
	def GetExportProgress(self):
		"""
		Returns a tuple with the number of seconds exported
		and the number of total seconds.
		"""
		if self.exportPending or self.GetIsExporting():
			try:
				#total = self.mainpipeline.query_duration(gst.FORMAT_TIME)[0]
				total = self.GetProjectLength() * gst.SECOND
				current = self.mainpipeline.query_position(gst.FORMAT_TIME)[0]
			except gst.QueryError:
				return (-1, -1)
			else:
				if current > total:
					total = current
					self.TerminateExport()
				return (float(current)/gst.SECOND, float(total)/gst.SECOND)
		else:
			return (100, 100)
		
	#_____________________________________________________________________
	
	def GetIsPlaying(self):
		"""
		Returns true if the Project is not in the stopped state,
		because paused, playing and recording are all forms of playing.
		"""
		return self.audioState != self.AUDIO_STOPPED
	
	#_____________________________________________________________________
	
	def GetIsRecording(self):
		"""
		Returns true if the Project is in the recording state.
		"""
		return self.audioState == self.AUDIO_RECORDING
	
	#_____________________________________________________________________
	
	def GetIsExporting(self):
		"""
		Returns true if the Project is not in the stopped state,
		because paused, playing and recording are all forms of playing.
		"""
		return self.audioState == self.AUDIO_EXPORTING
	
	#_____________________________________________________________________
	
	def SetAudioState(self, newState):
		"""
		Set the Project's audio state to the new state enum value.
		
		Parameters:
			newState -- the new state to set the Project to.
		"""
		self.audioState = newState
		if newState == self.AUDIO_PAUSED:
			self.emit("audio-state::pause")
		elif newState == self.AUDIO_PLAYING:
			self.emit("audio-state::play")
		elif newState == self.AUDIO_STOPPED:
			self.emit("audio-state::stop")
		elif newState == self.AUDIO_RECORDING:
			self.emit("audio-state::record")
		elif newState == self.AUDIO_EXPORTING:
			self.exportPending = False
		
	#_____________________________________________________________________
	
	def __RecordingPadAddedCb(self, elem, pad, recInstruments, bin):
		"""
		Handles new pad creation on the GStreamer channel split element
		when recording multiple streams at once. This method will be called
		when the new pad is ready to be connected to the encoder.
		
		Parameters:
			elem -- the GStreamer channel split element.
			pad -- the new src pad on the channel split element.
			recInstruments -- list with all Instruments currently recording.
			bin -- the bin that stores all the recording elements.
		"""
		# SRC template: 'src%d'
		padname = pad.get_name()
		try:
			index = int(padname[3:])
		except ValueError:
			Globals.debug("Cannot start multichannel record: pad name does not match 'src%d':", padname)
			return

		for instr in recInstruments:
			if instr.inTrack == index:
				event = instr.GetRecordingEvent()
				
				encodeString = Globals.settings.recording["fileformat"]
				# 0 means this encoder doesn't take a bitrate
				if Globals.settings.recording["bitrate"] > 0:
					encodeString %= {'bitrate' : int(Globals.settings.recording["bitrate"])}
				pipe = "queue ! audioconvert ! level name=recordlevel ! audioconvert ! %s ! filesink name=sink"
				pipe %= encodeString
				
				encodeBin = gst.parse_bin_from_description(pipe, True)
				bin.add(encodeBin)
				pad.link(encodeBin.get_pad("sink"))
				
				filesink = bin.get_by_name("sink")
				level = bin.get_by_name("recordlevel")
				
				filesink.set_property("location", event.GetAbsFile())
				level.set_property("interval", int(event.LEVEL_INTERVAL * gst.SECOND))
				
				handle = self.bus.connect("message::element", event.recording_bus_level)
				
				# since we are adding the encodebin to an already playing pipeline, sync up there states
				encodeBin.set_state(gst.STATE_PLAYING)

				self.recordingEvents[instr] = (event, bin, handle)
				Globals.debug("Linked recording channel: instrument (%s), track %d" % (instr.name, instr.inTrack))
				break

	#_____________________________________________________________________
	
	def __PlaybackStateChangedCb(self, bus, message, newAudioState):
		"""
		Handles GStreamer statechange events when the pipline is changing from
		STATE_READY to STATE_PAUSED. Once STATE_PAUSED has been reached, this
		function will tell the transport manager to start playing.
		
		Parameters:
			bus -- reserved for GStreamer callbacks, don't use it explicitly.
			message -- reserved for GStreamer callbacks, don't use it explicitly.
			newAudioState -- the new Project audio state the transport manager
							should set when playback starts.
		"""
		Globals.debug("STATE CHANGED")
		change_status, new, pending = self.mainpipeline.get_state(0)
		Globals.debug("-- status:", change_status.value_name)
		Globals.debug("-- pending:", pending.value_name)
		Globals.debug("-- new:", new.value_name)

		#Move forward to playing when we reach paused (check pending to make sure this is the final destination)
		if new == gst.STATE_PAUSED and pending == gst.STATE_VOID_PENDING and not self.GetIsPlaying():
			bus.disconnect(self.state_id)
			#The transport manager will seek if necessary, and then set the pipeline to STATE_PLAYING
			self.transport.Play(newAudioState)

	#_____________________________________________________________________
	
	def __PipelineBusLevelCb(self, bus, message):
		"""
		Handles GStreamer bus messages about the currently reported level
		for the Project or any of the Instruments.
		
		Parameters:
			bus -- reserved for GStreamer callbacks, don't use it explicitly.
			message -- reserved for GStreamer callbacks, don't use it explicitly.
			
		Returns:
			True -- TODO
		"""
		struct = message.structure
		
		if struct and struct.get_name() == "level":
			if not message.src is self.levelElement:
				for instr in self.instruments:
					if message.src is instr.levelElement:
						instr.SetLevel(Utils.DbToFloat(struct["decay"][0]))
						break
			else:
				self.SetLevel(Utils.DbToFloat(struct["decay"][0]))
			
		return True

	#_____________________________________________________________________

	def __PipelineBusErrorCb(self, bus, message):
		"""
		Handles GStreamer error messages.
		
		Parameters:
			bus -- reserved for GStreamer callbacks, don't use it explicitly.
			message -- reserved for GStreamer callbacks, don't use it explicitly.
		"""
		error, debug = message.parse_error()
		
		Globals.debug("Gstreamer bus error:", str(error), str(debug))
		Globals.debug("Domain: %s, Code: %s" % (error.domain, error.code))
		Globals.debug("Message:", error.message)
		
		if error.domain == gst.STREAM_ERROR and Globals.DEBUG_GST:
			self.DumpDotFile()
		
		self.emit("gst-bus-error", str(error), str(debug))

	#_____________________________________________________________________
	
	def DumpDotFile(self):
		basepath, ext = os.path.splitext(self.projectfile)
		name = "jokosher-pipeline-" + os.path.basename(basepath)
		gst.DEBUG_BIN_TO_DOT_FILE_WITH_TS(self.mainpipeline, gst.DEBUG_GRAPH_SHOW_ALL, name)
		Globals.debug("Dumped pipeline to DOT file:", name)
		Globals.debug("Command to render DOT file: dot -Tsvg -o pipeline.svg <file>")
	
	#_____________________________________________________________________
	
	def SaveProjectFile(self, path=None, backup=False):
		"""
		Saves the Project and its children as an XML file
		to the path specified by file.
		
		Parameters:
			path -- path to the Project file.
		"""
		
		if not path:
			if not self.projectfile:
				raise Exception("No save path specified!")
			path = self.projectfile
		
		if not self.audio_path:
			self.audio_path = os.path.join(os.path.dirname(path), "audio")
		if not self.levels_path:
			self.levels_path = os.path.join(os.path.dirname(path), "levels")
			
		if os.path.exists(self.audio_path):
			if not os.path.isdir(self.audio_path):
				raise Exception("Audio save location is not a directory")
		else:
			os.mkdir(self.audio_path)
		
		if os.path.exists(self.levels_path):
			if not os.path.isdir(self.levels_path):
				raise Exception("Levels save location is not a directory")
		else:
			os.mkdir(self.levels_path)
		
		if not path.endswith(".jokosher"):
			path = path + ".jokosher"
			
		#sync the transport's mode with the one which will be saved
		self.transportMode = self.transport.mode
		
		if not backup:
			self.__unsavedChanges = False
			#purge main undo stack so that it will not prompt to save on exit
			self.__savedUndoStack.extend(self.__undoStack)
			self.__undoStack = []
			#purge savedRedoStack so that it will not prompt to save on exit
			self.__redoStack.extend(self.__savedRedoStack)
			self.__savedRedoStack = []
			
			# delete the incremental file since its all safe on disk now
			basepath, ext = os.path.splitext(self.projectfile)
			incr_path = basepath + self.INCREMENTAL_SAVE_EXT
			try:
				if os.path.exists(incr_path):
					os.remove(incr_path)
			except OSError:
				Globals.debug("Removal of .incremental failed! Next load we will try to restore unrestorable state!")
		
		doc = xml.Document()
		head = doc.createElement("JokosherProject")
		doc.appendChild(head)
		
		head.setAttribute("version", Globals.VERSION)
		
		params = doc.createElement("Parameters")
		head.appendChild(params)
		
		items = ["viewScale", "viewStart", "name", "name_is_unset", "author", "volume",
		         "transportMode", "bpm", "meter_nom", "meter_denom", "projectfile"]
		
		Utils.StoreParametersToXML(self, doc, params, items)
		
		notesNode = doc.createElement("Notes")
		head.appendChild(notesNode)
		
		# use repr() because XML will not preserve whitespace charaters such as \n and \t.
		notesNode.setAttribute("text", repr(self.notes))
			
		undo = doc.createElement("Undo")
		head.appendChild(undo)
		for action in self.__savedUndoStack:
			actionXML = doc.createElement("Action")
			undo.appendChild(actionXML)
			action.StoreToXML(doc, actionXML)
			
		redo = doc.createElement("Redo")
		head.appendChild(redo)
		for action in self.__redoStack:
			actionXML = doc.createElement("Action")
			redo.appendChild(actionXML)
			action.StoreToXML(doc, actionXML)
			
		for instr in self.instruments:
			instr.StoreToXML(doc, head)
			
		for instr in self.graveyard:
			instr.StoreToXML(doc, head, graveyard=True)
		
		try:
			#append "~" in case the saving fails
			gzipfile = gzip.GzipFile(path +"~", "w")
			gzipfile.write(doc.toprettyxml())
			gzipfile.close()
		except:
			os.remove(path + "~")
		else:
			#if the saving doesn't fail, move it to the proper location
			if os.path.exists(path):
				os.remove(path)
			os.rename(path + "~", path)		
		
		self.emit("undo")
	
	#_____________________________________________________________________
	
	def SaveIncrementalAction(self, action):
		if self.isDoingIncrementalRestore:
			return
		
		if self.__performingUndo or self.__performingRedo:
			return
		
		path, ext = os.path.splitext(self.projectfile)
		filename = path + self.INCREMENTAL_SAVE_EXT
		
		if self.hasDoneIncrementalSave:
			incr_file = open(filename, "a")
		else:
			# if we haven't performed an incremental save yet,
			# the existing .incremental file is old, so overwrite it.
			incr_file = open(filename, "w")
			self.hasDoneIncrementalSave = True
		
		incr_file.write(action.StoreToString())
		incr_file.write(self.INCREMENTAL_SAVE_DELIMITER)
		
		incr_file.close()
		
		self.SetUnsavedChanges()
		self.emit("incremental-save")
	
	#_____________________________________________________________________
	
	def CanDoIncrementalRestore(self):
		path, ext = os.path.splitext(self.projectfile)
		filename = path + self.INCREMENTAL_SAVE_EXT
		return os.path.exists(filename)	
	
	#_____________________________________________________________________
	
	def DoIncrementalRestore(self):
		"""
		Loads all the actions from the .incremental file and executes them
		to restore the project's state.
		"""
		
		if self.hasDoneIncrementalSave:
			Globals.debug("Cannot do incremental restore after incremental save.")
			return False
		
		path, ext = os.path.splitext(self.projectfile)
		filename = path + self.INCREMENTAL_SAVE_EXT
		
		save_action_list = []
		
		if os.path.isfile(filename):
			incr_file = open(filename, "r")
			filetext = incr_file.read()
			incr_file.close()
			for incr_xml in filetext.split(self.INCREMENTAL_SAVE_DELIMITER):
				incr_xml = incr_xml.strip()
				if incr_xml:
					incr_action = IncrementalSave.LoadFromString(incr_xml)
					save_action_list.append(incr_action)
		
		self.isDoingIncrementalRestore = True
		try:
			IncrementalSave.FilterAndExecuteAll(save_action_list, self)
		except:
			Globals.debug("Exception while restoring incremental save.",
						"Project state is surely out of sync with .incremental file")
			raise
		
		# set hasDoneIncrementSave to True because project is now in sync with .incremental file
		# i.e. we don't have to destory the .incremental file because the states match up.
		self.hasDoneIncrementalSave = True
		self.isDoingIncrementalRestore = False
		return True
		
	#_____________________________________________________________________

	def CloseProject(self):
		"""
		Closes down this Project.
		"""
		
		# when closing the file, the user chooses to either save, or discard
		# in either case, we don't need the incremental save file anymore
		path, ext = os.path.splitext(self.projectfile)
		filename = path + self.INCREMENTAL_SAVE_EXT
		try:
			if os.path.exists(filename):
				os.remove(filename)
		except OSError:
			Globals.debug("Removal of .incremental failed! Next load we will try to restore unrestorable state!")
		
		for file in self.deleteOnCloseAudioFiles:
			if os.path.exists(file):
				Globals.debug("Deleting copied audio file:", file)
				os.remove(file)
		self.deleteOnCloseAudioFiles = []
		
		self.mainpipeline.set_state(gst.STATE_NULL)
		
	#_____________________________________________________________________
	
	def Undo(self):
		"""
		Attempts to revert the last user action by popping an action
		from the undo stack and executing it.
		"""
		self.__performingUndo = True
		
		if len(self.__undoStack):
			cmd = self.__undoStack.pop()
			self.ExecuteAction(cmd)
			
		elif len(self.__savedUndoStack):
			self.__savedUndo = True
			cmd = self.__savedUndoStack.pop()
			self.ExecuteAction(cmd)
			self.__savedUndo = False
			
		self.__performingUndo = False
		
		# __performingUndo must be False for project to log
		inc = IncrementalSave.Undo()
		self.SaveIncrementalAction(inc)
	
	#_____________________________________________________________________
	
	def Redo(self):
		"""
		Attempts to redo the last undone action.
		"""
		self.__performingRedo = True
		
		if len(self.__savedRedoStack):
			self.__savedUndo = True
			cmd = self.__savedRedoStack.pop()
			self.ExecuteAction(cmd)
			self.__savedUndo = False
			
		elif len(self.__redoStack):
			cmd = self.__redoStack.pop()
			self.ExecuteAction(cmd)
			
		self.__performingRedo = False
		
		# __performingRedo must be False for project to log
		inc = IncrementalSave.Redo()
		self.SaveIncrementalAction(inc)

	#_____________________________________________________________________
	
	def AppendToCurrentStack(self, object):
		"""
		Appends the action specified by object onto the relevant
		undo/redo stack.
		
		Parameters:
			object -- action to be added to the undo/redo stack
		"""
		if self.__savedUndo and self.__performingUndo:
			self.__savedRedoStack.append(object)
		elif self.__savedUndo and self.__performingRedo:
			self.__savedUndoStack.append(object)
		elif self.__performingUndo:
			self.__redoStack.append(object)
		elif self.__performingRedo:
			self.__undoStack.append(object)
		else:
			self.__undoStack.append(object)
			self.__redoStack = []
			#if we have undone anything that was previously saved
			if len(self.__savedRedoStack):
				self.__savedRedoStack = []
				#since there is no other record that something has 
				#changed after savedRedoStack is purged
				self.__unsavedChanges = True
		self.emit("undo")
	
	#_____________________________________________________________________
	
	def NewAtomicUndoAction(self):
		"""
		Creates a new AtomicUndoAction and adds to the
		appropriate undo/redo stack for this project.
		
		Return:
			The newly created AtomicUndoAction instance.
		"""
		undoAction = UndoSystem.AtomicUndoAction()
		self.AppendToCurrentStack(undoAction)
		return undoAction
		
	#_____________________________________________________________________
	
	def CheckUnsavedChanges(self):
		"""
		Uses boolean self.__unsavedChanges and Undo/Redo to 
		determine if the program needs to save anything on exit.
		
		Return:
			True -- there's unsaved changes, undoes or redoes
			False -- the Project can be safely closed.
		"""
		return self.__unsavedChanges or \
			len(self.__undoStack) > 0 or \
			len(self.__savedRedoStack) > 0
	
	#_____________________________________________________________________
	
	def SetUnsavedChanges(self):
		self.__unsavedChanges = True
		self.emit("undo") 
		
	#_____________________________________________________________________
	
	def CanPerformUndo(self):
		"""
		Whether it's possible to perform an undo operation.
		
		Returns:
			True -- there is another undo command in the stack that can be performed.
			False -- there are no available undo commands.
		"""
		return bool(len(self.__undoStack) or len(self.__savedUndoStack))
	
	#_____________________________________________________________________
	
	def CanPerformRedo(self):
		"""
		Whether it's possible to perform an redo operation.
		
		Returns:
			True -- there is another redo command in the stack that can be performed.
			False -- there are no available redo commands.
		"""
		return bool(len(self.__redoStack) or len(self.__savedRedoStack))
	
	#_____________________________________________________________________
	
	def ExecuteAction(self, undoAction):
		"""
		Executes an AtomicUndoAction object, reverting all operations stored
		in it.
			
		Parameters:
			undoAction -- the instance of AtomicUndoAction to be executed.
		"""
		newUndoAction = self.NewAtomicUndoAction()
		for cmdList in reversed(undoAction.GetUndoCommands()):
			obj = cmdList[0]
			target_object = self.JokosherObjectFromString(obj)
			
			getattr(target_object, cmdList[1])(_undoAction_=newUndoAction, *cmdList[2])

	#_____________________________________________________________________
	
	def JokosherObjectFromString(self, string):
		"""
		Converts a string used to serialize references to Project, Instrument
		and Event instances into a reference to the actual object.
		
		Parameters:
			string -- The string to convert such as "P" for project or "I2" for instrument with ID equal to 2.
		"""
		if string[0] == "P":		# Check if the object is a Project
			return self
		elif string[0] == "I":		# Check if the object is an Instrument
			id = int(string[1:])
			for instr in self.instruments:
				if instr.id == id:
					return instr
		elif string[0] == "E":		# Check if the object is an Event
			id = int(string[1:])
			for instr in self.instruments:
				for event in instr.events:
					if event.id == id:
						return event
				for event in instr.graveyard:
					if event.id == id:
						return event
				
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("SetBPM", "temp")
	def SetBPM(self, bpm):
		"""
		Changes the current beats per minute.
		
		Parameters:
			bpm -- value of the new beats per minute.
		"""
		self.temp = self.bpm
		if self.bpm != bpm:
			self.bpm = bpm
			#FIXME: find a better way to do project.PrepareClick() it doesn't take a really long time with large bpm
			self.PrepareClick()
			self.emit("bpm")
	
	#_____________________________________________________________________

	@UndoSystem.UndoCommand("SetMeter", "temp", "temp1")
	def SetMeter(self, nom, denom):
		"""
		Changes the current time signature.
		
		Example:
			nom = 3
			denom = 4
			
			would result in the following signature:
				3/4
		
		Parameters:
			nom -- new time signature nominator.
			denom --new time signature denominator.
		"""
		self.temp = self.meter_nom
		self.temp1 = self.meter_denom
		
		if self.meter_nom != nom or self.meter_denom != denom:
			self.meter_nom = nom
			self.meter_denom = denom
			self.emit("time-signature")
			
	#_____________________________________________________________________
	
	def AddInstruments(self, instrTuples):
		"""
		Adds one or more instruments to the Project, and ensures that
		they are all appended to the undo stack as a single atomic action.
		
		Parameters:
			instrTuples -- a list of tuples containing name and type
					that will be passed to AddInstrument().
			
		Returns:
			A list of the added Instruments.
		"""
		
		undoAction = self.NewAtomicUndoAction()
		instrList = []
		for name, type in instrTuples:
			instr = self.AddInstrument(name, type, _undoAction_=undoAction)
			instrList.append(instr)
		return instrList
	
	#_____________________________________________________________________
	
	def DeleteInstrumentsOrEvents(self, instrumentOrEventList):
		"""
		Removes the given instruments the Project.
		
		Parameters:
			instrumentList -- a list of Instrument instances to be removed.
		"""
		undoAction = self.NewAtomicUndoAction()
		for instrOrEvent in instrumentOrEventList:
			if isinstance(instrOrEvent, Instrument.Instrument):
				self.DeleteInstrument(instrOrEvent.id, _undoAction_=undoAction)
			elif isinstance(instrOrEvent, Event.Event):
				instrOrEvent.instrument.DeleteEvent(instrOrEvent.id, _undoAction_=undoAction)
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteInstrument", "temp")
	def AddInstrument(self, name, type):
		"""
		Adds a new instrument to the Project and returns the ID for that instrument.
		
		Considerations:
			In most cases, AddInstruments() should be used instead of this function
			to ensure that the undo actions are made atomic.
		
		Parameters:
			name -- name of the instrument.
			type -- type of the instrument.
			
		Returns:
			The created Instrument object.
		"""
		pixbuf = Globals.getCachedInstrumentPixbuf(type)
		instr = Instrument.Instrument(self, name, type, pixbuf)
		if len(self.instruments) == 0:
			#If this is the first instrument, arm it by default
			instr.isArmed = True
		
		self.temp = instr.id
		self.instruments.append(instr)
		
		self.emit("instrument::added", instr)
		return instr
		
	#_____________________________________________________________________	
	
	@UndoSystem.UndoCommand("ResurrectInstrument", "temp")
	def DeleteInstrument(self, id):
		"""
		Removes the instrument matching id from the Project.
		
		Considerations:
			In most cases, DeleteInstrumentsOrEvents() should be used instead
			of this function to ensure that the undo actions are made atomic.
		
		Parameters:
			id -- unique ID of the instument to remove.
		"""
		
		instrs = [x for x in self.instruments if x.id == id]
		if not instrs:
			raise UndoSystem.CancelUndoCommand()
		
		instr = instrs[0]
		instr.RemoveAndUnlinkPlaybackbin()
		
		self.graveyard.append(instr)
		self.instruments.remove(instr)
		if instr.isSolo:
			self.soloInstrCount -= 1
			self.OnAllInstrumentsMute()
		
		for event in instr.events:
			event.StopGenerateWaveform(False)
			
		self.temp = id
		self.emit("instrument::removed", instr)
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteInstrument", "temp")
	def ResurrectInstrument(self, id):
		"""
		Brings a deleted Instrument back from the graveyard.
		
		Parameters:
			id -- unique ID of the instument to restore.
		"""
		instr = [x for x in self.graveyard if x.id == id][0]
		
		instr.AddAndLinkPlaybackbin()
		
		self.instruments.append(instr)
		if instr.isSolo:
			self.soloInstrCount += 1
			self.OnAllInstrumentsMute()
			
		for event in instr.events:
			if event.isLoading:
				event.GenerateWaveform()
		
		instr.isVisible = True
		self.graveyard.remove(instr)
		self.temp = id
		self.emit("instrument::added", instr)
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("MoveInstrument", "temp", "temp1")
	def MoveInstrument(self, id, position):
		"""
		Move an instrument in the instrument list.
		Used for drag and drop ordering of instruments in InstrumentViewer.py
		
		Parameters:
			id -- unique ID of the instument to restore.
			position -- new position of the instrument inside the instrument 
						pane to the left of the screen.
		"""
		self.temp = id
		instr = [x for x in self.instruments if x.id == id][0]
		self.temp1 = self.instruments.index(instr)
		
		self.instruments.remove(instr)
		self.instruments.insert(position, instr)
		self.emit("instrument::reordered", instr)
	
	#_____________________________________________________________________
	
	def AddInstrumentAndEvents(self, fileList, copyFile=False, undoAction=None):
		"""
		Adds a new instrument of type "audio file" to the project, and adds the
		given files to the new instrument.
		
		Parameters:
			fileList -- the list of paths of the files that should be added.
			copyFile -- True = copy the files to Project's audio directory.
					False = don't copy the files to the Project's audio directory.
		"""
		if not undoAction:
			undoAction = self.NewAtomicUndoAction()
	
		uris = []
		for filename in fileList:
			if filename.find("://"):
				uris.append(filename)
			else:
				# We've been passed a path, so convert it to a URI
				uris.append(PlatformUtils.pathname2url(filename))

		name, type, pixbuf, path = [x for x in Globals.getCachedInstruments() if x[1] == "audiofile"][0]
		instr = self.AddInstrument(name, type, _undoAction_=undoAction)
		instr.AddEventsFromList(0, uris, copyFile, undoAction)
	
	#_____________________________________________________________________
	
	def ClearEventSelections(self):
		"""
		Clears the selection of any events.
		"""
		for instr in self.instruments:
			for event in instr.events:
				event.SetSelected(False)

	#_____________________________________________________________________

	def SelectInstrument(self, instrument=None):
		"""
		Selects an instrument and clears the selection of all other instruments.
		
		Parameters:
			instrument -- Instrument object corresponding to the selected instrument.
		"""
		for instr in self.instruments:
			if instr is not instrument:
				instr.SetSelected(False)
			else:
				instr.SetSelected(True)
			
	#_____________________________________________________________________
	
	def SetViewStart(self, start):
		"""
		Sets the time at which the Project view should start.

		Parameters:
			start -- start time for the view in seconds.
		"""
		start = max(0, min(self.GetProjectLength(), start))
		if self.viewStart != start:
			self.viewStart = start
			self.emit("view-start")
		
	#_____________________________________________________________________
	
	def SetViewScale(self, scale):
		"""
		Sets the scale of the Project view.
		
		Parameters:
			scale -- view scale in pixels per second.
		"""
		self.viewScale = scale
		self.emit("zoom")
		
	#_____________________________________________________________________

	def GetProjectLength(self):
		"""
		Returns the length of the Project.
		
		Returns:
			lenght of the Project in seconds.
		"""
		length = 0
		for instr in self.instruments:
			for event in instr.events:
				size = event.start + max(event.duration, event.loadingLength)
				length = max(length, size)
		return length

	#_____________________________________________________________________
	
	def OnAllInstrumentsMute(self):
		"""
		Mutes all Instruments in this Project.
		"""
		for instr in self.instruments:
			instr.OnMute()
			
	#_____________________________________________________________________
	
	def GenerateUniqueID(self, id = None,  reserve=True):
		"""
		Creates a new unique ID which can be assigned to an new Project object.
		
		Parameters:
			id -- an unique ID proposal. If it's already taken, a new one is generated.
			reserve -- if True, the ID will be recorded and never returned again.
			
		Returns:
			an unique ID suitable for a new Project.
		"""
		if id != None:
			if id in self.___id_list:
				Globals.debug("Error: id", id, "already taken")
			else:
				if reserve:
					self.___id_list.append(id)
				return id
				
		counter = 0
		while True:
			if not counter in self.___id_list:
				if reserve:
					self.___id_list.append(counter)
				return counter
			counter += 1
	
	#_____________________________________________________________________

	def SetVolume(self, volume):
		"""
		Sets the volume of an instrument.
		
		Parameters:
			volume - a value in the range [0,1]
		"""
		self.volume = volume
		for instr in self.instruments:
			instr.UpdateVolume()
		self.emit("volume")

	#_____________________________________________________________________

	def SetLevel(self, level):
		"""
		Sets the current REPORTED level, NOT THE VOLUME!
		
		Parameters:
			level -- a value in the range [0,1]
		"""
		self.level = level

	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("SetTransportMode", "temp")
	def SetTransportMode(self, val):
		"""
		Sets the Mode in the Transportmanager. Used to enable Undo/Redo.
		
		Parameters:
			val -- the mode to display the timeline bar:
					TransportManager.MODE_HOURS_MINS_SECS
					TransportManager.MODE_BARS_BEATS
		"""
		self.temp = self.transport.mode
		self.transport.SetMode(val)

	#_____________________________________________________________________

	def PrepareClick(self):
		"""
		Prepares the click track.
		"""

		self.ClearClickTimes()

		second = 1000000000
		
		# FIXME: currently hard coded to 600 seconds
		length = (600 * second)
		interval = second / (self.bpm/60)
		
		self.clickTrackController.set("volume", 0 * gst.SECOND, 0.0)

		current = 0 + interval

		while current < length:
			self.clickTrackController.set("volume", current-(second / 10), 0.0)
			self.clickTrackController.set("volume", current, 1.0)
			self.clickTrackController.set("volume", current+(second / 10), 0.0)

			current = current + interval

	#_____________________________________________________________________

	def SetClickTrackVolume(self, value):
		"""
		Unmutes and enables the click track.
		
		Parameters:
			value -- The volume of the click track between 0.0 and 1.0
		"""
		if self.clickVolumeValue != value:
			self.clickTrackVolume.set_property("mute", (value < 0.01))
			# convert the 0.0 to 1.0 range to 0.0 to 2.0 range (to let the user make it twice as loud)
			self.clickTrackVolume.set_property("volume", value * 2)
			self.clickVolumeValue = value
			self.emit("click-track", value)

	#_____________________________________________________________________

	def ClearClickTimes(self):
		"""
		Clears the click track controller times.
		"""
		self.clickTrackController.unset_all("volume")
		
	#_____________________________________________________________________
	
	def SetProjectSink(self):
		"""
		Grabs the sink element based on the Global preferences, and sets
		the pipeline to use that sink.
		"""
		
		if self.audioState == self.AUDIO_EXPORTING:
			#we're exporting so some encoders and a filesink are hooked up
			#changing that would mess everything up.
			return
		
		if self.audioState != self.AUDIO_STOPPED:
			self.Stop()
		
		self.levelElement.unlink(self.masterSink)
		self.playbackbin.remove(self.masterSink)
		self.masterSink.set_state(gst.STATE_NULL)
		
		self.masterSink = self.MakeProjectSink()
		self.playbackbin.add(self.masterSink)
		self.levelElement.link(self.masterSink)
	
	#_____________________________________________________________________
	
	def SetProjectSinkDevice(self):
		"""
		Grabs the sink element device based on the Global preferences, and sets
		the pipeline to use that device.
		"""
		if self.audioState != self.AUDIO_EXPORTING and \
		   self.audioState != self.AUDIO_STOPPED:
			self.Stop()
			
		if not self.masterSink:
			return
		
		sinkElement = self.masterSink.sinks().next()
		if hasattr(sinkElement.props, "device"):
			outdevice = Globals.settings.playback["device"]
			Globals.debug("Changing output device: %s" % outdevice)
			sinkElement.set_property("device", outdevice)
		
	#_____________________________________________________________________
	
	def MakeProjectSink(self):
		"""
		Contructs a GStreamer sink element (or bin with ghost pads) for the 
		Project's audio output, according to the Global "audiosink" property.
		
		Return:
			the newly created GStreamer sink element.
		"""
		
		sinkString = Globals.settings.playback["audiosink"]
		if self.currentSinkString == sinkString:
			return self.masterSink
		
		self.currentSinkString = sinkString
		sinkBin = None
		
		try:
			sinkBin = gst.parse_bin_from_description(sinkString, True)
		except gobject.GError:
			Globals.debug("Parsing failed: %s" % sinkString)
			# autoaudiosink is our last resort
			sinkBin = gst.element_factory_make("autoaudiosink")
			Globals.debug("Using autoaudiosink for audio output")
		else:
			Globals.debug("Using custom pipeline for audio sink: %s" % sinkString)
			
			sinkElement = sinkBin.sinks().next()
			if hasattr(sinkElement.props, "device"):
				outdevice = Globals.settings.playback["device"]
				Globals.debug("Output device: %s" % outdevice)
				sinkElement.set_property("device", outdevice)
		
		return sinkBin
		
	#____________________________________________________________________	
	
	def OnCaptureBackendChange(self):
		for instr in self.instruments:
			instr.input = None
			instr.inTrack = -1
	
	#____________________________________________________________________	
	
	def GetInputFilenames(self):
		"""
		Obtains a list of  all filenames that are to be input to
		the pipeline.
		
		Return: 
			a list of  the filenames
		"""
		fileList = []
		for instrument in self.instruments:
			for event in instrument.events:
				fileList.append(event.GetAbsFile())
		return fileList
		
	#____________________________________________________________________	
	
	def GetAudioAndLevelsFilenames(self, include_deleted=False):
		levels_files = set()
		rel_audio_files = set()
		abs_audio_files = set()
		
		if include_deleted:
			instrs = self.instruments + self.graveyard
		else:
			instrs = self.instruments
		
		for instrument in instrs:
			if include_deleted:
				events = instrument.events + instrument.graveyard
			else:
				events = instrument.events
		
			for event in events:
				levels_files.add(event.levels_file)
				if os.path.isabs(event.file):
					abs_audio_files.add(event.file)
				else:
					rel_audio_files.add(event.file)
					
		return abs_audio_files, rel_audio_files, levels_files
	
	#____________________________________________________________________	
	
	def SetName(self, name):
		if self.name != name:
			self.name = name
			self.name_is_unset = False
			inc = IncrementalSave.SetName(name)
			self.SaveIncrementalAction(inc)
			self.emit("name", name)
			
	#____________________________________________________________________	
	
	def SetAuthor(self, author):
		if self.author != author:
			self.author = author
			inc = IncrementalSave.SetAuthor(author)
			self.SaveIncrementalAction(inc)
	
	#____________________________________________________________________	
	
	def SetNotes(self, notes):
		if self.notes != notes:
			self.notes = notes
			inc = IncrementalSave.SetNotes(notes)
			self.SaveIncrementalAction(inc)
	
	#____________________________________________________________________		
#=========================================================================
