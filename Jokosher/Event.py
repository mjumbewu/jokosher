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

from UndoSystem import *
import xml.dom.minidom as xml
import pygst
pygst.require("0.10")
import gst
from Monitored import *
from Utils import *
import os, Globals
import gettext
_ = gettext.gettext

#=========================================================================

class Event(Monitored):
	"""
	This class handles maintaing the information for a single audio 
	event, normally, a fragment of a recorded file.
	"""
	
	""" State changed types (to be sent through the Monitored class) """
	WAVEFORM, MOVE, LENGTH, CORRUPT = range(4)
	
	""" The level sample interval in seconds """
	LEVEL_INTERVAL = 0.1
	
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
		Monitored.__init__(self)
		
		self.start = 0.0			# Time in seconds at which the event begins
		self.duration = 0.0			# Duration in seconds of the event
		# The file this event should play (without escaped characters)
		# If you need characters escaped, please do self.file.replace(" ", "\ ") 
		# but **do not** assign it to this variable.
		self.file = file

		# the label is the filename to print in error messages
		# if it differs from the real filename (i.e its been copied into the project)
		if filelabel != None:
			self.filelabel = filelabel
		else:
			self.filelabel = file

		self.isSelected = False		# True if the event is currently selected
		self.name = "New Event"		# Name of this event
		
		self.selection  = [0, 0]	# List start and end of selection (for fades, etc) measured in seconds 
		self.levels = []			# Array of audio levels to be drawn for this event
		
		self.id = instrument.project.GenerateUniqueID(id)  #check is id is already taken, then set it.
		self.instrument = instrument	# The parent instrument
		self.filesrc = None 			# The gstreamer gnlfilesource object.
		
		self.offset = 0.0			# Offset through the file in seconds
		self.isLoading = False		# True if the event is currently loading level data
		self.isRecording = False		# True if the event is currently loading level data from a live recording
		self.loadingLength = 0 		# The length of the file in seconds as its being rendered
		self.lastEnd = 0 			# The last length of the loading file - used to minimise redraws
		
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
		#Just like self.levels except with all the levels scaled according to the
		#points in self.audioFadePoints.
		self.fadeLevels = []

	#_____________________________________________________________________
	
	def CreateFilesource(self):	
		"""
		Creates a new GStreamer file source with an unique id.
		It then calls SetProperties() to populate the new object's
		properties.
		"""
		Globals.debug("create file source")
		if not self.filesrc:
			self.filesrc = gst.element_factory_make("gnlfilesource", "Event_%d"%self.id)
		if not self.filesrc in list(self.instrument.composition.elements()):
			self.instrument.composition.add(self.filesrc)
		
		self.SetProperties()
		
	#_____________________________________________________________________
		
	def SetProperties(self):
		"""
		Sets basic Event properties like location, start, duration, etc.
		"""
		if self.file:
			Globals.debug("setting event properties")
			self.filesrc.set_property("location", self.file)
			self.filesrc.set_property("start", long(self.start * gst.SECOND))
			self.filesrc.set_property("duration", long(self.duration * gst.SECOND))
			self.filesrc.set_property("media-start", long(self.offset * gst.SECOND))
			self.filesrc.set_property("media-duration", long(self.duration * gst.SECOND))
			self.filesrc.set_property("priority", 2)
			
			Globals.debug("location =", self.file)
			Globals.debug("start =", long(self.start * gst.SECOND))
			Globals.debug("duration =", long(self.duration * gst.SECOND))
			Globals.debug("media-start =", long(self.offset * gst.SECOND))
			Globals.debug("media-duration =", long(self.duration * gst.SECOND))
			
			Globals.debug("event properties set")

	#_____________________________________________________________________

	def StoreToXML(self, doc, parent, graveyard=False):
		"""
		Converts this Event into an XML representation suitable for saving to a file.

		Parameters:
			doc -- the XML dcxument object the Event will be saved to.
			parent -- the parent node that the serialized Event should
						be added to.
			graveyard -- True if this Event is on the graveyard stack,
						and should be serialized as a dead event.
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
				  "name", "offset", "file", "isLoading"
				]
				
		#Since we are saving the path to the project file, don't delete it on exit
		if self.file in self.instrument.project.deleteOnCloseAudioFiles:
			self.instrument.project.deleteOnCloseAudioFiles.remove(self.file)
		
		self.temp = self.file
		if os.path.samefile(self.instrument.path, os.path.dirname(self.file)):
			# If the file is in the audio dir, just include the filename, not the absolute path
			self.file = os.path.basename(self.file)
		
		StoreParametersToXML(self, doc, params, items)
		
		# Put self.file back to its absolute path
		self.file = self.temp
		
		
		xmlPoints = doc.createElement("FadePoints")
		ev.appendChild(xmlPoints)
		StoreDictionaryToXML(doc, xmlPoints, self.__fadePointsDict, "FadePoint")
		
		if self.levels:
			levelsXML = doc.createElement("Levels")
			ev.appendChild(levelsXML)
			stringList = map(str, self.levels)
			levelsXML.setAttribute("value", ",".join(stringList))
			
	#_____________________________________________________________________
			
	def LoadFromXML(self, node):
		"""
		Restores an Event from its serialized XML representation.
		
		Parameters:
			node -- the XML node to retreive data from.
		"""
		params = node.getElementsByTagName("Parameters")[0]
		
		LoadParametersFromXML(self, params)
		
		if not os.path.isabs(self.file):
			# If there is a relative path for self.file, assume it is in the audio dir
			self.file = os.path.join(self.instrument.path, self.file)
		
		try:
			xmlPoints = node.getElementsByTagName("FadePoints")[0]
		except IndexError:
			Globals.debug("Missing FadePoints in Event XML")
		else:
			self.__fadePointsDict = LoadDictionaryFromXML(xmlPoints)
		
		try:	
			levelsXML = node.getElementsByTagName("Levels")[0]
		except IndexError:
			Globals.debug("No event levels in project file")
			self.GenerateWaveform()
		else: 
			if levelsXML.nodeType == xml.Node.ELEMENT_NODE:
				value = str(levelsXML.getAttribute("value"))
				self.levels = map(float, value.split(","))

		if self.isLoading or self.isRecording:
			self.GenerateWaveform()

		self.__UpdateAudioFadePoints()
		self.CreateFilesource()
		
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
	
	@UndoCommand("Move", "start", "temp")
	def Move(self, frm, to):
		"""
		Moves this Event in time.

		Parameters:
			frm -- the time the Event's moving from.
			to -- the time the Event's moving to.
		"""
		self.temp = frm
		self.start = to
		self.SetProperties()
	
	#_____________________________________________________________________
	
	@UndoCommand("Join", "temp")
	def Split(self, split_point, id=-1):
		"""
		Splits this Event.
		
		Parameters:
			split_point -- time offset split_point in seconds to start the split.
			id -- if specified, then the created event will be pulled from the
					graveyard (for undo/redo compatibility).
					
		Returns:
			the newly created event, which is the one on the right
			(after the splitpoint).
		"""
		if id == -1:
			e = self.split_event(split_point)
			e.SetProperties()
			self.instrument.events.append(e)
			self.temp = e.id
			self.SetProperties()
			self.StateChanged(self.LENGTH)
			
			return e
		else:
			d = self.duration
			self.duration = split_point
			
			event = [x for x in self.instrument.graveyard if x.id == id][0]
			self.instrument.events.append(event)
			
			nl = int(len(self.levels) * (split_point / d))
			self.levels = self.levels[:nl]
			
			self.temp = event.id
			
			self.StateChanged(self.LENGTH)
		
	#_____________________________________________________________________
	
	@UndoCommand("Split", "temp", "temp2")
	def Join(self, joinEventID):
		"""
		Joins two Events together.
		
		Parameters:
			joinEventID -- the ID of the Event to join to this one.
		"""
		event = [x for x in self.instrument.events if x.id == joinEventID][0]

		self.temp = self.duration
		self.temp2 = event.id
		
		self.join_event(event)
		# Now that they're joined, move rightEvent to the graveyard
		self.instrument.events.remove(event)
		self.instrument.graveyard.append(event)
		
		self.StateChanged(self.LENGTH)

	#_____________________________________________________________________
	
	def split_event(self, split_point, cutRightSide=True):
		"""
		Helper function for Split() and Trim(). 
		
		Considerations:
			All other methods and classes should not invoke this function 
			directly since there is no undo for it.
		
		Parameters:
			split_point --
			cutRightSide -- if True, a new event will be created to represent
							the piece on the right which was split. This instance
							will be the one on the left.
							if False, this instance is the one on the right.
							
		Returns:
			the newly created Event.
		"""
		dur = self.duration
		
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
			
			nl = int(len(self.levels) * (split_point / dur))
			e.levels = self.levels[nl:]
			self.levels = self.levels[:nl]
			
			self.__fadePointsDict = dictLeft
			e.__fadePointsDict = dictRight
			self.__UpdateAudioFadePoints()
			e.__UpdateAudioFadePoints()
		else:
			e.start = self.start
			e.offset = self.offset
			e.duration = split_point
		
			self.start = self.start + split_point
			self.offset = self.offset + split_point
			self.duration = dur - split_point
			
			nl = int(len(self.levels) * (split_point / dur))
			e.levels = self.levels[:nl]
			self.levels = self.levels[nl:]
			
			self.__fadePointsDict = dictRight
			e.__fadePointsDict = dictLeft
			self.__UpdateAudioFadePoints()
			e.__UpdateAudioFadePoints()
		
		return e
	
	#_____________________________________________________________________
	
	def join_event(self, joinEvent, joinToRight=True):
		"""
		Helper function for Join() and Trim(). After joining the events on
		either side, this method will not remove the Event from the instrument lane.
		This must be done from the calling function.
		
		Considerations:
			All other methods and classes should not invoke this function 
			directly since there is no undo for it.
		
		Parameters:
			joinEvent -- Event to join with elf.
			joinToRight --	if True, the joinEvent will be merged to the right
							side of self.
							if False, the joinEvent will be to the left of self.
		"""
		if joinToRight:
			for key, value in joinEvent.__fadePointsDict.iteritems():
				self.__fadePointsDict[key + self.duration] = value
			#remove the point on either edge that was created when they were split
			if self.__fadePointsDict.has_key(self.duration):
				del self.__fadePointsDict[self.duration]
			
			self.duration += joinEvent.duration
			self.levels.extend(joinEvent.levels)
			#update the fade point list after the level, and duration because it depends on them
			self.__UpdateAudioFadePoints()
		else:
			self.start = joinEvent.start
			self.offset = joinEvent.offset
			self.duration += joinEvent.duration
			self.levels = joinEvent.levels + self.levels
			
			newDict = joinEvent.__fadePointsDict.copy()
			for key, value in self.__fadePointsDict.iteritems():
				newDict[key + joinEvent.duration] = value
			#remove the point on either edge that was created when they were split
			if newDict.has_key(joinEvent.duration):
				del newDict[joinEvent.duration]
			self.__fadePointsDict = newDict
			self.__UpdateAudioFadePoints()
		
	#_____________________________________________________________________
	
	@UndoCommand("UndoTrim", "temp", "temp2")
	def Trim(self, start_split, end_split):
		"""
		Splits the Event and then deletes the first and last sections,
		leaving only the middle section.
		
		Parameters:
			start_split -- the time for the start of the trim.
			end_split -- the time for the end of the trim.
		"""
		# Split off the left section of the event, then put it in the graveyard for undo
		leftSplit = self.split_event(start_split, False)
		self.instrument.graveyard.append(leftSplit)
		self.temp = leftSplit.id
		
		#Adjust the end_split value since splitting the left has changed self.duration
		end_split = end_split - start_split
		
		# Split off the right section of the event, then put it in the graveyard for undo
		rightSplit = self.split_event(end_split)
		self.instrument.graveyard.append(rightSplit)
		self.temp2 = rightSplit.id
		
		self.SetProperties()
		self.StateChanged(self.LENGTH)
		
	#_____________________________________________________________________
	
	@UndoCommand("Trim", "temp", "temp2")
	def UndoTrim(self, leftID, rightID):
		"""
		Resurrects two pieces from the graveyard and joins them to
		either side of this Event.
		
		Parameters:
			leftID -- id of the left Event to be resurrected.
			rightID -- id of the right Event to be resurrected.
		"""
		leftEvent = [x for x in self.instrument.graveyard if x.id == leftID][0]
		rightEvent = [x for x in self.instrument.graveyard if x.id == rightID][0]
		
		self.temp = leftEvent.duration
		self.temp2 = leftEvent.duration + self.duration
		
		self.join_event(leftEvent, False)
		self.join_event(rightEvent)
		
		self.instrument.graveyard.remove(leftEvent)
		self.instrument.graveyard.remove(rightEvent)
		
		self.SetProperties()
		self.StateChanged(self.LENGTH)
		
	#_____________________________________________________________________
	
	@UndoCommand("Resurrect")
	def Delete(self):
		"""
		Deletes this Event and sends it to the graveyard.
		"""
		self.instrument.graveyard.append(self)
		self.instrument.events.remove(self)
		self.instrument.composition.remove(self.filesrc)

	#_____________________________________________________________________
	
	@UndoCommand("Delete")
	def Resurrect(self):
		"""
		Brings this Event back from the graveyard.
		"""
		self.instrument.events.append(self)
		self.instrument.graveyard.remove(self)
		self.CreateFilesource()
		
	#______________________________________________________________________
	
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
		if st:
			if st.get_name() == "level":
				newLevel = self.__CalculateAudioLevel(st["peak"])
				self.levels.append(newLevel)
				
				end = st["endtime"] / float(gst.SECOND)
				self.loadingLength = int(end)
				
				# Only send events every second processed to reduce GUI load
				if self.loadingLength != self.lastEnd:
					self.lastEnd = self.loadingLength 
					self.StateChanged(self.LENGTH) # tell the GUI
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
			q = self.bin.query_duration(gst.FORMAT_TIME)
			length = q[0] / float(gst.SECOND)
			
			if self.offset > 0 or self.duration != length:
				dt = int(self.duration * len(self.levels) / length)
				start = int(self.offset * len(self.levels) / length)
				self.levels = self.levels[start:start+dt]
			
			# We're done with the bin so release it
			self.bin.set_state(gst.STATE_NULL)
			self.isLoading = False
			
			# Signal to interested objects that we've changed
			self.StateChanged(self.WAVEFORM)
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
			time = self.bin.query_duration(gst.FORMAT_TIME)
			if self.duration == 0:
				self.duration = float(time[0] / float(gst.SECOND))
				#update position with proper duration
				self.MoveButDoNotOverlap(self.start)
				self.SetProperties()
				self.StateChanged(self.MOVE)
				self.StateChanged(self.LENGTH)
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
		
		Globals.debug("Event bus error:", str(error), str(debug))
		self.StateChanged(self.CORRUPT, str(error), str(debug))
	
	#_____________________________________________________________________
	
	def bus_message_tags(self, bus, message):
		"""
		Handler for catching audio file tags that Gstreamer throws.
		
		Parameters:
			bus -- GStreamer bus sending the message.
			message -- GStreamer message.
		"""
		Globals.debug("recieved group of tags")
		st = message.structure
		
		title, artist = None, None
		if st.has_key("title"):
			title = st["title"]
		if st.has_key("artist"):
			artist = st["artist"]
		
		#check which tags actually contain something
		if title and artist:
			self.name = _("%s by %s") % (title, artist)
		elif title:
			self.name = title
	
	#_____________________________________________________________________
	
	def GenerateWaveform(self):
		"""
		Renders the level information for the GUI.
		"""
		pipe = """filesrc name=src location=%s ! decodebin ! audioconvert ! level interval=%d message=true ! fakesink""" 
		pipe = pipe % (self.file.replace(" ", "\ "), self.LEVEL_INTERVAL * gst.SECOND)
		self.bin = gst.parse_launch(pipe)

		self.bus = self.bin.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)
		self.bus.connect("message::tag", self.bus_message_tags)
		self.bus.connect("message::state-changed", self.bus_message_statechange)
		self.bus.connect("message::eos", self.bus_eos)
		self.bus.connect("message::error", self.bus_error)

		self.levels = []
		self.isLoading = True

		self.bin.set_state(gst.STATE_PLAYING)

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
			newLevel = self.__CalculateAudioLevel(st["peak"])
			self.levels.append(newLevel)
			
			end = st["endtime"] / float(gst.SECOND)
			#Round to one decimal place so it updates 10 times per second
			self.loadingLength = round(end, 1)
			
			# Only send events every second processed to reduce GUI load
			if self.loadingLength != self.lastEnd:
				self.lastEnd = self.loadingLength 
				self.StateChanged(self.LENGTH) # tell the GUI
		return True
		
	#_____________________________________________________________________
	
	def __CalculateAudioLevel(self, channelLevels):
		"""
		Calculates an average for all channel levels.
		
		Parameters:
			channelLevels -- list of levels from each channel.
			
		Returns:
			an average level, also taking into account negative infinity numbers,
			which will be discarded in the average.
		"""
		negInf = float("-inf")
		peaktotal = 0
		peakcount = 0
		for peak in channelLevels:
			#don't add -inf values cause 500 + -inf is still -inf
			if peak != negInf:
				peaktotal += peak
				peakcount += 1
		#avoid a divide by zero here
		if peakcount > 0:
			peaktotal /= peakcount
		#it must be put back to -inf if nothing has been added to it, so that the DbToFloat conversion will work
		elif peakcount == 0:
			peaktotal = negInf
		
		#convert to 0...1 float, and return
		return DbToFloat(peaktotal)
		
	#_____________________________________________________________________
	
	def SetSelected(self, sel):
		"""
		Enables or disables the selection state for this Event.

		Parameters:
			sel -- the new selection state:
					True = the Event has been selected.
					False = the Event has been deselected.
		"""
		# No need to call StateChanged when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.StateChanged()
	
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
	
	@UndoCommand("RemoveAudioFadePoints", "temp", "temp2", "temp3", "temp4")
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
	
	@UndoCommand("AddAudioFadePoints", "temp", "temp2", "temp3", "temp4")
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
		self.StateChanged(self.WAVEFORM)
	
	#_____________________________________________________________________
	
	def __UpdateFadeLevels(self):
		"""
		Private function that uses the private dictionary with
		all the fade leves to update the fadeLevels list. *CHECK*
		"""
		if not self.audioFadePoints:
			#there are no fade points for us to use
			return
			
		fadePercents = []
		oneSecondInLevels = len(self.levels) / self.duration
		
		previousFade = self.audioFadePoints[0]
		for fade in self.audioFadePoints[1:]:
			#calculate the number of levels that should be in the list between the two points
			levelsInThisSection = int(round((fade[0] - previousFade[0]) * oneSecondInLevels))
			if fade[1] == previousFade[1]:
				# not actually a fade, just two points at the same volume
				fadePercents.extend([ fade[1] ] * levelsInThisSection)
			else:
				step = (fade[1] - previousFade[1]) / levelsInThisSection
				floatList = floatRange(previousFade[1], fade[1], step)
				#make sure the list of levels does not exceed the calculated length
				floatList = floatList[:levelsInThisSection]
				fadePercents.extend(floatList)
			previousFade = fade
		
		if len(fadePercents) != len(self.levels):
			#make sure its not longer than the levels list
			fadePercents = fadePercents[:len(self.levels)]
			#make sure its not shorter than the levels list
			#by copying the last level over again
			lastLevel = fadePercents[-1]
			while len(fadePercents) < len(self.levels):
				fadePercents.append(lastLevel)
				
		self.fadeLevels = []
		for i in range(len(self.levels)):
			self.fadeLevels.append(fadePercents[i] * self.levels[i])
		
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
			return self.levels[:]
			
		if len(self.fadeLevels) != len(self.levels):
			self.__UpdateFadeLevels()
			
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
