#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Instrument.py
#	
#	This module is the non-gui class the represents instruments. instruments
#	represent a track of audio that can contain many different sources in sequence.
#	This module handles loading and saving instruments from xml, the gstreamer
#	bits for playing and recording events, audio effects plugins, as well as any 
#	instrument specific functionality like; solo, mute, volume, etc.
#
#-------------------------------------------------------------------------------

from Event import *
from UndoSystem import *
import pygst
pygst.require("0.10")
import gst
import os
import time
from Monitored import *
from Utils import *
import gobject
import gnomevfs
import Globals
import shutil
import AlsaDevices
import gettext
_ = gettext.gettext

#=========================================================================	

class Instrument(Monitored):
	
	#_____________________________________________________________________
	
	def __init__(self, project, name, type, pixbuf, id=None):
		Monitored.__init__(self)
		
		self.project = project
		
		self.path = ""					# The 'audio' directory for this instrument
		self.events = []				# List of events attached to this instrument
		self.graveyard = []				# List of events that have been deleted (kept for undo)
		self.name = name				# Name of this instrument
		self.pixbuf = pixbuf			# The icon pixbuf resource
		self.isArmed = False			# True if the instrument is armed for recording
		self.isMuted = False			# True if the "mute" button is toggled on
		self.actuallyIsMuted = False	# True if the instrument is muted (silent)
		self.isSolo = False				# True if the instrument is solo'd (only instrument active)
		self.isVisible = True			# True if the instrument should be displayed in the mixer views
		self.level = 0.0				# Current audio level in range 0..1
		self.volume = 0.5				# Gain of the current instrument in range 0..1
		self.instrType = type			# The type of instrument
		self.effects = []				# List of GStreamer effect elements
		self.pan = 0.0					# pan number (between -100 and 100)
		self.effectsbin_obsolete = 0    # set this to 1 when effects bin needs unlinking
		self.currentchainpreset = None	# current instrument wide chain preset
		
		# Select first input device as default to avoid a GStreamer bug which causes
		# large amounts of latency with the ALSA 'default' device.
		try:    
			self.input = AlsaDevices.GetAlsaList("capture").values()[1]
		except: 
			self.input = "default"

		self.inTrack = 0	# Input track to record from
		self.output = ""
		self.recordingbin = None
		self.id = project.GenerateUniqueID(id) #check is id is already being used before setting
		self.isSelected = False			# True if the instrument is currently selected
		
		# GStreamer pipeline elements for this instrument		
		self.volumeElement = gst.element_factory_make("volume", "Instrument_Volume_%d"%self.id)
		self.converterElement = gst.element_factory_make("audioconvert", "Instrument_Converter_%d"%self.id)
		#self.endConverterElement = gst.element_factory_make("audioconvert", "End_Instrument_Converter_%d"%self.id)
		self.levelElement = gst.element_factory_make("level", "Instrument_Level_%d"%self.id)
		self.levelElement.set_property("interval", gst.SECOND / 50)
		self.levelElement.set_property("message", True)
		self.levelElement.set_property("peak-ttl", 0)
		self.levelElement.set_property("peak-falloff", 20)

		self.panElement = gst.element_factory_make("audiopanorama", "Instrument_Pan_%d"%self.id)

		self.playbackbin = gst.element_factory_make("bin", "Instrument_%d"%self.id)

		self.playbackbin.add(self.volumeElement)
		Globals.debug("added volume (instrument)")

		self.playbackbin.add(self.levelElement)
		Globals.debug("added level (instrument)")

		self.playbackbin.add(self.panElement)
		Globals.debug("added audiopanorama (instrument)")


		self.playbackbin.add(self.converterElement)
		Globals.debug("added audioconvert (instrument)")

		self.effectsbin = gst.element_factory_make("bin", "InstrumentEffects_%d"%self.id)
		self.playbackbin.add(self.effectsbin)
		
		self.composition = gst.element_factory_make("gnlcomposition")

		# adding default source - this adds silence betweent the tracks
		self.silenceaudio = gst.element_factory_make("audiotestsrc")
		self.silenceaudio.set_property("wave", 4)	#4 is silence
		
		self.silencesource = gst.element_factory_make("gnlsource")
		self.silencesource.set_property("priority", 2 ** 32 - 1)
		self.silencesource.set_property("start", 0)
		self.silencesource.set_property("duration", 1000 * gst.SECOND)
		self.silencesource.set_property("media-start", 0)
		self.silencesource.set_property("media-duration", 1000 * gst.SECOND)
		self.silencesource.add(self.silenceaudio)
		self.composition.add(self.silencesource)

		self.playbackbin.add(self.composition)
		Globals.debug("added composition (instrument)")
		
		self.resample = gst.element_factory_make("audioresample")
		self.playbackbin.add(self.resample)
		Globals.debug("added audioresample (instrument)")

		# create operation

		self.volbin = gst.element_factory_make("bin", "volbin")

		self.opvol = gst.element_factory_make("volume", "opvol")
		self.volbin.add(self.opvol)

		self.vollac = gst.element_factory_make("audioconvert", "vollac")
		self.volbin.add(self.vollac)
		
		self.volrac = gst.element_factory_make("audioconvert", "volrac")
		self.volbin.add(self.volrac)

		self.vollac.link(self.opvol)
		self.opvol.link(self.volrac)

		for pad in self.vollac.pads():
			if pad.get_direction() == gst.PAD_SINK:
				volbinsink = gst.GhostPad("sink", pad)
				break

		for pad in self.volrac.pads():
			if pad.get_direction() == gst.PAD_SRC:
				volbinsrc = gst.GhostPad("src", pad)
				break

		self.volbin.add_pad(volbinsink)
		self.volbin.add_pad(volbinsrc)

		self.op = gst.element_factory_make("gnloperation", "gnloperation")
		self.op.set_property("start", long(0) * gst.SECOND)
		self.op.set_property("duration", long(20) * gst.SECOND)
		self.op.set_property("priority", 1)

		self.op.add(self.volbin)

		self.composition.add(self.op)
		
		# set controller

		self.control = gst.Controller(self.opvol, "volume")
		self.control.set_interpolation_mode("volume", gst.INTERPOLATE_LINEAR)

		# link elements
		
		#self.converterElement.link(self.volumeElement)
		#print "linked instrument audioconvert to instrument volume"

		self.volumeElement.link(self.levelElement)
		Globals.debug("linked instrument volume to instrument level")

		self.levelElement.link(self.panElement)
		self.panElement.set_property("panorama", 0)
		Globals.debug("linked instrument level to instrument pan")


		self.panElement.link(self.resample)
		Globals.debug("linked instrument pan to instrument resample")
		
		self.playghostpad = gst.GhostPad("src", self.resample.get_pad("src"))
		self.playbackbin.add_pad(self.playghostpad)
		Globals.debug("created ghostpad for instrument playbackbin")
	
		self.AddAndLinkPlaybackbin()

		self.composition.connect("pad-added", self.project.newPad, self)
		self.composition.connect("pad-removed", self.project.removePad, self)
		
		#mute this instrument if another one is solo
		self.OnMute()

		self.effectbinsrc = None
		self.effectbinsink = None
		
	#_____________________________________________________________________
	
	def __repr__(self):
		return "Instrument [%d] %s"%(self.id, self.name)
		
	#_____________________________________________________________________
		
	def StoreToXML(self, doc, parent, graveyard=False):
		if graveyard:
			ins = doc.createElement("DeadInstrument")
		else:
			ins = doc.createElement("Instrument")
		parent.appendChild(ins)
		ins.setAttribute("id", str(self.id))
		
		items = ["name", "isArmed", 
				  "isMuted", "isSolo", "input", "output",
				  "isSelected", "isVisible", "inTrack", "instrType", "pan"]
		
		params = doc.createElement("Parameters")
		ins.appendChild(params)
		
		StoreParametersToXML(self, doc, params, items)
		
		for effect in self.effects:
			globaleffect = doc.createElement("GlobalEffect")
			globaleffect.setAttribute("element", effect.get_factory().get_name())
			ins.appendChild(globaleffect)
		
			propsdict = {}
			for prop in gobject.list_properties(effect):
				if prop.flags & gobject.PARAM_WRITABLE:
					propsdict[prop.name] = effect.get_property(prop.name)
			
			StoreDictionaryToXML(doc, globaleffect, propsdict)
			
		for e in self.events:
			e.StoreToXML(doc, ins)
		for e in self.graveyard:
			e.StoreToXML(doc, ins, graveyard=True)
			
	#_____________________________________________________________________	
			
	def LoadFromXML(self, node):
		
		params = node.getElementsByTagName("Parameters")[0]
		
		LoadParametersFromXML(self, params)
		
		#figure out the instrument's path based on the location of the projectfile
		self.path = os.path.join(os.path.dirname(self.project.projectfile), "audio")
		
		globaleffect = node.getElementsByTagName("GlobalEffect")
		
		for effect in globaleffect:
			elementname = str(effect.getAttribute("element"))
			Globals.debug("Loading effect:", elementname)
			instance = gst.element_factory_make(elementname, "effect")
			
			propsdict = LoadDictionaryFromXML(effect)
			for key, value in propsdict.iteritems():
				instance.set_property(key, value)		
			self.effects.append(instance)
			
		for ev in node.getElementsByTagName("Event"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			e = Event(self, None, id)
			e.LoadFromXML(ev)
			self.events.append(e)
	
		for ev in node.getElementsByTagName("DeadEvent"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			e = Event(self, None, id)
			e.LoadFromXML(ev)
			self.graveyard.append(e)
			#remove it from the composition so it doesnt play
			self.composition.remove(e.filesrc)
		
		#load image from file based on unique type
		#TODO replace this with proper cache manager
		for i in Globals.getCachedInstruments():
			if self.instrType == i[1]:
				self.pixbuf = i[2]
				break
		if not self.pixbuf:
			Globals.debug("Error, could not load image:", self.instrType)
		
		# load pan level
		
		self.panElement.set_property("panorama", self.pan)
			
		#initialize the actuallyIsMuted variable
		self.checkActuallyIsMuted()

	#_____________________________________________________________________

	def AddEffect(self, effectName):
		"""
		Add an effect with the Gstreamer element name effectName
		"""
		# if self.effects is empty, this is the first effect being
		# added, and we need to unlink the converter and volume elements as
		# they had no effectsbin between them
		if not self.effects:
			self.converterElement.unlink(self.volumeElement)
		effectElement = gst.element_factory_make(effectName)
		self.effects.append(effectElement)
		self.StateChanged("effects")
	
	#_____________________________________________________________________
	
	def RemoveEffect(self, effect):
		"""
		Remove the given Gstreamer element from the effects bin.
		"""
		self.effectsbin.remove(effect)
		self.effects.remove(effect)
		if self.effects == []:
			self.effectsbin_obsolete = 1
		
		self.StateChanged("effects")
	
	#_____________________________________________________________________
	
	def getRecordingEvent(self):
		event = Event(self)
		event.start = 0
		event.isRecording = True
		event.name = _("Recorded audio")
		event.file = "%s_%d_%d.ogg"%(os.path.join(self.path, self.name.replace(" ", "_")), self.id, int(time.time()))
		self.events.append(event)
		return event

	#_____________________________________________________________________

	@UndoCommand("DeleteEvent", "temp")
	def finishRecordingEvent(self, event):
		event.isRecording = False
		event.GenerateWaveform()
		self.temp = event.id
		self.StateChanged()
	
	#_____________________________________________________________________

	@UndoCommand("DeleteEvent", "temp")
	def addEventFromFile(self, start, file, copyfile=False):
		''' Adds an event to this instrument, and attaches the specified
			file to it. 
			
			start - The offset time in seconds
			file - file path
			copyfile - if True copy file to project audio dir
		'''
		filelabel=file

		if copyfile:
			basename = os.path.split(file.replace(" ", "_"))[1]
			basecomp = basename.rsplit('.', 1)
			if len(basecomp) > 1:
				newfile = "%s_%d_%d.%s" % (basecomp[0], self.id, int(time.time()), basecomp[len(basecomp)-1])
			else:
				newfile = "%s_%d_%d" % (basecomp[0], self.id, int(time.time()))

			audio_file = os.path.join(self.path, newfile)
			shutil.copyfile(file,audio_file)
			self.project.deleteOnCloseAudioFiles.append(audio_file)
			
			file = audio_file
			name = basename
		else:
			name = file.split(os.sep)[-1]

		e = Event(self, file,None,filelabel)
		e.start = start
		e.name = name
		self.events.append(e)
		e.GenerateWaveform()

		self.temp = e.id
		
		self.StateChanged()
		
		return e
		
	#_____________________________________________________________________
	
	@UndoCommand("DeleteEvent", "temp")
	def addEventFromURL(self, start, url):
		''' Adds an event to this instrument, and downloads the specified
			URL and saves it against this event.
			
			start - The offset time in seconds
			file - file path
			
			NB: there is no copyfile option here, because it's mandatory.
		'''
		
		# no way of knowing whether there's a filename, so make one up
		newfile = "%d_%d" % (self.id, int(time.time()))

		audio_file = os.path.join(self.path, newfile)
		self.project.deleteOnCloseAudioFiles.append(audio_file)
		
		# Create the event now so we can return it, and fill in the file later
		e = Event(self, None, None)
		e.start = start
		self.events.append(e)
		self.temp = e.id

		PRIORITY_DEFAULT = 0 # not wrapped in gnomevfs module yet
		gnomevfs.async.open(url, self.__got_url_handle, gnomevfs.OPEN_READ, 
		  PRIORITY_DEFAULT, [audio_file, start, e])

		return e
	
	#_____________________________________________________________________
	
	def __got_url_handle(self, handle, param, callbackdata):
		"""Called once gnomevfs has an object that we can read data from"""
		audio_file, start, event = callbackdata
		fp = open(audio_file, 'wb')
		handle.read(1024, self.__async_read_callback, [fp, start, event])
	
	#_____________________________________________________________________
	
	def __async_read_callback(self, handle, data, iserror, length, callbackdata):
		fp, start, event = callbackdata
		fp.write(data)
		if iserror is None:
			handle.read(1024, self.__async_read_callback, [fp, start, event])
		else:
			# all data now loaded
			Globals.debug("Event data downloaded")
			event.name = os.path.split(fp.name)[1]
			event.file = fp.name
			fp.close()
			Globals.debug("Creating filesource")
			event.CreateFilesource()
			Globals.debug("Generating waveform")
			event.GenerateWaveform()
			self.StateChanged()
		
	#_____________________________________________________________________
	
	@UndoCommand("DeleteEvent", "temp")
	def addEventFromEvent(self, start, event):
		"""Creates a new event instance identical to the event parameter 
		   and adds it to this instrument (for paste functionality).
		      start - The offset time in seconds
		      event - The event to be recreated on this instrument
		"""
		e = Event(self, event.file)
		e.start = start
		for i in ["duration", "name", "offset"]:
			setattr(e, i, getattr(event, i))
		e.levels = event.levels[:]
		
		self.events.append(e)
		e.SetProperties()
		e.MoveButDoNotOverlap(e.start)
		
		self.temp = e.id
		self.StateChanged()
	
	#_____________________________________________________________________
	
	def DeleteEvent(self, eventid):
		'''Removes an event from this instrument. 
		   It does not register with undo or append it to the graveyard,
		   because both are done by event.Delete()
		'''
		event = [x for x in self.events if x.id == eventid][0]
		event.Delete()
	
	#_____________________________________________________________________

	def MultipleEventsSelected(self):
		''' Confirms whether or not multiple events are selected '''
		multiple = 0
		for ev in self.events:
			if (ev.isSelected):
				multiple += 1
		return (multiple > 1)

	#_____________________________________________________________________

	def JoinEvents(self):
		''' Joins together all the selected events into a single event '''

		eventsToJoin = []
		for ev in self.events:
			if (ev.isSelected):
				eventsToJoin.append(ev)

		# Move them next to each other
		joinPoint = eventsToJoin[0].start + eventsToJoin[0].duration
		for ev in eventsToJoin[1:]:
			ev.Move(ev.start, joinPoint)
			joinPoint = joinPoint + ev.duration

		# Join them into a single event
		while (len(eventsToJoin) > 1):
			eventsToJoin[0].Join(eventsToJoin[1].id)
			eventsToJoin.remove(eventsToJoin[1])
			
	#_____________________________________________________________________

	def SetLevel(self, level):
		""" Note that this sets the current REPORTED level, NOT THE VOLUME!
		"""
		self.level = level
	
	#_____________________________________________________________________

	def SetVolume(self, volume):
		"""Sets the volume of the instrument in the range 0..1
		"""
		if self.volume != volume:
			self.volume = volume
			self.volumeElement.set_property("volume", volume)
			self.StateChanged("volume")

	#_____________________________________________________________________
	
	@UndoCommand("SetName", "temp")
	def SetName(self, name):
		"""
		   Sets the instrument to the given name
		   so it can be registered in the undo stack
		"""
		if self.name != name:
			self.temp = self.name
			self.name = name
			self.StateChanged()
	
	#_____________________________________________________________________
	
	@UndoCommand("ToggleArmed")
	def ToggleArmed(self):
		"""
		   Toggles the instrument to be armed for recording
		"""
		self.isArmed = not self.isArmed
		self.StateChanged()
		
	#_____________________________________________________________________
	
	@UndoCommand("ToggleMuted", "temp")
	def ToggleMuted(self, wasSolo):
		"""
		   Toggles the instrument to be muted
		"""
		self.temp = self.isSolo
		self.isMuted = not self.isMuted
		if self.isSolo and not wasSolo:
			self.isSolo = False
			self.project.soloInstrCount -= 1
			self.project.OnAllInstrumentsMute()
		elif not self.isSolo and wasSolo:
			self.isSolo = True
			self.project.soloInstrCount += 1
			self.project.OnAllInstrumentsMute()
		else:
			self.OnMute()
			
		self.StateChanged()
	
	#_____________________________________________________________________
	
	@UndoCommand("ToggleSolo", "temp")
	def ToggleSolo(self, wasMuted):
		"""
		   Toggles the all the other instruments muted
		"""
		self.temp = self.isMuted
		self.isMuted = wasMuted
		
		if self.isSolo:
			self.isSolo = False
			self.project.soloInstrCount -= 1
		else:
			self.isSolo = True
			self.project.soloInstrCount += 1
		
		self.project.OnAllInstrumentsMute()
		self.StateChanged()
	
	#_____________________________________________________________________
	
	@UndoCommand("SetVisible", "temp")
	def SetVisible(self, visible):
		"""
		   Sets wheather the instrument is minimized in CompactMixView
		"""
		if self.isVisible != visible:
			self.temp = self.isVisible
			self.isVisible = visible
			self.StateChanged()
	
	#_____________________________________________________________________
	
	def SetSelected(self, sel):
		"""
		   Sets the instrument to be highlighted 
		   and receive keyboard actions
		"""
		# No need to call StateChanged when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.StateChanged()
	
	#_____________________________________________________________________
	
	def OnMute(self):
		self.checkActuallyIsMuted()
		if self.actuallyIsMuted:
			self.volumeElement.set_property("mute", True)
		else:
			self.volumeElement.set_property("mute", False)
	
	#_____________________________________________________________________
	
	def checkActuallyIsMuted(self):
		"""Determines if this intrument should be muted
		   by taking into account if any other intruments are muted
		"""
		if self.isMuted:
			self.actuallyIsMuted = True
		elif self.isSolo:
			self.actuallyIsMuted = False
		elif self.project.soloInstrCount > 0:
			self.actuallyIsMuted = True
		else:
			self.actuallyIsMuted = False
	
	#_____________________________________________________________________
	
	def AddAndLinkPlaybackbin(self):
		if not self.playbackbin in list(self.project.playbackbin.elements()):
			self.project.playbackbin.add(self.playbackbin)
			Globals.debug("added instrument playbackbin to adder playbackbin")
		if not self.playghostpad.get_peer():
			self.playbackbin.link(self.project.adder)
			Globals.debug("linked instrument playbackbin to adder (project)")

	#_____________________________________________________________________
	
	def RemoveAndUnlinkPlaybackbin(self):
		#get reference to pad before removing self.playbackbin from project.playbackbin!
		pad = self.playghostpad.get_peer()
		
		if self.playbackbin in list(self.project.playbackbin.elements()):
			self.project.playbackbin.remove(self.playbackbin)
			Globals.debug("removed instrument playbackbin from project playbackbin")
		
		if pad:
			self.playbackbin.unlink(self.project.adder)
			self.project.adder.release_request_pad(pad)
			Globals.debug("unlinked instrument playbackbin from adder")
	
	#_____________________________________________________________________

	def PrepareEffectsBin(self):
		self.project.mainpipeline.set_state(gst.STATE_NULL)
		
		effBinHasKids = False
		
		try:
			self.effectsbin.elements().next()
			effBinHasKids = True
		except:
			effBinHasKids = False
		
		if effBinHasKids:
			for eff in list(self.effectsbin.elements()):
				self.effectsbin.remove(eff)
			
			self.effectsbin.remove_pad(self.effectsbinsink)
			self.effectsbin.remove_pad(self.effectsbinsrc)
	
			self.effectsbinsink = None
			self.effectsbinsrc = None		
		
		aclistnum = 1

		self.aclist = []

		numeffects = len(self.effects)

		for i in range(numeffects):
			aconvert = gst.element_factory_make("audioconvert", "EffectConverter_%d"%aclistnum)
			self.aclist.append(aconvert)
			self.effectsbin.add(aconvert)
			aclistnum += 1
			
		for effect in self.effects:	
			self.effectsbin.add(effect)

		efflink = 1
		acnum = 0
		effectnum = 0

		itertimes = (numeffects * 2) - 1
		
		Globals.debug("link effects")
		for i in range(itertimes):
			if efflink == 1:
				self.effects[effectnum].link(self.aclist[acnum])
				effectnum += 1
				efflink = 0
			else:
				self.aclist[acnum].link(self.effects[effectnum])
				acnum += 1 
				efflink = 1
	
		for pad in self.effects[0].pads():
			if pad.get_direction() == gst.PAD_SINK:
				self.effectsbinsink = gst.GhostPad("sink", pad)
				break

		for pad in self.aclist[-1].pads():
			if pad.get_direction() == gst.PAD_SRC:
				self.effectsbinsrc = gst.GhostPad("src", pad)
				break

		self.effectsbin.add_pad(self.effectsbinsink)
		self.effectsbin.add_pad(self.effectsbinsrc)
		

	#_____________________________________________________________________

	@UndoCommand("ChangeType", "temp", "temp2")
	def ChangeType(self, type, name):
		"""
		   Changes the intruments type to the type specified.
		   The given type must be loaded in the instrument list
		   in Globals or the image will not be found.
		"""
		
		self.temp = self.instrType
		self.temp2 = self.name
		
		pixbufList = [x[2] for x in Globals.getCachedInstruments() if x[1] == type]
		if type != self.instrType and pixbufList:
			pixbuf = pixbufList[0]
		else:
			return

		oldname = self.name.lower().replace(" ","")
		#if the instrument name has not been modified by the user, we can replace it.
		if oldname == self.instrType:
			self.name = name

		self.instrType = type
		self.pixbuf = pixbuf

		self.StateChanged("image")

	#_____________________________________________________________________

	def PrepareController(self):
		"""Fills the gst.Controller for the instrument with its list of fade times."""
		
		Globals.debug("Preparing the controller")
		# set the length of the operation to be the full length of the project
		self.op.set_property("duration", self.project.GetProjectLength() * gst.SECOND)
		self.control.unset_all("volume")
		firstpoint = False
		for ev in self.events:
			for point in ev.audioFadePoints:
				if ev.start + point[0] == 0.0:
					firstpoint = True
				#FIXME: remove vol=0.99 when gst.Controller is fixed to accept many consecutive 1.0 values.
				if point[1] == 1.0:
					vol = 0.99
				else:
					vol = point[1]
				Globals.debug("FADE POINT: time(%.2f) vol(%.2f)" % (ev.start + point[0], vol))
				self.control.set("volume", (ev.start + point[0]) * gst.SECOND, vol)
		if not firstpoint:
			Globals.debug("Set extra zero fade point")
			self.control.set("volume", 0, 0.99)
	#_____________________________________________________________________
	
#=========================================================================	
