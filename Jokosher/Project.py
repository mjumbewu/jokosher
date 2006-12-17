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
import os
import gzip
import urlparse
import shutil
import re

import TransportManager
from UndoSystem import *
import Globals
import xml.dom.minidom as xml
from Instrument import *
from Monitored import *
from Utils import *
from AlsaDevices import *

#=========================================================================

#_____________________________________________________________________

def CreateNew(projecturi, name, author):
	""" Creates a new project.

		projecturi
			The filesystem location for the new project. Currently,
			only file:// URIs are considered valid.
		name
			The name of the project.
		author
			The name of the project's author.
	"""
	if name == "" or author == "" or projecturi == "":
		raise CreateProjectError(4)

	(scheme, domain,folder, params, query, fragment) = urlparse.urlparse(projecturi, "file")

	if scheme!="file":
		# raise "The URI scheme used is invalid." message
		raise CreateProjectError(5)

	filename = (name + ".jokosher")
	projectdir = os.path.join(folder, name)

	try:
		project = Project()
	except Exception, e:
		Globals.debug("Could not make project object:", e)
		raise CreateProjectError(1)

	project.name = name
	project.author = author
	project.projectfile = os.path.join(projectdir, filename)

	if os.path.exists(projectdir):
		raise CreateProjectError(2)
	else: 
		audio_dir = os.path.join(projectdir, "audio")
		try:
			os.mkdir(projectdir)
			os.mkdir(audio_dir)
		except:
			raise CreateProjectError(3)

	project.SaveProjectFile(project.projectfile)

	return project

#_____________________________________________________________________

def LoadFromFile(uri):
	""" Loads a project from a save file on disk.

		uri
			The filesystem location of the project file to load. 
			Currently only file:// URIs are considered valid.
	"""
	p = Project()

	(scheme, domain, projectfile, params, query, fragment) = urlparse.urlparse(uri, "file")
	if scheme != "file":
		# raise "The URI scheme used is invalid." message
		raise OpenProjectError(1,scheme)

	Globals.debug(projectfile)

	if not os.path.exists(projectfile):
		raise OpenProjectError(4,projectfile)

	try:
		gzipfile = gzip.GzipFile(projectfile, "r")
		doc = xml.parse(gzipfile)
	except Exception, e:
		Globals.debug(e.__class__, e)
		# raise "This file doesn't unzip" message
		raise OpenProjectError(2,projectfile)
	
	p.projectfile = projectfile
	
	#only open projects with the proper version number
	version = doc.firstChild.getAttribute("version")
	if version != Globals.VERSION:
		if version == "0.1":
			LoadFromZPOFile(p, doc)
			#copy the project so that the 0.1 is not overwritten when the user clicks save
			withoutExt = os.path.splitext(projectfile)[0]
			shutil.copy(projectfile, "%s.0.1.jokosher" % withoutExt)
			return p
		else:
			if not version:
				version = "0.1" # 0.1 projects had version as element, not attr
			# raise a "this project was created in a different version of Jokosher" message
			raise OpenProjectError(3,version)
	
	params = doc.getElementsByTagName("Parameters")[0]
	
	LoadParametersFromXML(p, params)
	
	# Hack to set the transport mode
	p.transport.SetMode(p.transportMode)
	p.transport.SetBPM(p.transportbpm)
	
	try:
		undo = doc.getElementsByTagName("Undo")[0]
	except IndexError:
		Globals.debug("No saved undo in project file")
	else:
		for n in undo.childNodes:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				cmdList = []
				cmdList.append(str(n.getAttribute("object")))
				cmdList.append(str(n.getAttribute("function")))
				cmdList.extend(LoadListFromXML(n))
				p._Project__savedUndoStack.append(cmdList)
	
	try:
		redo = doc.getElementsByTagName("Redo")[0]
	except IndexError:
		Globals.debug("No saved redo in project file")
	else:
		for n in redo.childNodes:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				cmdList = []
				cmdList.append(str(n.getAttribute("object")))
				cmdList.append(str(n.getAttribute("function")))
				cmdList.extend(LoadListFromXML(n))
				p._Project__redoStack.append(cmdList)
	
	for instr in doc.getElementsByTagName("Instrument"):
		try:
			id = int(instr.getAttribute("id"))
		except ValueError:
			id = None
		i = Instrument(p, None, None, None, id)
		i.LoadFromXML(instr)
		p.instruments.append(i)
		if i.isSolo:
			p.soloInstrCount += 1
	
	for instr in doc.getElementsByTagName("DeadInstrument"):
		try:
			id = int(instr.getAttribute("id"))
		except ValueError:
			id = None
		i = Instrument(p, None, None, None, id)
		i.LoadFromXML(instr)
		p.graveyard.append(i)

	return p

#_____________________________________________________________________

def LoadFromZPOFile(project, doc):
	"""
	   Loads a project from a Jokosher 0.1 (ZPO) project file into
	   the given project object using the XML document doc.
	"""
	def LoadEventFromZPO(self, node):
		"""
		   Loads event properties from a Jokosher 0.1 XML node
		   and saves then to the given self object.
		"""
		params = node.getElementsByTagName("Parameters")[0]
		LoadParametersFromXML(self, params)
		
		try:
			xmlPoints = node.getElementsByTagName("FadePoints")[0]
		except IndexError:
			Globals.debug("Missing FadePoints in Event XML")
		else:
			for n in xmlPoints.childNodes:
				if n.nodeType == xml.Node.ELEMENT_NODE:
					pos = float(n.getAttribute("position"))
					value = float(n.getAttribute("fade"))
					self._Event__fadePointsDict[pos] = value
		
		try:	
			levelsXML = node.getElementsByTagName("Levels")[0]
		except IndexError:
			Globals.debug("No event levels in project file")
			self.GenerateWaveform()
		else: 
			if levelsXML.nodeType == xml.Node.ELEMENT_NODE:
				value = str(levelsXML.getAttribute("value"))
				self.levels = map(float, value.split(","))
		
		if self.isLoading:
			self.GenerateWaveform()

		self._Event__UpdateAudioFadePoints()
		self.CreateFilesource()
	#_____________________________________________________________________
	
	def LoadInstrFromZPO(self, node):
		"""
		   Loads instrument properties from a Jokosher 0.1 XML node
		   and saves then to the given self object.
		"""
		params = node.getElementsByTagName("Parameters")[0]
		LoadParametersFromXML(self, params)
		#work around because in 0.2 self.effects is a list not a string.
		self.effects = []
		
		for ev in node.getElementsByTagName("Event"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			e = Event(self, None, id)
			LoadEventFromZPO(e, ev)
			self.events.append(e)
	
		for ev in node.getElementsByTagName("DeadEvent"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			e = Event(self, None, id)
			LoadEventFromZPO(e, ev)
			self.graveyard.append(e)
		
		pixbufFilename = os.path.basename(self.pixbufPath)
		self.instrType = os.path.splitext(pixbufFilename)[0]
			
		for i in Globals.getCachedInstruments():
			if self.instrType == i[1]:
				self.pixbuf = i[2]
				break
		if not self.pixbuf:
			Globals.debug("Error, could not load image:", self.instrType)
			
		#initialize the actuallyIsMuted variable
		self.checkActuallyIsMuted()
	#_____________________________________________________________________
	
	params = doc.getElementsByTagName("Parameters")[0]
	
	LoadParametersFromXML(project, params)
	
	for instr in doc.getElementsByTagName("Instrument"):
		try:
			id = int(instr.getAttribute("id"))
		except ValueError:
			id = None
		i = Instrument(project, None, None, None, id)
		LoadInstrFromZPO(i, instr)
		project.instruments.append(i)
		if i.isSolo:
			project.soloInstrCount += 1
	
	for instr in doc.getElementsByTagName("DeadInstrument"):
		try:
			id = int(instr.getAttribute("id"))
		except ValueError:
			id = None
		i = Instrument(project, None, None, None, id)
		LoadInstrFromZPO(i, instr)
		project.graveyard.append(i)

	return project

#_____________________________________________________________________	

#=========================================================================

class Project(Monitored):
	
	""" This class maintains all of the information required about single
		project.
	"""
	
	Globals.VERSION = "0.2"	# The project structure version. Will be useful for handling old save files

	#_____________________________________________________________________

	def __init__(self):
		Monitored.__init__(self)
		
		self.author = ""			#the author of this project
		self.name = ""				#the name of this project
		self.projectfile = ""			# the name of the project file, complete with path
		self.___id_list = []			#the list of IDs that have already been used, to avoid collisions
		self.instruments = []		#the list of instruments held by this project
		self.graveyard = []			# The place where deleted instruments are kept, to later be retrieved by undo functions
		#used to delete copied audio files if the event that uses them is not saved in the project file
		self.deleteOnCloseAudioFiles = []	# WARNING: any paths in this list will be deleted on exit!
		self.clipboardList = []		#The list containing the events to cut/copy
		self.viewScale = 25.0		# View scale as pixels per second
		self.viewStart= 0.0			# View offset in seconds
		self.soloInstrCount = 0		#number of solo instruments (to know if others must be muted)
		self.IsPlaying = False		#True if we are currently playing
		self.IsExporting = False		#True if we are currently exporting to a file
		self.clickbpm = 120			#the number of beats per minute that the click track will play
		self.clickEnabled = False		#True is the click track is currently enabled
		self.RedrawTimeLine = False	#True if the timeline's background should be fully redrawn on the next update
		#Keys are instruments which are recording; values are 3-tuples of the event being recorded, the recording bin and bus handler id
		self.recordingEvents = {}	#Dict containing recording information for each recording instrument
		self.volume = 0.5			#The volume setting for the entire project
		self.level = 0.0				#The level of the entire project as reported by the gstreamer element

		# Variables for the undo/redo command system
		self.unsavedChanges = False	#This boolean is to indicate if something which is not on the undo/redo stack needs to be saved
		self.__undoStack = []		#not yet saved undo commands
		self.__redoStack = []		#not yet saved actions that we're undone
		self.__savedUndoStack = []	#undo commands that have already been saved in the project file
		self.__savedRedoStack = []	#redo commands that have already been saved in the project file
		self.__performingUndo = False	#True if we are currently in the process of performing an undo command
		self.__performingRedo = False	#True if we are currently in the process of performing a redo command
		self.__savedUndo = False		#True if we are performing an undo/redo command that was previously saved
		

		
		
		# CREATE GSTREAMER ELEMENTS AND SET PROPERTIES#
		self.mainpipeline = gst.Pipeline("timeline")
		self.playbackbin = gst.Bin("playbackbin")
		self.adder = gst.element_factory_make("adder")
		self.volumeElement = gst.element_factory_make("volume")
		self.masterSink = gst.element_factory_make("alsasink")
		
		self.levelElement = gst.element_factory_make("level", "MasterLevel")
		self.levelElement.set_property("interval", gst.SECOND / 50)
		self.levelElement.set_property("message", True)
		
		#Restrict adder's output caps due to adder bug
		self.levelElementCaps = gst.element_factory_make("capsfilter", "levelcaps")
		caps = gst.caps_from_string("audio/x-raw-int,rate=44100,channels=2,width=16,depth=16,signed=(boolean)true")
		self.levelElementCaps.set_property("caps", caps)
		
		#Set the alsa device for audio output
		outdevice = Globals.settings.playback["devicecardnum"]
		if outdevice == "value":
			try:
				# Select first output device as default to avoid a GStreamer bug which causes
				# large amounts of latency with the ALSA 'default' device.
				outdevice = GetAlsaList("playback").values()[1]
			except:
				outdevice = "default"
		Globals.debug("Output device: %s" % outdevice)
		self.masterSink.set_property("device", outdevice)
		
		# ADD ELEMENTS TO THE PIPELINE AND/OR THEIR BINS #
		self.mainpipeline.add(self.playbackbin)
		Globals.debug("added project playback bin to the pipeline")
		for element in [self.adder, self.volumeElement, self.levelElementCaps, self.levelElement, self.masterSink]:
			self.playbackbin.add(element)
			Globals.debug("added %s to project playbackbin" % element.get_name())

		# LINK GSTREAMER ELEMENTS #
		self.adder.link(self.volumeElement)
		self.volumeElement.link(self.levelElementCaps)
		self.levelElementCaps.link(self.levelElement)
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
		self.transport = TransportManager.TransportManager(self.transportMode, self.mainpipeline)
		
		self.transportbpm = self.transport.bpm

		self.PrepareClick()

		# [DEBUG]
		# This debug block will be removed when we release. If you see this in a release version, we
		# obviously suck. Please email us and tell us about how shit we are.

		try:
			if os.environ['JOKOSHER_DEBUG']:
				import JokDebug
				self.debug = JokDebug.JokDebug()
		except:
			pass
		# [/DEBUG]

	#_____________________________________________________________________
	
	def Play(self, movePlayhead = True, recording=False):
		'''Set all instruments playing'''
		
		if len(self.instruments) > 0:
			Globals.debug("play() in Project.py")
			Globals.debug("current state:", self.mainpipeline.get_state(0)[1].value_name)

			for ins in self.instruments:
				ins.PrepareController()
					
			# And set it going
			self.state_id = self.bus.connect("message::state-changed", self.__PlaybackStateChangedCb, movePlayhead)
			#set to PAUSED so the transport manager can seek first (if needed)
			#the pipeline will be set to PLAY by self.state_changed()
			self.mainpipeline.set_state(gst.STATE_PAUSED)
			
			Globals.debug("just set state to PAUSED")
			
			if recording:
				self.StateChanged("record")
			else:
				self.StateChanged("play")

			# [DEBUG]
			# This debug block will be removed when we release. If you see this in a release version, we
			# obviously suck. Please email us and tell us about how shit we are.
			try:
				if os.environ['JOKOSHER_DEBUG']:
					Globals.debug("Play Pipeline:")
					self.debug.ShowPipelineTree(self.mainpipeline)
			except:
				pass
			# [/DEBUG]

	#_____________________________________________________________________

	def Stop(self, bus=None, message=None):
		'''Stop playing or recording'''

		Globals.debug("Stop pressed, about to set state to READY")
		Globals.debug("current state:", self.mainpipeline.get_state(0)[1].value_name)

		#read pipeline for current position - it will have been read
		#periodically in TimeLine.py but could be out by 1/FPS
		self.transport.QueryPosition()

		#If we've been recording then add new events to instruments
		for instr, (event, bin, handle) in self.recordingEvents.items():
			instr.finishRecordingEvent(event)
			self.bus.disconnect(handle)

		self.TerminateRecording()
			
		Globals.debug("Stop pressed, state just set to READY")

		self.StateChanged("stop")
		# [DEBUG]
		# This debug block will be removed when we release. If you see this in a release version, we
		# obviously suck. Please email us and tell us about how shit we are.
		try:
			if os.environ['JOKOSHER_DEBUG']:
				Globals.debug("PIPELINE AFTER STOP:")
				self.debug.ShowPipelineTree(self.mainpipeline)
		except:
			pass
		# [/DEBUG]
			
		self.transport.Stop()
			
	#_____________________________________________________________________

	def TerminateRecording(self):
		''' Terminate all instruments (used to disregard recording when an 
			error occurs after instruments have started).
		'''
		Globals.debug("Terminating recording.")

		self.mainpipeline.set_state(gst.STATE_READY)
	
		#Relink instruments and stop their recording bins
		for instr, (event, bin, handle) in self.recordingEvents.items():
			try:
				Globals.debug("Removing recordingEvents bin")
				self.mainpipeline.remove(bin)
			except:
				pass #Already removed from another instrument
			Globals.debug("set state to NULL")
			bin.set_state(gst.STATE_NULL)
			instr.AddAndLinkPlaybackbin()

		self.recordingEvents = {}

		self.IsPlaying = False

		self.transport.Stop()

	#_____________________________________________________________________
	
	def Record(self):
		'''Start all selected instruments recording'''

		Globals.debug("pre-record state:", self.mainpipeline.get_state(0)[1].value_name)

		#Add all instruments to the pipeline
		self.recordingEvents = {}
		devices = {}
		for device in GetAlsaList("capture").values():
			devices[device] = []
			for instr in self.instruments:
				if instr.isArmed and instr.input == device:
					instr.RemoveAndUnlinkPlaybackbin()
					devices[device].append(instr)

		for device, recInstruments in devices.items():
			if len(recInstruments) == 0:
				#Nothing to record on this device
				continue

			channelsNeeded = AlsaDevices.GetChannelsOffered(device)

			if channelsNeeded > 1 and not gst.registry_get_default().find_plugin("chansplit"):
				Globals.debug("Channel splitting element not found when trying to record from multi-input device.")
				raise AudioInputsError(2)

			if channelsNeeded > 1: #We're recording from a multi-input device
				recordingbin = gst.Bin()
				src = gst.element_factory_make("alsasrc")
				src.set_property("device", device)
				
				capsfilter = gst.element_factory_make("capsfilter")
				capsString = "audio/x-raw-int,rate=%s" % Globals.settings.recording["samplerate"]
				caps = gst.caps_from_string(capsString)
				capsfilter.set_property("caps", caps)
				
				split = gst.element_factory_make("chansplit")
				
				recordingbin.add(src)
				recordingbin.add(capsfilter)
				recordingbin.add(split)
				src.link(capsfilter)
				capsfilter.link(split)
				
				split.connect("pad-added", self.__RecordingPadAddedCb, recInstruments, recordingbin)
				Globals.debug("Recording in multi-input mode")
			else:
				instr = recInstruments[0]
				event = instr.getRecordingEvent()
				
				encodeString = Globals.settings.recording["fileformat"]
				capsString = "audio/x-raw-int,rate=%s" % Globals.settings.recording["samplerate"]
				pipe = "alsasrc device=%s ! %s ! audioconvert ! level name=recordlevel interval=%d" +\
							" ! audioconvert ! %s ! filesink location=%s"
				pipe %= (device, capsString, event.LEVEL_INTERVAL * gst.SECOND, encodeString, event.file.replace(" ", "\ "))
				
				Globals.debug("Using pipeline: %s" % pipe)
				
				recordingbin = gst.parse_launch("bin.( %s )" % pipe)
				#update the levels in real time
				handle = self.bus.connect("message::element", event.recording_bus_level)
				
				self.recordingEvents[instr] = (event, recordingbin, handle)
				
				Globals.debug("Recording in single-input mode")
				Globals.debug("Using input track: %s" % instr.inTrack)

		Globals.debug("adding recordingbin")
		self.mainpipeline.add(recordingbin)

		#Make sure we start playing from the beginning
		Globals.debug("recordingbin added, setting transport to Stop")
		self.transport.Stop()
		
		#start the pipeline!
		self.Play(recording=True)
		
	#_____________________________________________________________________

	def Export(self, filename, format=None):
		'''
		   Export to location filename with format specified by format variable.
		   Format is a string of the file extension as used in Globals.EXPORT_FORMATS.
		   ie; "ogg", "mp3", "wav".
		   If no format is given, the format will be guessed by the file extension.
		'''
		#NULL is required because some elements will be destroyed when we remove the references
		self.mainpipeline.set_state(gst.STATE_NULL)
		
		if not format:
			format = filename[filename.rfind(".")+1:].lower()
		
		exportingFormatDict = None
		for formatDict in Globals.EXPORT_FORMATS:
			if format == formatDict["extension"]:
				self.IsExporting = True
				exportingFormatDict = formatDict
				break
		if not self.IsExporting:
			Globals.debug("Unknown filetype for export")
			return -1
		
		#remove and unlink the alsasink
		self.playbackbin.remove(self.masterSink, self.levelElement)
		self.levelElementCaps.unlink(self.levelElement)
		self.levelElement.unlink(self.masterSink)
		
		#create filesink
		self.outfile = gst.element_factory_make("filesink", "export_file")
		self.outfile.set_property("location", filename)
		self.playbackbin.add(self.outfile)
		
		#create encoder/muxer
		self.encodebin = gst.gst_parse_bin_from_description("audioconvert ! %s" % exportingFormatDict["pipeline"], True)
		self.playbackbin.add(self.encodebin)
		self.levelElementCaps.link(self.encodebin)
		self.encodebin.link(self.outfile)
			
		#disconnect the bus message handler so the levels don't change
		self.bus.disconnect(self.Mhandler)
		self.bus.disconnect(self.EOShandler)
		self.EOShandler = self.bus.connect("message::eos", self.TerminateExport)
		
		#Make sure we start playing from the beginning
		self.transport.Stop()
		#start the pipeline!
		self.Play(movePlayhead=False)

	#_____________________________________________________________________
	
	def TerminateExport(self, bus=None, message=None):
		""" GStreamer End Of Stream handler. It is connected to eos on 
			mainpipeline while export is taking place.
		"""
		
		if not self.IsExporting:
			return
		else:
			self.IsExporting = False
	
		self.Stop()
		#NULL is required because elements will be destroyed when we delete them
		self.mainpipeline.set_state(gst.STATE_NULL)
	
		self.bus.disconnect(self.EOShandler)
		self.Mhandler = self.bus.connect("message::element", self.__PipelineBusLevelCb)
		self.EOShandler = self.bus.connect("message::eos", self.Stop)
		
		#remove the filesink and encoder
		self.playbackbin.remove(self.outfile, self.encodebin)		
		self.levelElementCaps.unlink(self.encodebin)
			
		#dispose of the elements
		del self.outfile, self.encodebin
		
		#re-add all the alsa playback elements
		self.playbackbin.add(self.masterSink, self.levelElement)
		self.levelElementCaps.link(self.levelElement)
		self.levelElement.link(self.masterSink)
	
	#_____________________________________________________________________
	
	def GetExportProgress(self):
		""" Returns tuple with number of seconds done, and number of total 
			seconds.
		"""
		if self.IsExporting:
			try:
				#total = self.mainpipeline.query_duration(gst.FORMAT_TIME)[0]
				total = self.GetProjectLength() * gst.SECOND
				cur = self.mainpipeline.query_position(gst.FORMAT_TIME)[0]
			except gst.QueryError:
				return (-1, -1)
			else:
				if cur > total:
					total = cur
					self.TerminateExport()
				return (float(cur)/gst.SECOND, float(total)/gst.SECOND)
		else:
			return (100, 100)
		
	#_____________________________________________________________________
	
	def __PlaybackStateChangedCb(self, bus, message, movePlayhead=True):
		"""
		Handler for GStreamer statechange events when the pipline is changing from
		STATE_READY to STATE_PAUSED. Once STATE_PAUSED has been reached, this
		function will tell the transport manager to start playing.
		"""
		Globals.debug("STATE CHANGED")
		change_status, new, pending = self.mainpipeline.get_state(0)
		Globals.debug("-- status:", change_status.value_name)
		Globals.debug("-- pending:", pending.value_name)
		Globals.debug("-- new:", new.value_name)

		#Move forward to playing when we reach paused (check pending to make sure this is the final destination)
		if new == gst.STATE_PAUSED and pending == gst.STATE_VOID_PENDING and not self.IsPlaying:
			bus.disconnect(self.state_id)
			#The transport manager will seek if necessary, and then set the pipeline to STATE_PLAYING
			self.transport.Play(movePlayhead)
			self.IsPlaying = True

	#_____________________________________________________________________
	
	def __PipelineBusLevelCb(self, bus, message):
		"""
		Handler for GStreamer bus messages about the currently reported level
		for the project or any of the instruments.
		"""
		st = message.structure
		
		if st and st.get_name() == "level":
			if not message.src is self.levelElement:
				for instr in self.instruments:
					if message.src is instr.levelElement:
						instr.SetLevel(DbToFloat(st["decay"][0]))
						break
			else:
				self.SetLevel(DbToFloat(st["decay"][0]))
			
		return True

	#_____________________________________________________________________


	def __PipelineBusErrorCb(self, bus, message):
		""" Handler for GStreamer error messages.
		"""
		st = message.structure
		error, debug = message.parse_error()
		
		Globals.debug("Gstreamer bus error:", str(error), str(debug))
		self.StateChanged("gst-bus-error", str(error), str(debug))

	#_____________________________________________________________________
	
	def SaveProjectFile(self, path=None):
		""" Saves the project and its children as an XML file 
			to the path specified by file.
		"""
		
		if not path:
			if not self.projectfile:
				raise "No save path specified!"
			path = self.projectfile
			
		if not path.endswith(".jokosher"):
			path = path + ".jokosher"
			
		#sync the transport's mode with the one which will be saved
		self.transportMode = self.transport.mode
		self.transportbpm = self.transport.bpm
		
		
		self.unsavedChanges = False
		#purge main undo stack so that it will not prompt to save on exit
		self.__savedUndoStack.extend(self.__undoStack)
		self.__undoStack = []
		#purge savedRedoStack so that it will not prompt to save on exit
		self.__redoStack.extend(self.__savedRedoStack)
		self.__savedRedoStack = []
		
		doc = xml.Document()
		head = doc.createElement("JokosherProject")
		doc.appendChild(head)
		
		head.setAttribute("version", Globals.VERSION)
		
		params = doc.createElement("Parameters")
		head.appendChild(params)
		
		items = ["viewScale", "viewStart", "name", "author", "transportMode", "transportbpm"]
		
		StoreParametersToXML(self, doc, params, items)
			
		undo = doc.createElement("Undo")
		head.appendChild(undo)
		for cmd in self.__savedUndoStack:
			e = doc.createElement("Command")
			e.setAttribute("object", cmd[0])
			e.setAttribute("function", cmd[1])
			undo.appendChild(e)
			StoreListToXML(doc, e, cmd[2:], "Parameter")
		
		redo = doc.createElement("Redo")
		head.appendChild(redo)
		for cmd in self.__redoStack:
			e = doc.createElement("Command")
			e.setAttribute("object", cmd[0])
			e.setAttribute("function", cmd[1])
			redo.appendChild(e)
			StoreListToXML(doc, e, cmd[2:], "Parameter")
		
			
		for i in self.instruments:
			i.StoreToXML(doc, head)
			
		for i in self.graveyard:
			i.StoreToXML(doc, head, graveyard=True)
		
		try:
			#append "~" in case the saving fails
			f = gzip.GzipFile(path +"~", "w")
			f.write(doc.toprettyxml())
			f.close()
		except:
			os.remove(path + "~")
		else:
			#if the saving doesn't fail, move it to the proper location
			os.rename(path + "~", path)		
		
		self.StateChanged("undo")
	
	#_____________________________________________________________________

	def CloseProject(self):
		""" Closes down this project.
		"""
		global GlobalProjectObject
		GlobalProjectObject = None
		
		for file in self.deleteOnCloseAudioFiles:
			if os.path.exists(file):
				Globals.debug("Deleting copied audio file:", file)
				os.remove(file)
		self.deleteOnCloseAudioFiles = []
		
		self.instruments = []
		self.metadata = {}
		self.projectfile = ""
		self.projectdir = ""
		self.name = ""
		self.ClearListeners()
		self.transport.ClearListeners()
		
	#_____________________________________________________________________
	
	def Undo(self):
		""" Attempts to revert the last user action by popping an action
			from the undo stack and executing it.
		"""
		self.__performingUndo = True
		
		if len(self.__undoStack):
			cmd = self.__undoStack.pop()
			self.ExecuteCommand(cmd)
			
		elif len(self.__savedUndoStack):
			self.__savedUndo = True
			cmd = self.__savedUndoStack.pop()
			self.ExecuteCommand(cmd)
			self.__savedUndo = False
			
		self.__performingUndo = False
	
	#_____________________________________________________________________
	
	def Redo(self):
		""" Attempts to redo the last undone action.
		"""
		self.__performingRedo = True
		
		if len(self.__savedRedoStack):
			self.__savedUndo = True
			cmd = self.__savedRedoStack.pop()
			self.ExecuteCommand(cmd)
			self.__savedUndo = False
			
		elif len(self.__redoStack):
			cmd = self.__redoStack.pop()
			self.ExecuteCommand(cmd)
			
		self.__performingRedo = False

	#_____________________________________________________________________
	
	def AppendToCurrentStack(self, object):
		""" Appends the action specified by object onto the relevant
			undo/redo stack.
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
				self.unsavedChanges = True
		self.StateChanged("undo")
	
	#_____________________________________________________________________
	
	def CheckUnsavedChanges(self):
		"""Uses boolean self.unsavedChanges and Undo/Redo to 
		   determine if the program needs to save anything on exit
		"""
		return self.unsavedChanges or \
			len(self.__undoStack) > 0 or \
			len(self.__savedRedoStack) > 0
	
	#_____________________________________________________________________
	
	def CanPerformUndo(self):
		"""
		Returns True if there is another undo command in the stack that can be performed, False otherwise.
		"""
		return bool(len(self.__undoStack) or len(self.__savedUndoStack))
	
	#_____________________________________________________________________
	
	def CanPerformRedo(self):
		"""
		Returns True if there is another redo command in the stack that can be performed, False otherwise.
		"""
		return bool(len(self.__redoStack) or len(self.__savedRedoStack))
	
	#_____________________________________________________________________
	
	def ExecuteCommand(self, cmdList):
		""" This function executes the string cmd from the undo/redo stack.
			Commands are made up of a list of which the first two items are
			the object (and it's ID if relevant), and the function to call. 
			The 3rd, 4th, etc. items in the list are the parameters to give to
			the function when it is called.

			i.e.
				["E2", "Move", 1, 2]
				which means 'Call Move(1, 2)' on the Event with ID=2
		"""		
		obj = cmdList[0]
		target_object = None
		if obj[0] == "P":		# Check if the object is a Project
			target_object = self
		elif obj[0] == "I":		# Check if the object is an Instrument
			id = int(obj[1:])
			target_object = [x for x in self.instruments if x.id==id][0]
		elif obj[0] == "E":		# Check if the object is an Event
			id = int(obj[1:])
			for i in self.instruments:
				# First of all see if it's alive on an instrument
				n = [x for x in i.events if x.id==id]
				if not n:
					# If not, check the graveyard on each instrument
					n = [x for x in i.graveyard if x.id==id]
				if n:
					target_object = n[0]
					break
		
		getattr(target_object, cmdList[1])(*cmdList[2:])

	#_____________________________________________________________________
	
	@UndoCommand("DeleteInstrument", "temp")
	def AddInstrument(self, name, type, pixbuf):
		''' Adds a new instrument to the project,
		   and return the ID for that instrument.
		'''
			
		instr = Instrument(self, name, type, pixbuf)
		if len(self.instruments) == 0:
			#If this is the first instrument, arm it by default
			instr.ToggleArmed()
		audio_dir = os.path.join(os.path.split(self.projectfile)[0], "audio")
		instr.path = os.path.join(audio_dir)
		
		self.temp = instr.id
		self.instruments.append(instr)
		
		return instr.id
		
	#_____________________________________________________________________	
	
	@UndoCommand("ResurrectInstrument", "temp")
	def DeleteInstrument(self, id):
		''' Removes the instrument matching id from the project.
			id: Unique ID of the instument to remove.
		'''
		
		instr = [x for x in self.instruments if x.id == id][0]
		
		instr.RemoveAndUnlinkPlaybackbin()
		
		self.graveyard.append(instr)
		self.instruments.remove(instr)
		if instr.isSolo:
			self.soloInstrCount -= 1
			self.OnAllInstrumentsMute()
			
		self.temp = id
	
	#_____________________________________________________________________
	
	@UndoCommand("DeleteInstrument", "temp")
	def ResurrectInstrument(self, id):
		''' Brings a deleted Instrument back from the graveyard.
		'''
		instr = [x for x in self.graveyard if x.id == id][0]
		
		instr.AddAndLinkPlaybackbin()
		
		self.instruments.append(instr)
		if instr.isSolo:
			self.soloInstrCount += 1
			self.OnAllInstrumentsMute()
		instr.isVisible = True
		self.graveyard.remove(instr)
		self.temp = id
		
	#_____________________________________________________________________
	
	@UndoCommand("MoveInstrument", "temp", "temp1")
	def MoveInstrument(self, id, position):
		'''	Move an instrument in the instrument list.
			Used for drag and drop ordering of instruments in
			InstrumentViewer.py
		'''
		self.temp = id
		instr = [x for x in self.instruments if x.id == id][0]
		self.temp1 = self.instruments.index(instr)
		
		self.instruments.remove(instr)
		self.instruments.insert(position, instr)		
	
	#_____________________________________________________________________
	
	def ClearEventSelections(self):
		''' Clears the selection of any events '''
		for instr in self.instruments:
			for ev in instr.events:
				ev.SetSelected(False)

	#_____________________________________________________________________

	def SelectInstrument(self, instrument=None):
		''' Selects instrument and clears the selection of all other instruments. '''
		for instr in self.instruments:
			if instr is not instrument:
				instr.SetSelected(False)
			else:
				instr.SetSelected(True)
			
	#_____________________________________________________________________
	
	def SetViewStart(self, start):
		""" Sets the time at which the project view should start.

			start
				Start time for the view in seconds.
		"""
		if self.viewStart != start:
			self.viewStart = start
			self.RedrawTimeLine = True
			self.StateChanged()
		
	#_____________________________________________________________________
	
	def SetViewScale(self, scale):
		""" Sets the scale of the project view.
		"""
		self.viewScale = scale
		self.RedrawTimeLine = True
		self.StateChanged()
		
	#_____________________________________________________________________

	def GetProjectLength(self):
		""" Returns the length of the project in seconds.
		"""
		length = 0
		for instr in self.instruments:
			for ev in instr.events:
				size = ev.start + max(ev.duration, ev.loadingLength)
				length = max(length, size)
		return length

	#_____________________________________________________________________
	
	def OnAllInstrumentsMute(self):
		""" Mutes all Instruments in this project.
		"""
		for instr in self.instruments:
			instr.OnMute()
			
	#_____________________________________________________________________
	
	def GenerateUniqueID(self, id = None):
		""" Creates a new unique ID which can be assigned to an new 
			project object.
		"""
		if id != None:
			if id in self.___id_list:
				Globals.debug("Error: id", id, "already taken")
			else:
				self.___id_list.append(id)
				return id
				
		counter = 0
		while True:
			if not counter in self.___id_list:
				self.___id_list.append(counter)
				return counter
			counter += 1
	
	#_____________________________________________________________________

	def SetVolume(self, volume):
		"""Sets the volume of the instrument in the range 0..1
		"""
		self.volume = volume
		self.volumeElement.set_property("volume", volume)

	#_____________________________________________________________________

	def SetLevel(self, level):
		""" Note that this sets the current REPORTED level, NOT THE VOLUME!
		"""
		self.level = level

	#_____________________________________________________________________

	def ValidateProject(self):
		""" Checks that the project is valid - i.e. that of the files and 
			images that it references can be found.

			Returns
				True if the project is valid, False if not.
		"""
		unknownfiles=[]
		unknownimages=[]

		for instr in self.instruments:
			for ev in instr.events:
				if (ev.file!=None) and (not os.path.exists(ev.file)) and (not ev.file in unknownfiles):
					unknownfiles.append(ev.file)
		if len(unknownfiles)>0 or len(unknownimages)>0:
			raise InvalidProjectError(unknownfiles,unknownimages)

		return True
	
	#_____________________________________________________________________
	
	@UndoCommand("SetTransportMode", "temp")
	def SetTransportMode(self, val):
		"""
		   Sets the Mode in the Transportmanager. Used to enable Undo/Redo.
		"""
		self.temp = self.transport.mode
		self.transport.SetMode(val)

	#_____________________________________________________________________

	def PrepareClick(self):
		'''Prepare the click track'''

		self.ClearClickTimes()

		second = 1000000000
		
		# FIXME: currently hard coded to 600 seconds
		length = (600 * second)
		interval = second / (self.transport.bpm/60)
		
		self.clickTrackController.set("volume", 0 * gst.SECOND, 0.0)

		current = 0 + interval

		while current < length:
			self.clickTrackController.set("volume", current-(second / 10), 0.0)
			self.clickTrackController.set("volume", current, 1.0)
			self.clickTrackController.set("volume", current+(second / 10), 0.0)

			current = current + interval

	#_____________________________________________________________________

	def EnableClick(self):
		'''Enable the click track'''
	
		self.clickTrackVolume.set_property("mute", False)
		self.clickEnabled = True

	#_____________________________________________________________________

	def DisableClick(self):
		'''Disable the click track'''
	
		self.clickTrackVolume.set_property("mute", True)
		self.clickEnabled = False

	#_____________________________________________________________________

	def ClearClickTimes(self):
		'''Clear the click track controller times'''
		self.clickTrackController.unset_all("volume")


#=========================================================================
	
class OpenProjectError(EnvironmentError):
	def __init__(self, errno, info = None):
		""" Error Numbers:
		   1) Invalid uri passed for the project file
		   2) Unable to unzip the project
		   3) Project created by a different version of Jokosher 
		If a version string is given, it means the project file was created by
		another version of Jokosher. That version is specified in the string.
		   4) Project file doesn't exist
		"""
		EnvironmentError.__init__(self)
		self.info = info
		self.errno = errno
		
#=========================================================================

class CreateProjectError(Exception):
	def __init__(self, errno):
		"""Error numbers:
		   1) Unable to create a project object
		   2) Path for project file already exists
		   3) Unable to create file. (Invalid permissions, read-only, or the disk is full)
		   4) Invalid path, name or author
		   5) Invalid uri passed for the project file
		"""
		Exception.__init__(self)
		self.errno=errno

#=========================================================================

class AudioInputsError(Exception):
	def __init__(self, errno):
		"""Error numbers:
		   1) No recording channels found
		   2) Sound card is not capable of multiple simultanious inputs
		   3) Channel splitting element not found
		"""
		Exception.__init__(self)
		self.errno = errno

#=========================================================================

class InvalidProjectError(Exception):
	def __init__(self, missingfiles,missingimages):
		Exception.__init__(self)
		self.files=missingfiles
		self.images=missingimages

#=========================================================================


GlobalProjectObject = None
