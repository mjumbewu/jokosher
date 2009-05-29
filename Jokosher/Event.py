#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Event.py
#	
#	This module is the non-gui class the represents events. Events
#	represent a piece of audio such as a file or something that was recorded.
#	This module handles loading and saving events from xml, the gstreamer
#	bits event properties as well as any event specific functionality like;
#	audio fades, splits, joins, trims, waveform levels, etc.
#
#-------------------------------------------------------------------------------

import xml.dom.minidom as xml
import os, sys, os.path
import pygst
pygst.require("0.10")
import gst, gobject
import Utils, LevelsList
import UndoSystem, IncrementalSave
import Globals
import gettext
import urllib
import PlatformUtils

from elements.singledecodebin import SingleDecodeBin
_ = gettext.gettext

#=========================================================================

class Event(gobject.GObject):
	"""
	This class handles maintaing the information for a single audio 
	event, normally, a fragment of a recorded file.

	Signals:
		"waveform" -- The waveform date for this event has changed.
		"position" -- The starting position of this event has changed.
		"length" -- The length of this event has changed.
		"corrupt" -- The audio file for this event is not playable. Two strings with detailed information are sent.
		"loading" -- Loading has started or completed.

	"""
	__gsignals__ = {
		"waveform" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"position" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"length" 		: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"corrupt" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,)),
		"loading" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () ),
		"selected" 	: ( gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, () )
	}

	""" The level sample interval in seconds """
	LEVEL_INTERVAL = 0.1
	LEVELS_FILE_EXTENSION = ".leveldata"
	
	#_____________________________________________________________________
	
	def __init__(self, instrument, file=None, id=None, filelabel=None):
		"""
		Creates a new instance of Event.
		
		Parameters:
			instrument -- Instrument associated with this Event.
			file -- the file this Event should play.
			id -- unique ID for this Event. If it's taken, a new one will be generated.
			filelabel -- label to print in error messages.
						It can be different	from the file parameter.
		"""
		gobject.GObject.__init__(self)
		
		self.id = instrument.project.GenerateUniqueID(id)  #check is id is already taken, then set it.
		self.start = 0.0			# Time in seconds at which the event begins
		self.duration = 0.0			# Duration in seconds of the event
		# The file this event should play (without escaped characters)
		# If you need characters escaped, please do self.file.replace(" ", "\ ") 
		# but **do not** assign it to this variable.
		self.file = file
		if self.file and os.path.isabs(self.file) and \
		      PlatformUtils.samefile(instrument.project.audio_path, os.path.dirname(self.file)):
			# If the file is in the audio dir, just include the filename, not the absolute path
			Globals.debug("Event() given absolute file, should be relative:", self.file)
			self.file = os.path.basename(self.file)
		
		# levels_file is a filename only, no directory information for levels here.
		basename = os.path.basename(self.file or "Unknown")
		self.levels_file = "%s_%d%s" % (basename, self.id, self.LEVELS_FILE_EXTENSION)
		
		# the label is the filename to print in error messages
		# if it differs from the real filename (i.e its been copied into the project)
		if filelabel != None:
			self.filelabel = filelabel
		else:
			self.filelabel = file

		self.isSelected = False		# True if the event is currently selected
		self.name = "New Event"		# Name of this event
		
		self.selection  = [0, 0]	# List start and end of selection (for fades, etc) measured in seconds 
		self.levels_list = LevelsList.LevelsList()	# LevelsList class containing array of audio levels to be drawn for this event
		
		self.instrument = instrument	# The parent instrument
		self.gnlsrc = None 			# The gstreamer gnlsource object.
		self.single_decode_bin = None		# The gstreamer file decoder element.
		
		self.offset = 0.0			# Offset through the file in seconds
		self.isLoading = False		# True if the event is currently loading level data
		self.isDownloading = False	# True if the event is currently loading from a remote source.
		self.isRecording = False		# True if the event is currently loading level data from a live recording
		self.loadingLength = 0 		# The length of the file in seconds as its being rendered
		self.lastEnd = 0 			# The last length of the loading file - used to minimise redraws
		self.loadingPipeline = None	# The Gstreamer pipeline used to load the waveform
		self.bus = None			# The bus to monitor messages on the loadingPipeline
		
		self.CreateFilesource()

		# a private dictionary containing the audio fade point times as keys
		# and the volume for that point between 0 and 1 as the values.
		# this is private, so if someone else wants a list of audio fade points
		# they must use the sorted list below.
		self.__fadePointsDict = {}
		# A list of control points for the audio fades
		# where each tuple is (<time in seconds>, <volume between 0 and 1>)
		# The list *must* be ordered by time-in-seconds, so when you update it from
		# the dictionary using dict.items(), be sure to sort it again.
		self.audioFadePoints = []
		#Just like self.levels_list except with all the levels scaled according to the
		#points in self.audioFadePoints.
		self.fadeLevels = LevelsList.LevelsList()

	#_____________________________________________________________________
	
	def GetFilename(self):
		return os.path.basename(self.file)
	
	#_____________________________________________________________________
	
	def GetAbsFile(self):
		if os.path.isabs(self.file):
			return self.file
		else:
			return os.path.join(self.instrument.project.audio_path, self.file)
	
	#_____________________________________________________________________
	
	def GetAbsLevelsFile(self):
		return os.path.join(self.instrument.project.levels_path, self.levels_file)
	
	#_____________________________________________________________________
	
	def CreateFilesource(self):	
		"""
		Creates a new GStreamer file source with an unique id.
		It then calls SetProperties() to populate the new object's
		properties.
		"""
		Globals.debug("create file source")
		if not self.gnlsrc:
			self.gnlsrc = gst.element_factory_make("gnlsource", "Event_%d"%self.id)
		if not self.gnlsrc in list(self.instrument.composition.elements()):
			self.instrument.composition.add(self.gnlsrc)
		
		self.SetProperties()

	#_____________________________________________________________________

	def DestroyFilesource(self):
		"""
		Removes the Gstreamer file source from the instrument's composition.
		"""
		if self.gnlsrc in list(self.instrument.composition.elements()):
			self.instrument.composition.remove(self.gnlsrc)
		
	#_____________________________________________________________________
		
	def SetProperties(self):
		"""
		Sets basic Event properties like location, start, duration, etc.
		"""
		if self.file:
			if self.single_decode_bin:
				self.gnlsrc.remove(self.single_decode_bin)
				self.single_decode_bin.set_state(gst.STATE_NULL)

			Globals.debug("creating SingleDecodeBin")
			caps = gst.caps_from_string("audio/x-raw-int;audio/x-raw-float")
			f = PlatformUtils.pathname2url(self.GetAbsFile())
			Globals.debug("file uri is:", f)
			self.single_decode_bin = SingleDecodeBin(caps=caps, uri=f)
			self.gnlsrc.add(self.single_decode_bin)
			Globals.debug("setting event properties:")
			propsDict = {
					"caps" : caps,
					"start" : long(self.start * gst.SECOND),
					"duration" : long(self.duration * gst.SECOND),
					"media-start" : long(self.offset * gst.SECOND),
					"media-duration" : long(self.duration * gst.SECOND),
					"priority" : 2
					}
					
			for prop, value in propsDict.iteritems():
				self.gnlsrc.set_property(prop, value)
				Globals.debug("\t", prop, "=", value)

	#_____________________________________________________________________

	def StoreToXML(self, doc, parent, graveyard=False):
		"""
		Converts this Event into an XML representation suitable for saving to a file.

		Parameters:
			doc -- the XML document object the Event will be saved to.
			parent -- the parent node that the serialized Event should
						be added to.
			graveyard -- True if this Event is on the graveyard stack,
						and should be serialized as a dead Event.
		"""
		if graveyard:
			ev = doc.createElement("DeadEvent")
		else:
			ev = doc.createElement("Event")
		parent.appendChild(ev)
		ev.setAttribute("id", str(self.id))
		
		params = doc.createElement("Parameters")
		ev.appendChild(params)
		
		items = ["start", "duration", "isSelected", 
				  "name", "offset", "file", "filelabel", "levels_file",
				  "isLoading", "isRecording"
				]
				
		#Since we are saving the path to the project file, don't delete it on exit
		if self.GetAbsFile() in self.instrument.project.deleteOnCloseAudioFiles:
			self.instrument.project.deleteOnCloseAudioFiles.remove(self.GetAbsFile())
		
		Utils.StoreParametersToXML(self, doc, params, items)		
		
		xmlPoints = doc.createElement("FadePoints")
		ev.appendChild(xmlPoints)
		Utils.StoreDictionaryToXML(doc, xmlPoints, self.__fadePointsDict, "FadePoint")
		
		if self.levels_list:
			self.levels_list.tofile(self.GetAbsLevelsFile())
		if self.GetAbsLevelsFile() in self.instrument.project.deleteOnCloseAudioFiles:
			self.instrument.project.deleteOnCloseAudioFiles.remove(self.GetAbsLevelsFile())
		
	#_____________________________________________________________________
		
	def __repr__(self):
		"""
		Creates a representation string of the Event.

		Returns:
			a string representing the name, id, start and duration
			for this Event.
		"""
		return "Event: '%s' (%d) : %d -> %d" % (self.name, self.id, self.start, self.duration)
		
	#_____________________________________________________________________
	
	def __cmp__(self, object):
		"""
		Compares two Events for equality.
		
		Returns:
			True -- the Events are equal.
			False -- the Events are different.
		"""
		if type(object) != type(self):
			return -1
		else:
			# If cmp(self.start, object.start) is not zero, return it.
			# If it is zero, return cmp(seld.id, object.id).
			return cmp(self.start, object.start) or cmp(self.id, object.id)
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("Move", "temp")
	def Move(self, to, frm=None):
		"""
		Moves this Event in time.

		Parameters:
			to -- the time the Event's moving to.
			frm -- the time the Event's moving from.
		"""
		if frm is None:
			self.temp = self.start
		else:
			self.temp = frm
		self.start = to
		self.SetProperties()
		self.emit("position")
	
	#_____________________________________________________________________
	
	def _Compat09_Move(self, frm, to, _undoAction_):
		"""
		Moves this Event in time.
		
		Considerations:
			A compatibility method for undo functions from 
			0.1, 0.2 and 0.9 project files. It should not be called
			explicitly by anyone.
		
		Parameters:
			frm -- the time the Event's moving from.
			to -- the time the Event's moving to.
		"""
		self.Move(to, frm, _undoAction_=_undoAction_)
	
	#_____________________________________________________________________
	
	def _Compat02_Split(self, split_point, id=-1):
		"""
		Function kept for compatibility with 0.2 project files.
		Parameters are the same as SplitEvent().
		"""
		self.SplitEvent(split_point)
	
	#_____________________________________________________________________
	
	def _Compat02_Join(self, joinEventID):
		"""
		Function kept for compatibility with 0.2 project files.
		Parameters are the same as JoinEvent().
		"""
		self.JoinEvent(joinEventID)
	
	#_____________________________________________________________________
	
	def CopySelection(self, eventID=-1):
		"""
		Only for use with a 2-point selection.
		Essentially performs a 'fake split' and returns a new event
		which would be the result of splitting an event at the 2 points.
		
		This is used when the user shift-drags an event to create a selection,
		then chooses 'copy' from the context menu. The new event can be placed
		wherever the user wishes by right-clicking and choosing 'paste'.
		"""
		if eventID >= 0:
			e = [x for x in self.instrument.graveyard if x.id == eventID][0]
			self.instrument.graveyard.remove(e)
		else:
			e = Event(self.instrument, self.file)
		e.name = self.name
		
		dur = self.selection[1] - self.selection[0]
		
		e.start = self.start + self.selection[0]
		e.offset = self.selection[0] #+self.offset
		e.duration = dur
		
		dictLeft = {}
		dictRight = {}
		for key, value in self.__fadePointsDict.iteritems():
			if key < self.selection[0]:
				dictLeft[key] = value
			if key > self.selection[0]:
				dictRight[key - self.selection[0]] = value
		#in case there is a fade passing through the split point, recreate half of it on either side
		splitFadeLevel = self.GetFadeLevelAtPoint(self.selection[0])
		dictLeft[self.selection[0]] = splitFadeLevel
		dictRight[0.0] = splitFadeLevel
		
		millis = int(self.selection[0] * 1000)
		e.levels_list = self.levels_list.slice_by_endtime(millis)
		e.__fadePointsDict = dictRight
			
		e.__UpdateAudioFadePoints()
		e.SetProperties()
		self.instrument.events.append(e)
		e.emit("length")
		e.emit("position")
		
		return e
		

	
	@UndoSystem.UndoCommand("JoinEvent", "temp", "temp2")
	def SplitEvent(self, split_point, cutRightSide=True, eventID=-1):
		"""
		Splits this Event.
		
		Parameters:
			split_point -- time offset split_point in seconds to start the split.
			cutRightSide -- if True, a new event will be created to represent
					the piece on the right which was split. This instance
					will be the one on the left.
					if False, this instance is the one on the right.
			eventID -- the ID of an event that was previously used for the same
					split. This should only be used by the undo stack and will
					help prevent the creation of multiple garbage copies of the
					same event each time a split is undone and redone.
					
		Returns:
			the newly created event.
		"""
		dur = self.duration
		
		#if we were given an event ID, reuse that event instead of creating a new one
		if eventID >= 0:
			e = [x for x in self.instrument.graveyard if x.id == eventID][0]
			self.instrument.graveyard.remove(e)
		else:
			e = Event(self.instrument, self.file)
		e.name = self.name
		
		dictLeft = {}
		dictRight = {}
		for key, value in self.__fadePointsDict.iteritems():
			if key < split_point:
				dictLeft[key] = value
			if key > split_point:
				dictRight[key - split_point] = value
		#in case there is a fade passing through the split point, recreate half of it on either side
		splitFadeLevel = self.GetFadeLevelAtPoint(split_point)
		dictLeft[split_point] = splitFadeLevel
		dictRight[0.0] = splitFadeLevel
		
		if cutRightSide:
			e.start = self.start + split_point
			e.offset = self.offset + split_point
			e.duration = dur - split_point
			self.duration = split_point
			
			millis = int(split_point * 1000)
			e.levels_list = self.levels_list.slice_by_endtime(millis)
			self.levels_list = self.levels_list.slice_by_endtime(0, millis)
			
			self.__fadePointsDict = dictLeft
			e.__fadePointsDict = dictRight
		else:
			e.start = self.start
			e.offset = self.offset
			e.duration = split_point
		
			self.start = self.start + split_point
			self.offset = self.offset + split_point
			self.duration = dur - split_point
			
			millis = int(split_point * 1000)
			e.levels_list = self.levels_list.slice_by_endtime(0, millis)
			self.levels_list = self.levels_list.slice_by_endtime(millis)
			
			self.__fadePointsDict = dictRight
			e.__fadePointsDict = dictLeft
			
		self.__UpdateAudioFadePoints()
		e.__UpdateAudioFadePoints()
		e.SetProperties()
		self.instrument.events.append(e)
		self.SetProperties()
		self.emit("length")
		self.emit("position")
		self.instrument.emit("event::added", e)
		
		#undo parameters
		self.temp = e.id
		self.temp2 = cutRightSide
		
		return e
		
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("SplitEvent", "temp", "temp2", "temp3")
	def JoinEvent(self, joinEvent, joinToRight=True):
		"""
		Joins two Events together.
		
		Parameters:
			joinEvent -- the ID of the Event, or the Event object to join to this one.
			joinToRight -- True if the event will be joined on the right side
		"""
		eventObjectList = [x for x in self.instrument.events if x.id == joinEvent]
		if eventObjectList:
			joinEvent = eventObjectList[0]
		
		if joinToRight:
			self.temp = self.duration
			
			for key, value in joinEvent.__fadePointsDict.iteritems():
				self.__fadePointsDict[key + self.duration] = value
			#remove the point on either edge that was created when they were split
			if self.__fadePointsDict.has_key(self.duration):
				del self.__fadePointsDict[self.duration]
			
			old_duration = int(self.duration * 1000)
			self.duration += joinEvent.duration
			self.levels_list.extend(old_duration, joinEvent.levels_list)
			#update the fade point list after the level, and duration because it depends on them
			self.__UpdateAudioFadePoints()
		else:
			self.temp = joinEvent.duration
		
			self.start = joinEvent.start
			self.offset = joinEvent.offset
			
			old_duration = int(self.duration * 1000)
			self.duration += joinEvent.duration
			self.levels_list = LevelsList.add(old_duration, joinEvent.levels_list, self.levels_list)
			
			newDict = joinEvent.__fadePointsDict.copy()
			for key, value in self.__fadePointsDict.iteritems():
				newDict[key + joinEvent.duration] = value
			#remove the point on either edge that was created when they were split
			if newDict.has_key(joinEvent.duration):
				del newDict[joinEvent.duration]
			self.__fadePointsDict = newDict
			self.__UpdateAudioFadePoints()
			
		#create an undo action that is not attached to the project so that
		# the following delete will not be undone (it will be re-split not resurrected)
		nullAction = UndoSystem.AtomicUndoAction()
		# Now that they're joined, move delete the rightEvent
		joinEvent.Delete(_undoAction_=nullAction)
		
		self.emit("length")
		self.emit("position")
		
		self.temp2 = joinToRight
		self.temp3 = joinEvent.id

	#_____________________________________________________________________
	
	def Trim(self, start_split, end_split):
		"""
		Splits the Event and then deletes the first and last sections,
		leaving only the middle section.
		
		Parameters:
			start_split -- the time for the start of the trim.
			end_split -- the time for the end of the trim.
		"""
		
		if start_split > end_split or (start_split <= 0 and end_split >= self.duration):
			#both points must not be right at the edges, or there is nothing to split
			return
			
		undoAction = self.instrument.project.NewAtomicUndoAction()

		if 0 < start_split < self.duration:
			# Split off the left section of the event
			leftSplit = self.SplitEvent(start_split, False, _undoAction_=undoAction)
			self.instrument.DeleteEvent(leftSplit.id, _undoAction_=undoAction)
		
		#Adjust the end_split value since splitting the left has changed self.duration
		end_split = end_split - start_split
		
		if 0 < end_split < self.duration:
			# Split off the right section of the event
			rightSplit = self.SplitEvent(end_split, _undoAction_=undoAction)
			self.instrument.DeleteEvent(rightSplit.id, _undoAction_=undoAction)
		
		self.SetProperties()
		self.emit("length")
		
	#_____________________________________________________________________
	
	def _Compat02_UndoTrim(self, leftID, rightID):
		"""
		Resurrects two pieces from the graveyard and joins them to
		either side of this Event.
		
		Considerations: 
			This method is kept here for undo compatibility with Jokosher
			version 0.2 project files, and is never called when a 0.9 or
			greater project is being used.
		
		Parameters:
			leftID -- id of the left Event to be resurrected.
			rightID -- id of the right Event to be resurrected.
		"""
		undoAction = self.instrument.project.NewAtomicUndoAction()
		
		self.instrument.ResurrectEvent(leftID, _undoAction_=undoAction)
		self.JoinEvent(leftID, False, _undoAction_=undoAction)
		self.instrument.ResurrectEvent(rightID, _undoAction_=undoAction)
		self.JoinEvent(rightID, _undoAction_=undoAction)
		
	#_____________________________________________________________________
	
	def Delete(self, _undoAction_=None):
		"""
		Deletes this Event and sends it to the graveyard.
		"""
		if _undoAction_:
			self.instrument.DeleteEvent(self.id, _undoAction_=_undoAction_)
		else:
			self.instrument.DeleteEvent(self.id)
			
	#_____________________________________________________________________
	
	def Resurrect(self, _undoAction_=None):
		"""
		Brings this event back from the graveyard.
		
		Considerations:
			This method is made obsolete by instrument.ResurrectEvent(),
			but is still kept here for 0.2 undo history compatibility.
		"""
		if _undoAction_:
			self.instrument.ResurrectEvent(self.id, _undoAction_=_undoAction_)
		else:
			self.instrument.ResurrectEvent(self.id)
			
	#_____________________________________________________________________

	def install_plugin_cb(self, result):
		self._installing_plugins = False
		# hardcode gst.pbutils.INSTALL_PLUGINS_SUCCESS to avoid conditional gst.pbutils import
		INSTALL_PLUGINS_SUCCESS = 0
		if result == INSTALL_PLUGINS_SUCCESS:
			gst.update_registry()
			self.GenerateWaveform()
			return

		# FIXME: send a better error
		msg = "failed to install plugins: %s" % result
		self.emit("corrupt", msg)

	#_____________________________________________________________________
	
	def bus_message(self, bus, message):
		"""
		Handler for the GStreamer bus messages relevant to this Event.
		At the moment, this is used to report on how the loading progress
		is going.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
			
		Returns:
			True -- the Event is loading.
			False -- the Event isn't loading.
		"""
		if not self.isLoading:
			return False

		st = message.structure
		if not st:
			return False
		
		if st.get_name().startswith('missing-'):
			self.loadingPipeline.set_state(gst.STATE_NULL)
			Utils.HandleGstPbutilsMissingMessage(message, self.install_plugin_cb)

		elif st.get_name() == "level":
			self.__AppendLevelToList(st)
			
			#Truncate so it updates once per second
			self.loadingLength = st["endtime"] / gst.SECOND
			
			# Only send events every second processed to reduce GUI load
			if self.loadingLength != self.lastEnd:
				self.lastEnd = self.loadingLength 
				self.emit("length") # tell the GUI
		return True
		
	#_____________________________________________________________________
		
	def bus_eos(self, bus, message):	
		"""
		Handler for the GStreamer End Of Stream message. Currently
		used when the file is loading and is being rendered. This
		function is called at the end of the file loading process and
		finalises the rendering.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
			
		Returns:
			False -- stops the signal propagation. *CHECK*
		"""
		if message.type == gst.MESSAGE_EOS:
			
			# Update levels for partial events
			q = self.loadingPipeline.query_duration(gst.FORMAT_TIME)
			length = float(q[0] / float(gst.SECOND))
			
			#we're at EOS, and still have no value for duration
			if not self.duration:
				if length:
					self.duration = length
				else:
					self.duration = self.loadingLength
			
			if self.levels_list:
				final_endtime = self.levels_list[-1][0]
				if final_endtime > int(self.duration * 1000):
					Globals.debug("Event %d: duration (%f) is less than last level endtime (%d)."
					              % (self.id, self.duration, final_endtime))
					self.duration = final_endtime / 1000.0
					self.SetProperties()
					Globals.debug("\tduration has been increased to", self.duration)
			
			if length and (self.offset > 0 or self.duration != length):
				starttime = int(self.offset * 1000)
				stoptime = int((self.offset + self.duration) * 1000)
				self.levels_list = self.levels_list.slice_by_endtime(starttime, stoptime)
				
			# We're done with the bin so release it
			self.StopGenerateWaveform()
			
			# Signal to interested objects that we've changed
			self.emit("waveform")
			return False
			
	#_____________________________________________________________________

	def bus_message_statechange(self, bus, message):
		"""
		Handler for the GStreamer statechange message.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
		"""
		# state has changed
		try:
			time = self.loadingPipeline.query_duration(gst.FORMAT_TIME)
			if self.duration == 0 and time[0] > 0:
				self.duration = float(time[0] / float(gst.SECOND))
				
				#update position with proper duration
				self.MoveButDoNotOverlap(self.start)
				self.SetProperties()
				self.emit("length")
				self.emit("position")
		except:
			# no size available yet
			pass

	#_____________________________________________________________________

	def bus_error(self, bus, message):
		"""
		Handler for when things go completely wrong with GStreamer.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
		"""
		error, debug = message.parse_error()
		
		Globals.debug("Event Bus Error Message:")
		Globals.debug("\tCode:", error.code)
		Globals.debug("\tDomain:", error.domain)
		Globals.debug("\tMessage:", error.message)
		
		Globals.debug("Event bus error:", str(error), str(debug))
		self.emit("corrupt", "%s\n%s" % (error, debug))
	
	#_____________________________________________________________________
	
	def bus_message_tags(self, bus, message):
		"""
		Handler for catching audio file tags that Gstreamer throws.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
		"""
		Globals.debug("received group of tags")
		st = message.structure
		
		title, artist = None, None
		if st.has_key("title"):
			title = st["title"]
		if st.has_key("artist"):
			artist = st["artist"]
		
		#check which tags actually contain something
		if title and artist:
			self.name = _("%(title)s by %(artist)s") % {"title":title, "artist":artist}
		elif title:
			self.name = title
	
	#_____________________________________________________________________
	
	def GenerateWaveform(self):
		"""
		Renders the level information for the GUI.
		"""
		pipe = """filesrc name=src ! decodebin ! audioconvert ! level message=true name=level_element ! fakesink"""
		self.loadingPipeline = gst.parse_launch(pipe)
		
		filesrc = self.loadingPipeline.get_by_name("src")
		level = self.loadingPipeline.get_by_name("level_element")
		
		filesrc.set_property("location", self.GetAbsFile())
		level.set_property("interval", int(self.LEVEL_INTERVAL * gst.SECOND))

		self.bus = self.loadingPipeline.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)
		self.bus.connect("message::tag", self.bus_message_tags)
		self.bus.connect("message::state-changed", self.bus_message_statechange)
		self.bus.connect("message::eos", self.bus_eos)
		self.bus.connect("message::error", self.bus_error)

		self.levels_list = LevelsList.LevelsList()
		self.isLoading = True
		self.emit("loading")

		self.loadingPipeline.set_state(gst.STATE_PLAYING)

	#_____________________________________________________________________
	
	def CopyAndGenerateWaveform(self, uri):
		"""
		Copies the audio file to the new file location and reads the levels
		at the same time.
		"""
		
		urisrc = gst.element_make_from_uri(gst.URI_SRC, uri)
		if not urisrc:
			#This means that here is no gstreamer src element on the system that can handle this URI type.
			return False
		
		pipe = """tee name=mytee mytee. ! queue ! filesink name=sink """ +\
		       """mytee. ! queue ! decodebin ! audioconvert ! level name=level_element message=true ! fakesink""" 
		self.loadingPipeline = gst.parse_launch(pipe)
		
		tee = self.loadingPipeline.get_by_name("mytee")
		filesink = self.loadingPipeline.get_by_name("sink")
		level = self.loadingPipeline.get_by_name("level_element")
		
		self.loadingPipeline.add(urisrc)
		urisrc.link(tee)
		
		filesink.set_property("location", self.GetAbsFile())
		level.set_property("interval", int(self.LEVEL_INTERVAL * gst.SECOND))

		self.bus = self.loadingPipeline.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)
		self.bus.connect("message::tag", self.bus_message_tags)
		self.bus.connect("message::state-changed", self.bus_message_statechange)
		self.bus.connect("message::eos", self.bus_eos)
		self.bus.connect("message::error", self.bus_error)

		self.levels_list = LevelsList.LevelsList()
		self.isLoading = True
		self.emit("loading")

		self.loadingPipeline.set_state(gst.STATE_PLAYING)
		
		return True
		
	#_____________________________________________________________________
	
	def StopGenerateWaveform(self, finishedLoading=True):
		"""
		Stops the internal pipeline that loads the waveform from this event's file.
		
		Parameters:
			finishedLoading -- True if the event has finished loading the waveform,
					False if the loading is being cancelled.
		"""
		if self.bus:
			self.bus.remove_signal_watch()
			self.bus = None
		if self.loadingPipeline:
			self.loadingPipeline.set_state(gst.STATE_NULL)
			
			if finishedLoading and self.levels_list:
				self.levels_list.tofile(self.GetAbsLevelsFile())
				del_on_close_list = self.instrument.project.deleteOnCloseAudioFiles
				# this event might not be in the project file yet
				# if so, levels_file should be deleted when audio file is deleted on exit
				if self.GetAbsFile() in del_on_close_list:
					del_on_close_list.append(self.GetAbsLevelsFile())
					
				inc = IncrementalSave.CompleteLoading(self.id, self.duration, self.levels_file)
				self.instrument.project.SaveIncrementalAction(inc)
			
			if self.isDownloading:
				# If we are currently downloading, we can't restart later, 
				# so cancel regardless of the finishedLoading boolean's value.
				self.isDownloading = False
				self.isLoading = False
			else:
				self.isLoading = not finishedLoading
			
			
			self.loadingPipeline = None
			self.loadingLength = 0
			self.emit("loading")
	
	#_____________________________________________________________________

	def recording_bus_level(self, bus, message):
		"""
		Handler for the GStreamer bus messages relevant to this Event.
		At the moment this is used to report on how the recording
		progress is going. *CHECK*
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
			
		Returns:
			True -- the Event is recording.
			False -- the Event isn't recording.
		"""
		if not self.isRecording:
			return False
		
		st = message.structure
		if st and message.src.get_name() == "recordlevel":
			self.__AppendLevelToList(st)
			
			end = st["endtime"] / float(gst.SECOND)  #convert to float representing seconds 
			#Round to one decimal place so it updates 10 times per second
			self.loadingLength = round(end, 1)
			
			# Only send events every second processed to reduce GUI load
			if self.loadingLength != self.lastEnd:
				self.lastEnd = self.loadingLength 
				self.emit("length") # tell the GUI
		return True
		
	#_____________________________________________________________________
	
	def __AppendLevelToList(self, structure):
		(end, peaks) = Utils.CalculateAudioLevelFromStructure(structure)
		
		# the last level may be sent twice. If timestamp is the same, ignore it.
		if self.levels_list and self.levels_list[-1][0] == end:
			return
		
		# work around GStreamer bug where stream time will be -1 (indicating error)
		# and then cast to guint64 which results in the maximum 64-bit integer value.
		# In this case stream-time and endtime are bogus values, but duration is still correct.
		stream_time = structure["stream-time"]
		if stream_time == ((2**64) - 1):
			delta = int(structure["duration"] / Utils.NANO_TO_MILLI_DIVISOR)
			self.levels_list.append_time_delta(delta, peaks)
		else:
			self.levels_list.append(end, peaks)
		
	#_____________________________________________________________________
	
	def SetSelected(self, sel):
		"""
		Enables or disables the selection state for this Event.

		Parameters:
			sel -- the new selection state:
					True = the Event has been selected.
					False = the Event has been deselected.
		"""
		# No need to emit a signal when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.emit("selected")
	
	#_____________________________________________________________________
	
	def MayPlace(self, xpos):
		"""
		Checks if this event could be placed at xpos without 
		overlapping another Event on the same Instrument.

		Parameters:
			xpos -- the potential start position to check.
		
		Returns:
			True if it's OK to place the Event at xpos, False if not.
		"""
		for e in self.instrument.events:
			if e is self:
				continue
			if not (e.start + e.duration <= xpos or e.start >= xpos + self.duration):
				return False
		return True
		
	#_____________________________________________________________________
	
	def MoveButDoNotOverlap(self, xpos):
		"""
		This method will attempt to move this Event to the given position.
		If the position requires overlapping, this Event will be put flush
		against the closest side of the Event which is in the way.

		Parameters:
			xpos -- the potential position to move the Event to.
		"""
		alreadyTriedRemovingOverlap = False
		self.instrument.events.sort()
		
		for e in self.instrument.events:
			if e is self:
				continue
			
			elif alreadyTriedRemovingOverlap:
				#we have already attempted to place to the left, on the last iteration
				#from now on we only try placing on the right side
				start = e.start + e.duration
				if self.MayPlace(start):
					self.start = start
					return
				continue
			
			rightPos = e.start + e.duration
			leftPos = e.start - self.duration
			#if this event IS overlapping with the other event
			if not (rightPos <= xpos or leftPos >= xpos):
				#if the middle of this event is on the RIGHT of the middle of the other event
				if rightPos > xpos and e.start + (e.duration/2) < xpos + (self.duration/2):
					order = (rightPos, max(leftPos, 0))
				else: #if the middle is on the LEFT
					order = (max(leftPos, 0), rightPos)
				
				for start in order:
					if self.MayPlace(start):
						self.start = start
						return
				
				alreadyTriedRemovingOverlap = True
				
		#There are no other events overlapping with this one
		self.start = xpos
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("RemoveAudioFadePoints", "temp", "temp2", "temp3", "temp4")
	def AddAudioFadePoints(self, firstPoint, secondPoint, firstVolume, secondVolume):
		"""
		Adds two fade points to the audioFadePoints list.
		If either point exists already, replaces it, and resorts the list by time.
		
		Parameters:
			firstPoint -- point in time, where the fade starts.
			secondPoint -- point in time, where the fade ends.
			firstVolume -- value of the initial fade volume.
			secondVolume -- value of the final fade volume.
		"""
		#for command manager to use with undo
		self.temp = firstPoint
		self.temp2 = secondPoint
		self.temp3 = None
		self.temp4 = None
		
		if self.__fadePointsDict.has_key(firstPoint):
			self.temp3 = self.__fadePointsDict[firstPoint]
		if self.__fadePointsDict.has_key(secondPoint):
			self.temp4 = self.__fadePointsDict[secondPoint]
		
		#we *must* compare to None here because audio points with volume 0 *are* allowed
		if firstPoint != None and firstVolume != None:
			self.__fadePointsDict[firstPoint] = firstVolume
		if secondPoint != None and secondVolume != None:
			self.__fadePointsDict[secondPoint] = secondVolume
		
		self.__UpdateAudioFadePoints()
	
	#_____________________________________________________________________
	
	@UndoSystem.UndoCommand("AddAudioFadePoints", "temp", "temp2", "temp3", "temp4")
	def RemoveAudioFadePoints(self, firstPoint, secondPoint, firstOldVolume=None, secondOldVolume=None):
		"""
		Removes a fade point (along with its values) from the audioFadePoints list.
		If firstOldVolume and secondOldVolume are given, the levels at the two points
		will be replaced with those old values, instead of being removed.
		
		Parameters:
			firstPoint -- point in time, where the fade starts.
			secondPoint -- point in time, where the fade ends.
			firstOldVolume -- old value of the initial fade volume,
								used to replace the current one.
			secondOldVolume -- old value of the final fade volume,
								used to replace the current one.
		"""
		#undo values
		self.temp = firstPoint
		self.temp2 = secondPoint
		self.temp3 = None
		self.temp4 = None
		
		if self.__fadePointsDict.has_key(firstPoint):
			self.temp3 = self.__fadePointsDict[firstPoint]
		if self.__fadePointsDict.has_key(secondPoint):
			self.temp4 = self.__fadePointsDict[secondPoint]
		
		#if the point had a previous value (firstOldPoint) then put the value back
		#we *must* compare to None here because audio points with volume 0 *are* allowed
		if firstOldVolume != None:
			self.__fadePointsDict[firstPoint] = firstOldVolume
		#else, just remove the point because it didn't exist before
		elif self.__fadePointsDict.has_key(firstPoint):
			del self.__fadePointsDict[firstPoint]
		
		#same as above but for the second point
		if secondOldVolume != None:
			self.__fadePointsDict[secondPoint] = secondOldVolume
		elif self.__fadePointsDict.has_key(secondPoint):
			del self.__fadePointsDict[secondPoint]
			
		self.__UpdateAudioFadePoints()
	
	#_____________________________________________________________________
	
	def __UpdateAudioFadePoints(self):
		"""
		Private function that uses the private dictionary with
		all the fade points to update the audioFadePoints list.
		The audioFadePoints is different from the dictionary
		because it will always have points at the beginning and
		the end of the event (unless there are none at all), and
		it is a list, so accessing the contents in order is much faster.
		"""
		
		#update the fade points list from the dictionary
		self.audioFadePoints = self.__fadePointsDict.items()
		#dicts dont have order, so sort after update
		self.audioFadePoints.sort(key=lambda x: x[0])
		
		#only add beginning and end points if there are some other points already in the list
		if self.audioFadePoints:
			#if there is no point at the beginning, make one with the
			#same value as the first fade point. This makes the first fade
			#extend back to the beginning.
			if self.audioFadePoints[0][0] != 0.0:
				first = (0.0, self.audioFadePoints[0][1])
				self.audioFadePoints.insert(0, first)
			#same as above but for the end of the event.
			if self.audioFadePoints[-1][0] != self.duration:
				last = (self.duration, self.audioFadePoints[-1][1])
				self.audioFadePoints.append(last)
			
		self.__UpdateFadeLevels()
		self.emit("waveform")
	
	#_____________________________________________________________________
	
	def __UpdateFadeLevels(self):
		"""
		Private function that uses the private dictionary with
		all the fade leves to update the fadeLevels list. The fadeLevels
		list is a cache of faded levels as they will be shown on the screen
		so that we don't have to calculate them everytime we draw.
		"""
		if not self.audioFadePoints or len(self.audioFadePoints) < 2:
			Globals.debug("Event", self.id, ": no fade points to use")
			#there are no fade points for us to use
			return
			
		#fadePercents = []
		#oneSecondInLevels = len(self.levels) / self.duration
		
		self.fadeLevels = LevelsList.LevelsList()
		
		iterFadePoints = iter(self.audioFadePoints)
		firstFadeTime, firstFadeValue = iterFadePoints.next()
		firstFadeTime = int(firstFadeTime * 1000)	#convert to milliseconds
		secondFadeTime, secondFadeValue = iterFadePoints.next()
		secondFadeTime = int(secondFadeTime * 1000)	#convert to milliseconds
		# if less than one percent difference, assume they are the same
		sameValues = abs(firstFadeValue - secondFadeValue) < 0.01
		
		if not sameValues:
			slope = (secondFadeValue - firstFadeValue) / (secondFadeTime - firstFadeTime)
		
		for endtime, peak in self.levels_list:
			# check if we have moved into the next fade point pair
			# don't care about 1 millisecond difference, its rounding error
			if endtime > (secondFadeTime + 1):  
				firstFadeTime = secondFadeTime
				firstFadeValue = secondFadeValue
				try:
					secondFadeTime, secondFadeValue = iterFadePoints.next()
				except StopIteration:
					Globals.debug("Event %d: endtime (%d) is after last fade point (%d,%d)"
					              % (self.id, endtime, secondFadeTime, secondFadeValue))
				
				secondFadeTime = int(secondFadeTime * 1000)	#convert to milliseconds
				
				# if less than one percent difference, assume they are the same
				sameValues = abs(firstFadeValue - secondFadeValue) < 0.01
				if not sameValues:
					# the fade line is not flat, so calculate the slope of it
					slope = (secondFadeValue - firstFadeValue) / (secondFadeTime - firstFadeTime)
			
			if sameValues:
				#no fade here, the same volume continues across
				self.fadeLevels.append(endtime, [int(peak * firstFadeValue)])
			else:
				rel_time = endtime - firstFadeTime
				peak_delta = slope * rel_time
				new_fade_value = firstFadeValue + peak_delta
				assert new_fade_value <= 1.0		# a fade cannot be more than 100%
				peak = int(peak * new_fade_value)
				
				self.fadeLevels.append(endtime, [peak])
	#_____________________________________________________________________
	
	def GetFadeLevels(self):
		"""
		Obtain the fade levels list.
		The only difference between this list and the levels list is
		that the levels in this list are scaled according to the fade
		curves applied to the current Event.
		
		Returns:
			a list of fade levels, the same length as the levels list.
		"""
		# no fades registered
		if not self.audioFadePoints:
			return self.levels_list
			
		if len(self.fadeLevels) != len(self.levels_list):
			self.__UpdateFadeLevels()
			assert len(self.fadeLevels) == len(self.levels_list)
			
		return self.fadeLevels
		
	#_____________________________________________________________________
	
	def GetFadeLevelAtPoint(self, time):
		"""
		Obtain the level of audio at any point in time.
		
		Parameters:
			time -- point in time to extract the audio level from.
		
		Returns:
			the level of the audio in percentage format [0,1]
		"""
		if not self.audioFadePoints:
			return 1.0
		if self.audioFadePoints[-1][0] < time or self.audioFadePoints[0][0] > time:
			#for some reason the time given is outside the event, so ignore it
			return 1.0
		
		#we can assume that audioFadePoints is sorted and has at least 2 elements
		points = self.audioFadePoints
		for i in xrange(1, len(points)):
			if points[i][0] >= time:
				right = points[i]
				left = points[i-1]
				break
		
		if right[0] == left[0]:
			return 1.0
		elif right[1] == left[1]:
			return left[1]
		else:
			ratio = (right[1] - left[1]) / (right[0] - left[0])
			
		relativeLevel = ratio * (time - left[0])
		return left[1] + relativeLevel
		
	#_____________________________________________________________________
	
	def DeleteSelectedFadePoints(self):
		"""
		Removes all the fade points for this Event.
		"""
		removeList = []
		for key in self.__fadePointsDict.iterkeys():
			if self.selection[0] <= key <= self.selection[1]:
				removeList.append(key)
		
		if len(removeList) % 2 == 0:
			#if we have an even number, use the fact that
			#RemoveAudioFadePoints takes two points.
			for i in range(len(removeList))[::2]:
				self.RemoveAudioFadePoints(removeList[i], removeList[i+1])
		else:
			for i in removeList:
				self.RemoveAudioFadePoints(i, None)
	
	#_____________________________________________________________________
#=========================================================================	
