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

import pygst
pygst.require("0.10")
import gst
import os, time, shutil
import gobject
import Event
import UndoSystem
from Monitored import Monitored
import Utils

import Globals
import AlsaDevices
import gettext
_ = gettext.gettext

#=========================================================================	

class Instrument(Monitored):
	"""
	This module is the non-gui class the represents Instruments. Instruments
	represent a track of audio that can contain many different sources in sequence.
	It also handles loading and saving Instruments from xml, the gstreamer
	bits for playing and recording events, audio effects plugins, as well as any 
	Instrument specific functionality like; solo, mute, volume, etc.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, project, name, type, pixbuf, id=None):
		"""
		Creates a new instance of Instrument.
		
		Parameters:
			project -- the currently active Project.
			name -- name of the Instrument.
			type -- type of the Instrument.
			pixbuf -- image of the Instrument resource object.
			id -- unique ID value for the Instrument.
		"""
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
		self.volume = 1.0				# Gain of the current instrument in range 0..1
		self.instrType = type			# The type of instrument
		self.effects = []				# List of GStreamer effect elements
		self.pan = 0.0					# pan number (between -100 and 100)
		self.currentchainpreset = None	# current instrument wide chain preset
		
		# Select first input device as default to avoid a GStreamer bug which causes
		# large amounts of latency with the ALSA 'default' device.
		try:
			self.input = AlsaDevices.GetAlsaList("capture").keys()[1]
		except: 
			self.input = "default"
	
		self.inTrack = 0	# Input track to record from
		self.output = ""
		self.recordingbin = None
		self.id = project.GenerateUniqueID(id) #check is id is already being used before setting
		self.isSelected = False			# True if the instrument is currently selected
		
		# GStreamer pipeline elements for this instrument		
		self.volumeElement = gst.element_factory_make("volume", "Instrument_Volume_%d"%self.id)
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

		# Create Effects Bin
		self.effectsBin = gst.element_factory_make("bin", "InstrumentEffects_%d"%self.id)
		self.playbackbin.add(self.effectsBin)
		# Create convert for start of effects bin
		self.effectsBinConvert = gst.element_factory_make("audioconvert", "Start_Effects_Converter_%d"%self.id)
		self.effectsBin.add(self.effectsBinConvert)
		# Create ghostpads for the bin from the audioconvert
		self.effectsBinSink = gst.GhostPad("sink", self.effectsBinConvert.get_pad("sink"))
		self.effectsBin.add_pad(self.effectsBinSink)
		self.effectsBinSrc = gst.GhostPad("src", self.effectsBinConvert.get_pad("src"))
		self.effectsBin.add_pad(self.effectsBinSrc)
		# Link the end of the effects bin to the level element
		self.effectsBin.link(self.volumeElement)
		
		
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

		volbinsink = gst.GhostPad("sink", self.vollac.get_pad("sink"))
		self.volbin.add_pad(volbinsink)
		volbinsrc = gst.GhostPad("src", self.volrac.get_pad("src"))
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

		self.composition.connect("pad-added", self.__PadAddedCb)
		self.composition.connect("pad-removed", self.__PadRemovedCb)
		
		#mute this instrument if another one is solo
		self.OnMute()
		#set the volume element since it depends on the project's volume as well
		self.UpdateVolume()
		
	#_____________________________________________________________________
	
	def __PadAddedCb(self, element, pad):
		"""
		Links a new pad to the rest of the playbackbin when one is created
		by the composition.
		
		Parameters:
			element -- GStreamer element calling this function.
			pad -- newly added pad object.
		"""
		Globals.debug("NEW PAD on instrument %s" % self.name)
		convpad = self.effectsBin.get_compatible_pad(pad, pad.get_caps())
		pad.link(convpad)

	#_____________________________________________________________________

	def __PadRemovedCb(self, element, pad):
		"""
		Removes a GStreamer pad from the specified instrument.
		
		Parameters:
			element -- GStreamer element calling this function.
			pad -- pad to be removed from the Instrument.
		"""
		Globals.debug("pad removed on instrument %s" % self.name)
		self.composition.set_state(gst.STATE_READY)

	#_____________________________________________________________________
	
	def __repr__(self):
		"""
		Creates a representation string of the Instrument.

		Returns:
			a string representing the id and name for this Instrument.
		"""
		return "Instrument [%d] %s"%(self.id, self.name)
		
	#_____________________________________________________________________
		
	def StoreToXML(self, doc, parent, graveyard=False):
		"""
		Converts this Instrument into an XML representation suitable for saving to a file.

		Parameters:
			doc -- the XML document object the Instrument will be saved to.
			parent -- the parent node that the serialized Instrument should
						be added to.
			graveyard -- True if this Instrument is on the graveyard stack,
						and should be serialized as a dead Instrument.
		"""
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
		
		Utils.StoreParametersToXML(self, doc, params, items)
		
		for effect in self.effects:
			globaleffect = doc.createElement("GlobalEffect")
			globaleffect.setAttribute("element", effect.get_factory().get_name())
			ins.appendChild(globaleffect)
		
			propsdict = {}
			for prop in gobject.list_properties(effect):
				if prop.flags & gobject.PARAM_WRITABLE:
					propsdict[prop.name] = effect.get_property(prop.name)
			
			Utils.StoreDictionaryToXML(doc, globaleffect, propsdict)
			
		for ev in self.events:
			ev.StoreToXML(doc, ins)
		for ev in self.graveyard:
			ev.StoreToXML(doc, ins, graveyard=True)

	#_____________________________________________________________________

	def AddEffect(self, effectName):
		"""
		Adds an effect to the pipeline for this Instrument.
		
		Considerations:
			The effect is always placed in the pipeline after any other
			effects that were previously added.
			
		Parameters:
			effectName -- GStreamer element name of the effect to add.
			
		Returns:
			the added effect element.
		"""
		#make the new effect and an audioconvert to go with it
		convert = gst.element_factory_make("audioconvert")
		effectElement = gst.element_factory_make(effectName)
		self.effects.append(effectElement)
		#add both elements to effects bin
		self.effectsBin.add(convert)
		self.effectsBin.add(effectElement)
		
		# The sink pad on the first element to the right of the bin
		externalSinkPad = self.effectsBinSrc.get_peer()
		# The src pad on the last element in the bin
		endSrcPad = self.effectsBinSrc.get_target()
		
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			endSrcPad.set_blocked(True)
		# Unlink the bin from the external element so we can put in a new ghostpad
		self.effectsBinSrc.unlink(externalSinkPad)
		# Remove the old ghostpad
		self.effectsBin.remove_pad(self.effectsBinSrc)
		
		newEffectPad = effectElement.sink_pads().next()
		# Link the last element in the bin with the new effect
		endSrcPad.link(newEffectPad)
		# Link the new element to the new convert
		effectElement.link(convert)
		# Make the audioconvert the new ghostpad
		self.effectsBinSrc = gst.GhostPad("src", convert.get_pad("src"))
		self.effectsBin.add_pad(self.effectsBinSrc)
		self.effectsBinSrc.link(externalSinkPad)
		
		# make the elements' state match the bin's state
		convert.set_state(state)
		effectElement.set_state(state)
		#give it a lambda for a callback that does nothing, so we don't have to wait
		endSrcPad.set_blocked_async(False, lambda x,y: False)
		
		self.StateChanged("effects")
		
		return effectElement
	
	#_____________________________________________________________________
	
	def RemoveEffect(self, effect):
		"""
		Remove the given GStreamer element from the effects bin.
		
		Parameters:
			effect -- GStreamer effect to be removed from this Instrument.
		"""
		if effect not in self.effects:
			Globals.debug("Error: trying to remove an element that is not in the list")
			return
		
		previousConvert = None
		for pad in effect.sink_pads():
			if pad.is_linked():
				previousConvert = pad.get_peer().get_parent()
				break
					
		nextConvert = None
		for pad in effect.src_pads():
			if pad.is_linked():
				nextConvert = pad.get_peer().get_parent()
				break
		
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			previousConvert.get_pad("src").set_blocked(True)
		
		# If we have to remove from the end
		if self.effects[-1] == effect:
			# The sink pad on the first element to the right of the bin
			externalSinkPad = self.effectsBinSrc.get_peer()
			
			# Unlink the bin from the external element so we can put in a new ghostpad
			self.effectsBinSrc.unlink(externalSinkPad)
			# Remove the old ghostpad
			self.effectsBin.remove_pad(self.effectsBinSrc)
			
			previousConvert.unlink(effect)
			
			# Make the audioconvert the new ghostpad
			self.effectsBinSrc = gst.GhostPad("src", previousConvert.get_pad("src"))
			self.effectsBin.add_pad(self.effectsBinSrc)
			self.effectsBinSrc.link(externalSinkPad)
			
		# Else we are removing from the middle or beginning of the list
		else: 
			nextEffect = nextConvert.get_pad("src").get_peer().get_parent()
			nextConvert.unlink(nextEffect)
			
			previousConvert.unlink(effect)
			previousConvert.link(nextEffect)
			
		# Remove and dispose of the two elements
		effect.unlink(nextConvert)
		self.effectsBin.remove(effect)
		self.effectsBin.remove(nextConvert)
		effect.set_state(gst.STATE_NULL)
		nextConvert.set_state(gst.STATE_NULL)
		#remove the effect from our own list
		self.effects.remove(effect)
		
		#give it a lambda for a callback that does nothing, so we don't have to wait
		previousConvert.get_pad("src").set_blocked_async(False, lambda x,y: False)
		
		self.StateChanged("effects")
	
	#_____________________________________________________________________
	
	def ChangeEffectOrder(self, effect, newPosition):
		"""
		Move a given GStreamer element inside the effects bin. This method
		does not swap the element into its new position, it simply shifts all the
		elements between the effect's current position and the new position
		down by one. Since a Gstreamer pipeline is essentially a linked list, this
		"shift" implementation is the fastest way to make one element move to
		a new position without changing the order of any of the others.
		For example if this instrument has five effects which are ordered
		A, B, C, D, E, and I call this method with effect D and a new position
		of 2 the new order will be:  A, D, B, C, E.
		
		Parameters:
			effect -- GStreamer effect to be moved.
			newPosition -- value of the new position inside the effects bin
					the effect will have (with 0 as the first position).
		"""
		if effect not in self.effects:
			Globals.debug("Error: trying to remove an element that is not in the list")
			return
		if newPosition >= len(self.effects):
			Globals.debug("Error: trying to move effect to position past the end of the list")
			return
			
		oldPosition = self.effects.index(effect)
		if oldPosition == newPosition:
			#the effect is already in the proper position
			return
		
		# The effect currently at the position we want to move the given effect to
		newPositionEffect = self.effects[newPosition]
		
		previousConvert = None
		for pad in effect.sink_pads():
			if pad.is_linked():
				previousConvert = pad.get_peer().get_parent()
				break
					
		nextConvert = None
		for pad in effect.src_pads():
			if pad.is_linked():
				nextConvert = pad.get_peer().get_parent()
				break
		
		# The src pad on the last element in the bin
		endSrcPad = self.effectsBinSrc.get_target()
		# check the state and block if we have to
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			endSrcPad.set_blocked(True)
			
		#here's where we unlink everything
		previousConvert.unlink(effect)
		effect.unlink(nextConvert)
		
		if oldPosition > newPosition:
			newPositionPreviousConvert = None
			for pad in newPositionEffect.sink_pads():
				if pad.is_linked():
					newPositionPreviousConvert = pad.get_peer().get_parent()
					break
			
			newPositionPreviousConvert.unlink(newPositionEffect)
			previousConvertSink = previousConvert.get_pad("sink")
			# the "src" pad on the end of the chain of events that is being shifted over
			chainEndPad = previousConvertSink.get_peer()
			chainEndPad.unlink(previousConvertSink)
			
			#here's where we link everything back together in the new order
			newPositionPreviousConvert.link(effect)
			effect.link(previousConvert)
			previousConvert.link(newPositionEffect)
			chainEndPad.link(nextConvert.get_pad("sink"))
		else:
			newPositionNextConvert = None
			for pad in newPositionEffect.src_pads():
				if pad.is_linked():
					newPositionNextConvert = pad.get_peer().get_parent()
					break
					
			newPositionEffect.unlink(newPositionNextConvert)
			nextConvertSrc = nextConvert.get_pad("src")
			chainBeginningPad = nextConvertSrc.get_peer()
			nextConvertSrc.unlink(chainBeginningPad)
			
			previousConvert.get_pad("src").link(chainBeginningPad)
			newPositionEffect.link(nextConvert)
			nextConvert.link(effect)
			effect.link(newPositionNextConvert)
		
		# remove and insert to our own llst so it matches the changes just made
		del self.effects[oldPosition]
		self.effects.insert(newPosition, effect)
		
		#give it a lambda for a callback that does nothing, so we don't have to wait
		endSrcPad.set_blocked_async(False, lambda x,y: False)
		
		self.StateChanged("effects")
	
	#_____________________________________________________________________
	
	def GetRecordingEvent(self):
		"""
		Obtain an Event suitable for recording. *CHECK*
		Returns:
			an Event suitable for recording.
		"""
		event = Event.Event(self)
		event.start = self.project.transport.GetPosition()
		event.isRecording = True
		event.name = _("Recorded audio")
		event.file = "%s_%d_%d.ogg" % (os.path.join(self.path, Globals.FAT32SafeFilename(self.name)), self.id, int(time.time()))
		#must add it to the instrument's list so that an update of the event lane will not remove the widget
		self.events.append(event)
		return event

	#_____________________________________________________________________

	@UndoSystem.UndoCommand("DeleteEvent", "temp")
	def FinishRecordingEvent(self, event):
		"""
		Called to log the adding of this event on the undo stack
		and to properly load the file that has just been recorded.
		
		Parameters:
			event -- Event object that has finished being recorded.
		"""
		event.isRecording = False
		event.GenerateWaveform()
		self.temp = event.id
		self.StateChanged()
	
	#_____________________________________________________________________
	
	def FinalizeRecording(self, event):
		"""
		Called when the recording of an Event has finished.
		
		Parameters:
			event -- Event object that has finished being recorded.
		"""
		#create our undo action to make everything atomic
		undoAction = UndoSystem.AtomicUndoAction()
		#make sure the event will act mormally (like a loaded file) now
		self.FinishRecordingEvent(event, _undoAction_=undoAction)
		# remove all the events behind the recorded event (because we can't have overlapping events.
		self.RemoveEventsUnderEvent(event, undoAction)
		
	#_____________________________________________________________________
	
	def AddEventsFromList(self, start, fileList, copyFile=False, undoAction=None):
		"""
		Adds multiple files to an instrument one after another starting
		at the given start position.
		
		Parameters:
			start -- the offset time in seconds for the first event.
			fileList -- paths to the Event files.
			copyfile --	True = copy the files to Project's audio directory.
						False = don't copy the files to the Project's audio directory.
		"""
		if not fileList:
			return
			
		if not undoAction:
			undoAction = UndoSystem.AtomicUndoAction()
		
		for file in fileList:
			event = self.addEventFromFile(start, file, copyFile, _undoAction_=undoAction)
			event.MoveButDoNotOverlap(event.start)
			event.SetProperties()
			start += event.duration
	
	#_____________________________________________________________________

	@UndoSystem.UndoCommand("DeleteEvent", "temp")
	def addEventFromFile(self, start, file, copyfile=False):
		"""
		Adds an Event from a file to this Instrument.
		
		Parameters:
			start -- the offset time in seconds for the Event.
			file -- path to the Event file.
			copyfile --	True = copy the file to Project's audio directory.
						False = don't copy the file to the Project's audio directory.
						
		Returns:
			the added Event.
		"""
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

		ev = Event.Event(self, file, None, filelabel)
		ev.start = start
		ev.name = name
		self.events.append(ev)
		ev.GenerateWaveform()

		self.temp = ev.id
		
		self.StateChanged()
		
		return ev
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteEvent", "temp")
	def addEventFromURL(self, start, url):
		"""
		Adds an Event from a URL to this Instrument.
		
		Considerations:
			Unlike addEventFromFile, there is no copyfile option here,
			because it's mandatory.
		
		Parameters:
			start -- The offset time in seconds for the Event.
			url -- url of the Event to be added.
			
		Returns:
			the added Event.
		"""
		# no way of knowing whether there's a filename, so make one up
		newfile = "%d_%d" % (self.id, int(time.time()))

		audio_file = os.path.join(self.path, newfile)
		self.project.deleteOnCloseAudioFiles.append(audio_file)
		
		# Create the event now so we can return it, and fill in the file later
		ev = Event.Event(self, audio_file, None, url)
		ev.start = start
		ev.name = os.path.split(audio_file)[1]
		ev.isDownloading = True
		self.events.append(ev)
		
		Globals.debug("Event data downloading...")
		ev.CopyAndGenerateWaveform(url)
		
		self.temp = ev.id
		self.StateChanged()
		
		return ev
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteEvent", "temp")
	def addEventFromEvent(self, start, event):
		"""
		Creates a new Event instance identical to the given Event object
		and adds it to this instrument (for paste functionality).
		
		Parameters:
			start - the offset time in seconds for the new Event.
			event - the Event to be cloned on this instrument.
		"""
		ev = Event.Event(self, event.file)
		ev.start = start
		for i in ["duration", "name", "offset"]:
			setattr(ev, i, getattr(event, i))
		ev.levels = event.levels[:]
		ev._Event__fadePointsDict = event._Event__fadePointsDict.copy()
		ev._Event__UpdateAudioFadePoints()
		
		self.events.append(ev)
		ev.SetProperties()
		ev.MoveButDoNotOverlap(ev.start)
		
		self.temp = ev.id
		self.StateChanged()
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("ResurrectEvent", "temp")
	def DeleteEvent(self, eventid):
		"""
		Removes an Event from this Instrument.
			
		Parameters:
			eventid -- ID of the Event to be removed.
		"""
		event = [x for x in self.events if x.id == eventid][0]
		
		self.graveyard.append(event)
		self.events.remove(event)
		self.composition.remove(event.filesrc)
		event.StopGenerateWaveform(False)
		
		self.temp = eventid
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteEvent", "temp")
	def ResurrectEvent(self, eventid):
		"""
		Brings an Event back from the graveyard.
		
		Parameters:
			eventid -- ID of the Event to be resurrected.
		"""
		event = [x for x in self.graveyard if x.id == eventid][0]
		
		self.events.append(event)
		self.graveyard.remove(event)
		event.CreateFilesource()
		if event.isLoading:
			event.GenerateWaveform()
		
		self.temp = eventid
	
	#_____________________________________________________________________

	def MultipleEventsSelected(self):
		"""
		Confirms whether or not multiple events are selected.
		
		Returns:
			True = multiple Instruments have been selected.
			False = none or just one Instrument has been seleced.
		"""
		multiple = 0
		for ev in self.events:
			if (ev.isSelected):
				multiple += 1
		return (multiple > 1)

	#_____________________________________________________________________

	def JoinEvents(self):
		"""
		Joins together all the selected Events into a single Event.
		"""

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
		"""
		Sets the level of this Instrument.
		
		Considerations:
			This sets the current REPORTED level, NOT THE VOLUME!
		
		Parameters:
			level -- new level value in a [0,1] range.
		"""
		self.level = level
	
	#_____________________________________________________________________

	def SetVolume(self, volume):
		"""
		Sets the volume of this Instrument.
		
		Parameters:
			volume -- new volume value in a [0,1] range.
		"""
		if self.volume != volume:
			self.volume = volume
			self.UpdateVolume()
			self.StateChanged("volume")

	#_____________________________________________________________________
	
	def UpdateVolume(self):
		"""
		Updates the volume property of the gstreamer volume element
		based on this instrument's volume and the project's master volume.
		"""
		volume = self.volume * self.project.volume
		self.volumeElement.set_property("volume", volume)
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("SetName", "temp")
	def SetName(self, name):
		"""
		Sets the Instrument's name so it can be registered in the undo stack.
		
		Parameters:
			name -- string with the name for the Instrument.
		"""
		if self.name != name:
			self.temp = self.name
			self.name = name
			self.StateChanged()
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("ToggleArmed")
	def ToggleArmed(self):
		"""
		Arms/Disarms the Instrument for recording.
		"""
		self.isArmed = not self.isArmed
		self.StateChanged()
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("ToggleMuted", "temp")
	def ToggleMuted(self, wasSolo):
		"""
		Mutes/Unmutes the Instrument.
		
		Parameters:
			wasSolo --	True = the Instrument had solo mode enabled.
						False = the Instrument was not in solo mode.
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
	
	@UndoSystem.UndoCommand("ToggleSolo", "temp")
	def ToggleSolo(self, wasMuted):
		"""
		Mutes/Unmutes the other Instruments in the Project.
		
		Parameters:
			wasMuted --	True = the Instrument was muted.
						False = the Instrument was not muted.
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
	
	@UndoSystem.UndoCommand("SetVisible", "temp")
	def SetVisible(self, visible):
		"""
		Sets whether the Instrument is minimized in the CompactMixView.
		
		Parameters:
			visible --	True = the Instrument should be hidden in the mixing view.
						False = the Instrument should be shown normally in 
								the mixing view.
		"""
		if self.isVisible != visible:
			self.temp = self.isVisible
			self.isVisible = visible
			self.StateChanged()
	
	#_____________________________________________________________________
	
	def SetSelected(self, sel):
		"""
		Sets the Instrument to be highlighted and receive keyboard actions.
		
		Parameters:
			sel -- 	True = the Instrument is currently selected.
					False = the Instrument is not currently selected.
		"""
		# No need to call StateChanged when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.StateChanged()
	
	#_____________________________________________________________________
	
	def OnMute(self):
		"""
		Updates the GStreamer volume element to reflect the mute status.
		"""
		self.checkActuallyIsMuted()
		if self.actuallyIsMuted:
			self.volumeElement.set_property("mute", True)
		else:
			self.volumeElement.set_property("mute", False)
	
	#_____________________________________________________________________
	
	def checkActuallyIsMuted(self):
		"""
		Determines if this Intrument should be muted, by taking into account
		if any other Intruments are muted.
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
		"""
		Creates a playback bin for this Instrument and adds it to the main
		playback pipeline. *CHECK*
		"""
		#make sure our playbackbin is in the same state so the pipeline can continue what it was doing
		status, state, pending = self.project.playbackbin.get_state(0)
		if pending != gst.STATE_VOID_PENDING:
			self.playbackbin.set_state(pending)
		else:
			self.playbackbin.set_state(state)
			
		if not self.playbackbin in list(self.project.playbackbin.elements()):
			self.project.playbackbin.add(self.playbackbin)
			Globals.debug("added instrument playbackbin to adder playbackbin", self.id)
		if not self.playghostpad.get_peer():
			self.playbackbin.link(self.project.adder)
			#give it a lambda for a callback that does nothing, so we don't have to wait
			self.playghostpad.set_blocked_async(False, lambda x,y: False)
			Globals.debug("linked instrument playbackbin to adder (project)")

	#_____________________________________________________________________
	
	def RemoveAndUnlinkPlaybackbin(self):
		"""
		Removes this Instrumen's playback bin from the main playback pipeline. *CHECK*
		"""
		#get reference to pad before removing self.playbackbin from project.playbackbin!
		pad = self.playghostpad.get_peer()
		
		if pad:
			status, state, pending = self.playbackbin.get_state(0)
			if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING or \
					pending == gst.STATE_PAUSED or pending == gst.STATE_PLAYING:
				self.playghostpad.set_blocked(True)
			self.playbackbin.unlink(self.project.adder)
			self.project.adder.release_request_pad(pad)
			Globals.debug("unlinked instrument playbackbin from adder")
		
		if self.playbackbin in list(self.project.playbackbin.elements()):
			self.project.playbackbin.remove(self.playbackbin)
			Globals.debug("removed instrument playbackbin from project playbackbin")
	
	#_____________________________________________________________________

	@UndoSystem.UndoCommand("ChangeType", "temp", "temp2")
	def ChangeType(self, type, name):
		"""
		Changes the Intrument's type and name.
		
		Considerations:
			The given type must be loaded in the Instrument list
			in Globals or the image will not be found.
			
		Parameters:
			type -- new type for this Instrument.
			name -- new name for this Instrument.
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
		"""
		Fills the gst.Controller for this Instrument with its list of fade times.
		"""
		
		Globals.debug("Preparing the controller")
		# set the length of the operation to be the full length of the project
		self.op.set_property("duration", self.project.GetProjectLength() * gst.SECOND)
		self.control.unset_all("volume")
		firstpoint = False
		for ev in self.events:
			if not ev.audioFadePoints:
				#there are no fade points, so just make it 100% all the way through
				for point, vol in ((ev.start, 0.99), (ev.start+ev.duration, 0.99)):
					Globals.debug("FADE POINT: time(%.2f) vol(%.2f)" % (point, vol))
					self.control.set("volume", (point) * gst.SECOND, vol)
				continue
			
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
	
	def RemoveEventsUnderEvent(self, mainEvent, undoAction=None):
		"""
		Deletes and/or trims any events which are between the two given values.
		This is useful for ensuring that a particular section of this instrument in
		totally clear of any audio.
		
		Parameters:
			start -- the start of the interval in seconds
			stop -- the stop of the interval in seconds
		"""
		if not undoAction:
			#init our own undo action so everything is nice and atomic
			undoAction = UndoSystem.AtomicUndoAction()
		
		start = mainEvent.start
		stop = mainEvent.start + max(mainEvent.duration, mainEvent.loadingLength)
		leftTrimEvent = rightTrimEvent = None
		for event in self.events:
			if event is mainEvent:
				continue
			
			eventLeft = event.start
			eventRight = event.start + event.duration
			if start <= eventLeft and eventRight <= stop:
				#this event is in between
				self.DeleteEvent(event.id, _undoAction_=undoAction)
			elif eventLeft < start < eventRight and eventRight <= stop:
				# this event is straddling the start of our interval
				leftTrimEvent = event
			elif start <= eventLeft and eventLeft < stop < eventRight:
				# this event is straddling the stop of our interval
				rightTrimEvent = event
		
		if leftTrimEvent:
			leftPiece = leftTrimEvent.Split(start - leftTrimEvent.start, _undoAction_=undoAction)
			self.DeleteEvent(leftPiece.id, _undoAction_=undoAction)
		if rightTrimEvent:
			rightTrimEvent.Split(stop - rightTrimEvent.start, _undoAction_=undoAction)
			self.DeleteEvent(rightTrimEvent.id, _undoAction_=undoAction)
	
	#_____________________________________________________________________
#=========================================================================	
