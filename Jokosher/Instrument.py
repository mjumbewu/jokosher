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
import PlatformUtils
import os, time, shutil
import urlparse # To split up URI's
import gobject
import Event
import UndoSystem, IncrementalSave
import Utils

import Globals
import gettext
_ = gettext.gettext

#=========================================================================	

class Instrument(gobject.GObject):
	"""
	This module is the non-gui class the represents Instruments. Instruments
	represent a track of audio that can contain many different sources in sequence.
	It also handles loading and saving Instruments from xml, the gstreamer
	bits for playing and recording events, audio effects plugins, as well as any 
	Instrument specific functionality like; solo, mute, volume, etc.
	"""
	
	#_____________________________________________________________________
	
	"""
	Only elements that accept these caps will be work if added to the effects bin.
	This current must be audio/x-raw-float to prevent static from occuring
	when adding LADSPA effects while playing.
	"""
	LADSPA_ELEMENT_CAPS = "audio/x-raw-float, width=(int)32, rate=(int)[ 1, 2147483647 ], channels=(int)1, endianness=(int)BYTE_ORDER"
	
	"""
	Signals:
		"arm" -- This instrument has been armed or dis-armed for recording.
		"effect" -- The effects for this instrument have changed. See below:
			"effect::added" -- An effect was added to this instrument.
			"effect::removed" -- An effect was removed from this instrument.
			"effect::reordered" -- An effect on this instrument has changed its position.
		"event" -- The events for this instrument have changed. The event ID will be passed as a parameter. See below:
			"event::added" -- An event was added to this instrument.
			"event::removed" -- An event was removed from this instrument.
		"image" -- The image for this instrument has changed.
		"mute" -- This instrument has been muted or unmuted.
		"name" -- The name of this instrument has changed.
		"recording-done" -- The event recording on this instrument has finished recording.
		"selected" -- This instrument has been selected or deselected.
		"visible" -- This instrument has been maximised or minimized in the mix view.
		"volume" -- The volume value for this instrument has changed.
	"""
	
	__gsignals__ = {
		"arm"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"effect"		: ( gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_DETAILED, gobject.TYPE_NONE, () ),
		"event"		: ( gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_DETAILED, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,) ),
		"image"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"mute"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"name"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"recording-done"	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"selected"	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"solo"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"visible"	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"volume"		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}
	
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
		gobject.GObject.__init__(self)
		
		self.project = project
		
		self.events = []				# List of events attached to this instrument
		self.graveyard = []			# List of events that have been deleted (kept for undo)
		self.effects = []				# List of GStreamer effect elements
		
		self.name = name			# Name of this instrument
		self.pixbuf = pixbuf			# The icon pixbuf resource
		self.instrType = type		# The type of instrument
		
		self.isArmed = False			# True if the instrument is armed for recording
		self.isMuted = False			# True if the "mute" button is toggled on
		self.actuallyIsMuted = False	# True if the instrument is muted (silent)
		self.isSolo = False			# True if the instrument is solo'd (only instrument active)
		self.isVisible = True			# True if the instrument should be displayed in the mixer views
		self.isSelected = False		# True if the instrument is currently selected
		
		self.level = 0.0				# Current audio level in range 0..1
		self.volume = 1.0			# Gain of the current instrument in range 0..1
		self.pan = 0.0				# pan number (between -100 and 100)
		self.currentchainpreset = None	# current instrument wide chain preset
		self.output = ""
		self.recordingbin = None
		self.id = project.GenerateUniqueID(id)	#check is id is already being used before setting
		
		self.input = None	# the device to use for recording on this instrument.
		self.inTrack = 0	# Input track to record from if device is multichannel.
	
		# CREATE GSTREAMER ELEMENTS #
		self.playbackbin = gst.element_factory_make("bin", "Instrument_%d"%self.id)
		self.volumeElement = gst.element_factory_make("volume", "Instrument_Volume_%d"%self.id)
		self.levelElement = gst.element_factory_make("level", "Instrument_Level_%d"%self.id)
		self.panElement = gst.element_factory_make("audiopanorama", "Instrument_Pan_%d"%self.id)
		self.resample = gst.element_factory_make("audioresample")
		
		self.composition = gst.element_factory_make("gnlcomposition")
		self.silentGnlSource = gst.element_factory_make("gnlsource")		# the default source that makes the silence between the tracks
		self.silenceAudioSource = gst.element_factory_make("audiotestsrc")
		
		self.effectsBin = gst.element_factory_make("bin", "InstrumentEffects_%d"%self.id)
		self.effectsBinConvert = gst.element_factory_make("audioconvert", "Start_Effects_Converter_%d"%self.id)
		self.effectsBinCaps = gst.element_factory_make("capsfilter", "Effects_float_caps_%d"%self.id)
		self.effectsBinCaps.set_property("caps", gst.Caps(self.LADSPA_ELEMENT_CAPS))
		self.effectsBinEndConvert = gst.element_factory_make("audioconvert", "End_Effects_Converter_%d"%self.id)
		
		self.volumeFadeBin = gst.element_factory_make("bin", "Volume_fades_bin")
		self.volumeFadeElement = gst.element_factory_make("volume", "Volume_Fade_Element")
		self.volumeFadeStartConvert = gst.element_factory_make("audioconvert", "Start_fadebin_converter")	
		self.volumeFadeEndConvert = gst.element_factory_make("audioconvert", "End_fadebin_converter")
		self.volumeFadeOperation = gst.element_factory_make("gnloperation", "gnloperation")
		self.volumeFadeController = gst.Controller(self.volumeFadeElement, "volume")
		
		# CREATE GHOSTPADS FOR BINS #
		self.effectsBin.add(self.effectsBinConvert, self.effectsBinCaps, self.effectsBinEndConvert)
		self.effectsBinSink = gst.GhostPad("sink", self.effectsBinConvert.get_pad("sink"))
		self.effectsBin.add_pad(self.effectsBinSink)
		self.effectsBinSrc = gst.GhostPad("src", self.effectsBinEndConvert.get_pad("src"))
		self.effectsBin.add_pad(self.effectsBinSrc)
		
		self.volumeFadeBin.add(self.volumeFadeElement)
		self.volumeFadeBin.add(self.volumeFadeStartConvert)
		self.volumeFadeBin.add(self.volumeFadeEndConvert)
		volumeFadeBinSink = gst.GhostPad("sink", self.volumeFadeStartConvert.get_pad("sink"))
		self.volumeFadeBin.add_pad(volumeFadeBinSink)
		volumeFadeBinSrc = gst.GhostPad("src", self.volumeFadeEndConvert.get_pad("src"))
		self.volumeFadeBin.add_pad(volumeFadeBinSrc)
		
		# SET ELEMENT PROPERTIES #
		self.levelElement.set_property("interval", gst.SECOND / 50)
		self.levelElement.set_property("message", True)
		self.levelElement.set_property("peak-ttl", 0)
		self.levelElement.set_property("peak-falloff", 20)
		
		self.panElement.set_property("panorama", 0)

		self.silenceAudioSource.set_property("wave", 4)	#4 is silence
		
		self.silentGnlSource.set_property("priority", 2 ** 32 - 1)
		self.silentGnlSource.set_property("start", 0)
		self.silentGnlSource.set_property("duration", 1000 * gst.SECOND)
		self.silentGnlSource.set_property("media-start", 0)
		self.silentGnlSource.set_property("media-duration", 1000 * gst.SECOND)
		
		self.volumeFadeOperation.set_property("start", long(0) * gst.SECOND)
		self.volumeFadeOperation.set_property("duration", long(20) * gst.SECOND)
		self.volumeFadeOperation.set_property("priority", 1)
		
		self.volumeFadeController.set_interpolation_mode("volume", gst.INTERPOLATE_LINEAR)
		
		# ADD ELEMENTS TO THE PIPELINE AND/OR THEIR BINS #
		self.playbackbin.add(self.volumeElement, self.levelElement, self.panElement, self.resample)
		self.playbackbin.add(self.composition)
		self.playbackbin.add(self.effectsBin)
		
		self.volumeFadeOperation.add(self.volumeFadeBin)
		self.silentGnlSource.add(self.silenceAudioSource)
		self.composition.add(self.silentGnlSource)
		self.composition.add(self.volumeFadeOperation)
		
		# LINK GSTREAMER ELEMENTS #
		self.effectsBinConvert.link(self.effectsBinCaps)
		self.effectsBinCaps.link(self.effectsBinEndConvert)
		
		self.effectsBin.link(self.volumeElement)
		self.volumeElement.link(self.levelElement)
		self.levelElement.link(self.panElement)	
		self.panElement.link(self.resample)

		self.playghostpad = gst.GhostPad("src", self.resample.get_pad("src"))
		self.playbackbin.add_pad(self.playghostpad)
		
		self.volumeFadeStartConvert.link(self.volumeFadeElement)
		self.volumeFadeElement.link(self.volumeFadeEndConvert)
		
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
				"isMuted", "isSolo", "input", "output", "volume",
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
		#make the new effect
		effectElement = gst.element_factory_make(effectName)
		self.effects.append(effectElement)
		#add the element to effects bin
		self.effectsBin.add(effectElement)
		
		# The src pad on the first element (an audioconvert) in the bin
		startSrcPad = self.effectsBinConvert.get_pad("src")
		
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			startSrcPad.set_blocked(True)
			
		lastEffectElement = self.effectsBinEndConvert.get_pad("sink").get_peer().get_parent()
		
		lastEffectElement.unlink(self.effectsBinEndConvert)
		lastEffectElement.link(effectElement)
		effectElement.link(self.effectsBinEndConvert)
		
		# make the element's state match the bin's state
		effectElement.set_state(state)
		#give it a lambda for a callback that does nothing, so we don't have to wait
		startSrcPad.set_blocked_async(False, lambda x,y: False)
		
		self.emit("effect::added")
		
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
		
		for pad in effect.sink_pads():
			if pad.is_linked():
				previousElement = pad.get_peer().get_parent()
				break
		
		for pad in effect.src_pads():
			if pad.is_linked():
				nextElement = pad.get_peer().get_parent()
				break
		
		# The src pad on the first element (an audioconvert) in the bin
		startSrcPad = self.effectsBinConvert.get_pad("src")
		
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			startSrcPad.set_blocked(True)
		
		previousElement.unlink(effect)
		effect.unlink(nextElement)
		previousElement.link(nextElement)
		
		# Remove and dispose of the element
		self.effectsBin.remove(effect)
		effect.set_state(gst.STATE_NULL)
		#remove the effect from our own list
		self.effects.remove(effect)
		
		#give it a lambda for a callback that does nothing, so we don't have to wait
		startSrcPad.set_blocked_async(False, lambda x,y: False)
		
		self.emit("effect::removed")
	
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
		of 1 the new order will be:  A, D, B, C, E.
		
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
		
		for pad in effect.sink_pads():
			if pad.is_linked():
				previousElement = pad.get_peer().get_parent()
				break
		
		for pad in effect.src_pads():
			if pad.is_linked():
				nextElement = pad.get_peer().get_parent()
				break
		
		# The src pad on the first element (an audioconvert) in the bin
		startSrcPad = self.effectsBinConvert.get_pad("src")
		# check the state and block if we have to
		state = self.playbackbin.get_state(0)[1]
		if state == gst.STATE_PAUSED or state == gst.STATE_PLAYING:
			startSrcPad.set_blocked(True)
			
		#here's where we start unlinking and relinking
		previousElement.unlink(effect)
		effect.unlink(nextElement)
		previousElement.link(nextElement)
		
		if oldPosition > newPosition:
			for pad in newPositionEffect.sink_pads():
				if pad.is_linked():
					newPositionPrevious = pad.get_peer().get_parent()
					break
			
			newPositionPrevious.unlink(newPositionEffect)
			newPositionPrevious.link(effect)
			effect.link(newPositionEffect)
		else:
			for pad in newPositionEffect.src_pads():
				if pad.is_linked():
					newPositionNext = pad.get_peer().get_parent()
					break
			
			newPositionEffect.unlink(newPositionNext)
			newPositionEffect.link(effect)
			effect.link(newPositionNext)
			
		# remove and insert to our own llst so it matches the changes just made
		del self.effects[oldPosition]
		self.effects.insert(newPosition, effect)
		
		#give it a lambda for a callback that does nothing, so we don't have to wait
		startSrcPad.set_blocked_async(False, lambda x,y: False)
		
		self.emit("effect:reordered")
	
	#_____________________________________________________________________
	
	def GetRecordingEvent(self):
		"""
		Obtain an Event suitable for recording.
		Returns:
			an Event suitable for recording.
		"""
		event = Event.Event(self)
		event.start = self.project.transport.GetPosition()
		event.isRecording = True
		event.name = _("Recorded audio")
		
		ext = Globals.settings.recording["file_extension"]
		filename = "%s_%d.%s" % (Globals.FAT32SafeFilename(self.name), event.id, ext)
		event.file = filename
		event.levels_file = filename + Event.Event.LEVELS_FILE_EXTENSION
		
		inc = IncrementalSave.NewEvent(self.id, filename, event.start, event.id, recording=True)
		self.project.SaveIncrementalAction(inc)
		
		#must add it to the instrument's list so that an update of the event lane will not remove the widget
		self.events.append(event)
		self.emit("event::added", event)
		return event

	#_____________________________________________________________________

	@UndoSystem.UndoCommand("DeleteEvent", "temp", incremental_save=False)
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
		self.emit("recording-done")
	
	#_____________________________________________________________________
	
	def FinalizeRecording(self, event):
		"""
		Called when the recording of an Event has finished.
		
		Parameters:
			event -- Event object that has finished being recorded.
		"""
		#create our undo action to make everything atomic
		undoAction = self.project.NewAtomicUndoAction()
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
			fileList -- URIs to the Event files.
			copyfile --	True = copy the files to Project's audio directory.
						False = don't copy the files to the Project's audio directory.
		"""
		if not fileList:
			return
			
		if not undoAction:
			undoAction = self.project.NewAtomicUndoAction()
			
		for uri in fileList:
			# Parse the uri, and continue only if it is pointing to a local file
			(scheme, domain, file, params, query, fragment) = urlparse.urlparse(uri, "file", False)
			if scheme == "file":
				file = PlatformUtils.url2pathname(file)
				event = self.addEventFromFile(start, file, copyFile, _undoAction_=undoAction)
			else:
				event = self.addEventFromURL(start, uri, _undoAction_=undoAction)
			
			if event:
				event.MoveButDoNotOverlap(event.start)
				event.SetProperties()
				start += event.duration
	
	#_____________________________________________________________________

	@UndoSystem.UndoCommand("DeleteEvent", "temp", incremental_save=False)
	def addEventFromFile(self, start, file, copyfile=False, name=None, duration=None, levels_file=None):
		"""
		Adds an Event from a file to this Instrument.
		
		Parameters:
			start -- the offset time in seconds for the Event.
			file -- path to the Event file.
			copyfile --	True = copy the file to Project's audio directory.
						False = don't copy the file to the Project's audio directory.
			name -- An optional user visible name. The filename will be used if None.
						
		Returns:
			the added Event.
		"""
		filelabel=file
		event_id = self.project.GenerateUniqueID(None,  reserve=False)
		if not name:
			name = os.path.basename(file)
		root,  extension = os.path.splitext(name.replace(" ", "_"))
		
		if extension:
			newfile = "%s_%d%s" % (root, event_id, extension)
		else:
			newfile = "%s_%d" % (root, event_id)

		if copyfile:
			audio_file = os.path.join(self.project.audio_path, newfile)
			
			try:
				shutil.copyfile(file, audio_file)
			except IOError:
				raise UndoSystem.CancelUndoCommand()
				
			self.project.deleteOnCloseAudioFiles.append(audio_file)
			inc = IncrementalSave.NewEvent(self.id, newfile, start, event_id)
			self.project.SaveIncrementalAction(inc)
			
			file = newfile
		else:
			inc = IncrementalSave.NewEvent(self.id, file, start, event_id)
			self.project.SaveIncrementalAction(inc)

		ev = Event.Event(self, file, event_id, filelabel)
		ev.start = start
		ev.name = name
		self.events.append(ev)
		
		if duration and levels_file:
			ev.duration = duration
			ev.levels_file = levels_file
			ev.levels_list.fromfile(ev.GetAbsLevelsFile())
			# update properties and position when duration changes.
			ev.MoveButDoNotOverlap(ev.start)
			ev.SetProperties()
		else:
			ev.GenerateWaveform()

		self.temp = ev.id
		
		self.emit("event::added", ev)
		
		return ev
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("DeleteEvent", "temp", incremental_save=False)
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
		event_id = self.project.GenerateUniqueID(None,  reserve=False)
		# no way of knowing whether there's a filename, so make one up
		newfile = str(event_id)
		
		audio_file = os.path.join(self.project.audio_path, newfile)
		self.project.deleteOnCloseAudioFiles.append(audio_file)
		
		# Create the event now so we can return it, and fill in the file later
		ev = Event.Event(self, newfile, event_id, url)
		ev.start = start
		ev.name = os.path.split(audio_file)[1]
		ev.isDownloading = True
		self.events.append(ev)
		
		Globals.debug("Event data downloading...")
		result = ev.CopyAndGenerateWaveform(url)
		
		if not result:
			self.events.remove(ev)
			raise UndoSystem.CancelUndoCommand()
		
		inc = IncrementalSave.StartDownload(self.id, url, newfile, start, event_id)
		self.project.SaveIncrementalAction(inc)
		
		self.temp = ev.id
		self.emit("event::added", ev)
		
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
		ev.levels_list = event.levels_list.copy()
		ev._Event__fadePointsDict = event._Event__fadePointsDict.copy()
		ev._Event__UpdateAudioFadePoints()
		
		self.events.append(ev)
		ev.SetProperties()
		ev.MoveButDoNotOverlap(ev.start)
		
		self.temp = ev.id
		self.emit("event::added", ev)
		return ev
	
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
		event.DestroyFilesource()
		event.StopGenerateWaveform(False)
		
		self.temp = eventid
		self.emit("event::removed", event)
	
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
		if event.isLoading or not event.levels_list:
			event.GenerateWaveform()
		
		self.temp = eventid
		self.emit("event::added", event)
	
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
			self.emit("volume")

	#_____________________________________________________________________
	
	def CommitVolume(self):
		"""
		Signal that the volume is no longer volatile. This means we can incrementally save,
		which we didn't do before because the volume was rapidly changing as the user
		moved the mouse.
		"""
		inc = IncrementalSave.InstrumentSetVolume(self.id, self.volume)
		self.project.SaveIncrementalAction(inc)
		
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
			self.emit("name")
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("ToggleArmed")
	def ToggleArmed(self):
		"""
		Arms/Disarms the Instrument for recording.
		"""
		self.isArmed = not self.isArmed
		self.emit("arm")
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("ToggleMuted", "temp")
	def ToggleMuted(self, wasSolo):
		"""
		Mutes/Unmutes the Instrument.
		
		Parameters:
			wasSolo --	True = the Instrument had solo mode enabled.
						False = the Instrument was not in solo mode.
						
		Considerations:
			The signal "mute" is not emitted here because it is emitted in
			the OnMute() function.
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
		self.emit("solo")
	
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
			self.emit("visible")
	
	#_____________________________________________________________________
	
	def SetSelected(self, sel):
		"""
		Sets the Instrument to be highlighted and receive keyboard actions.
		
		Parameters:
			sel -- 	True = the Instrument is currently selected.
					False = the Instrument is not currently selected.
		"""
		# No need to emit signal when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.emit("selected")
	
	#_____________________________________________________________________
	
	def SetInput(self, device, inTrack):
		if device != self.input or inTrack != self.inTrack:
			self.input = device
			self.inTrack = inTrack
			
			inc = IncrementalSave.InstrumentSetInput(self.id, device, inTrack)
			self.project.SaveIncrementalAction(inc)
			
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
		
		self.emit("mute")
	
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
		
		pixbuf = Globals.getCachedInstrumentPixbuf(type)
		if type == self.instrType or not pixbuf:
			raise UndoSystem.CancelUndoCommand()

		for tuple_ in Globals.getCachedInstruments():
			if tuple_[1] == self.instrType:
				if tuple_[0] == self.name:
					#if the instrument name has not been modified by the user, we can replace it.
					self.name = name
					self.emit("name")
				break

		self.instrType = type
		self.pixbuf = pixbuf

		self.emit("image")

	#_____________________________________________________________________

	def PrepareController(self):
		"""
		Fills the gst.Controller for this Instrument with its list of fade times.
		"""
		
		Globals.debug("Preparing the controller")
		# set the length of the operation to be the full length of the project
		self.volumeFadeOperation.set_property("duration", self.project.GetProjectLength() * gst.SECOND)
		self.volumeFadeController.unset_all("volume")
		firstpoint = False
		for ev in self.events:
			if not ev.audioFadePoints:
				#there are no fade points, so just make it 100% all the way through
				for point, vol in ((ev.start, 0.99), (ev.start+ev.duration, 0.99)):
					Globals.debug("FADE POINT: time(%.2f) vol(%.2f)" % (point, vol))
					self.volumeFadeController.set("volume", (point) * gst.SECOND, vol)
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
				self.volumeFadeController.set("volume", (ev.start + point[0]) * gst.SECOND, vol)
		if not firstpoint:
			Globals.debug("Set extra zero fade point")
			self.volumeFadeController.set("volume", 0, 0.99)
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
			undoAction = self.project.NewAtomicUndoAction()
		
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
			leftPiece = leftTrimEvent.SplitEvent(start - leftTrimEvent.start, _undoAction_=undoAction)
			self.DeleteEvent(leftPiece.id, _undoAction_=undoAction)
		if rightTrimEvent:
			rightTrimEvent.SplitEvent(stop - rightTrimEvent.start, _undoAction_=undoAction)
			self.DeleteEvent(rightTrimEvent.id, _undoAction_=undoAction)
	
	#_____________________________________________________________________
#=========================================================================
