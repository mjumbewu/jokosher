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

from CommandManager import *
import xml.dom.minidom as xml
import pygst
pygst.require("0.10")
import gst
from Monitored import *
from Utils import *
import os, Globals

#=========================================================================

class Event(Monitored, CommandManaged):
	""" This class handles maintaing the information for a single audio 
		event. This is normally a fragment of a recorded file.
	"""
	
	#state changed types (to be sent through the Monitored class)
	WAVEFORM, MOVE, LENGTH, CORRUPT = range(4)
	
	#_____________________________________________________________________
	
	def __init__(self, instrument, file=None, id=None, filelabel=None):
		Monitored.__init__(self)
		
		self.start = 0.0			# Time in seconds at which the event begins
		self.duration = 0.0			# Duration in seconds of the event
		# The file this event should play (without escaped characters)
		# If you need characters escaped, please do self.file.replace(" ", "\ ") 
		# but **do not** assign it to this variable.
		self.file = file

		# the label is the filename to print in error messages
		# if it differs from the real filename (i.e its been copied into the project)
		if filelabel!=None:
			self.filelabel = filelabel
		else:
			self.filelabel = file

		self.isSelected = False		# True if the event is currently selected
		self.name = "New Event"		# Name of this event
		
		self.selection  = [0, 0]			# List start and end of selection (for fades, etc) measured in seconds 
		self.levels = []			# Array of audio levels to be drawn for this event
		
		self.id = instrument.project.GenerateUniqueID(id)  #check is id is already taken, then set it.
		self.instrument = instrument	# The parent instrument
		self.filesrc = None 			# The gstreamer gnlfilesource object.
		
		self.offset = 0.0			# Offset through the file in seconds
		self.isLoading = False		# True if the event is currently loading level data
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
		Globals.debug("create file source")
		if not self.filesrc:
			self.filesrc = gst.element_factory_make("gnlfilesource", "Event_%d"%self.id)
		if not self.filesrc in list(self.instrument.composition.elements()):
			self.instrument.composition.add(self.filesrc)
		
		self.SetProperties()
		
	#_____________________________________________________________________
		
	def SetProperties(self):
		if self.file:
			Globals.debug("setting event properties")
			self.filesrc.set_property("location", self.file)
			self.filesrc.set_property("start", long(self.start * gst.SECOND))
			self.filesrc.set_property("duration", long(self.duration * gst.SECOND))
			self.filesrc.set_property("media-start", long(self.offset * gst.SECOND))
			self.filesrc.set_property("media-duration", long(self.duration * gst.SECOND))
			self.filesrc.set_property("priority", 2)
			
			Globals.debug("location = " + self.file)
			Globals.debug("start = " + str(long(self.start * gst.SECOND)))
			Globals.debug("duration = " + str(long(self.duration * gst.SECOND)))
			Globals.debug("media-start = " + str(long(self.offset * gst.SECOND)))
			Globals.debug("media-duration = " + str(long(self.duration * gst.SECOND)))
			
			Globals.debug("event properties set")

	#_____________________________________________________________________

	def StoreToXML(self, doc, parent, graveyard=False):
		""" Converts this Event into an XML representation suitable for 
			saving to a file.

			doc
				The XML dcxument object we're saving to.
			parent
				The parent node that the serialised Event should be added
				to.
			graveyard
				True if this Event is on the graveyard stack, and should
				be serialised as a dead event.
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
		""" Restores an event from its serialised XML representation.

			node
				The XML node to retreive data from.
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

		if self.isLoading == True:
			self.GenerateWaveform()

		self.__UpdateAudioFadePoints()
		self.CreateFilesource()
		
	#_____________________________________________________________________
		
	def __repr__(self):
		return "Event: '%s' (%d) : %d -> %d" % (self.name, self.id, self.start, self.duration)
		
	#_____________________________________________________________________
	
	def __cmp__(self, object):
		if type(object) != type(self):
			return -1
		else:
			# If cmp(self.start, object.start) is not zero, return it.
			# If it is zero, return cmp(seld.id, object.id).
			return cmp(self.start, object.start) or cmp(self.id, object.id)
	
	#_____________________________________________________________________
	
	def Move(self, frm, to):
		'''	Moves this Event.

			frm
				The time we're moving from.
			to
				The time we're moving to.

			undo : Move: start, temp
		'''
		self.temp = frm
		self.start = to
		self.SetProperties()
	
	#_____________________________________________________________________
	
	def Split(self, split_point, id=-1):
		'''
			Splits this event at time offset split_point in seconds. If
			id is specified, then the created event will be pulled from
			the graveyard (for undo/redo compatibility). Returns the
			newly created event, which is the one on the right (after the splitpoint).
		
			undo : Join: temp
		'''		
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
	
	def Join(self, joinEventID):
		''' Joins 2 events together. 

			joinEventID
				The ID of the Event to join to this one.

			undo : Split: temp, temp2
		'''
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
		"""helper function for Split() and Trim(). All other methods and classes
		   should not invoke this function directly since there is no undo for it.
		   
		   If cutRightSide is True, a new event will be created to represent 
		   the piece on the right which was split. This instance will be the one on the left.
		   If cutRightSide is False, this instance is the one on the right.
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
		"""helper function for Join() and Trim(). All other methods and classes
		   should not invoke this function directly since there is no undo for it.
		   
		   After joining the events on either side, this method will not remove the event
		   from the instrument lane. This must be done from the function that called this one.
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
	
	def Trim(self, start_split, end_split):
		""" Splits the event at points start_split and end_split
		    and then deletes the first and last sections leaving only
		    the middle section.

		    start_split
		   		The time for the start of the trim
			end_split
				The time for the end of the trim
		   
		    undo : UndoTrim: temp, temp2
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
	
	def UndoTrim(self, leftID, rightID):
		"""Resurrects two pieces from the graveyard and joins them to
		   either side of this event.
		   
		   undo : Trim: temp, temp2
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
	
	def Delete(self):
		"""	Deletes this Event and sends it to the graveyard to reflect
			on what it has done.

			undo : Resurrect
		"""
		self.instrument.graveyard.append(self)
		self.instrument.events.remove(self)
		self.instrument.composition.remove(self.filesrc)

	#_____________________________________________________________________
	
	def Resurrect(self):
		""" Brings this Event back from the graveyard.

			undo : Delete
		"""
		self.instrument.events.append(self)
		self.instrument.graveyard.remove(self)
		self.CreateFilesource()
		
	#______________________________________________________________________
				
	def bus_message(self, bus, message):
		""" Handler for the GStreamer bus messages relevant to this Event. 
			At the moment this is used to report on how the loading 
			progress is going.
		"""

		if not self.isLoading:
			return False

		st = message.structure
		if st:
			if st.get_name() == "level":
				end = st["endtime"] / float(gst.SECOND)
				self.levels.append(DbToFloat(st["peak"][0]))
				self.loadingLength = int(end)
											
				# Only send events every second processed to reduce GUI load
				if self.loadingLength != self.lastEnd:
					self.lastEnd = self.loadingLength 
					self.StateChanged(self.LENGTH) # tell the GUI
		return True
		
	#_____________________________________________________________________
		
	def bus_eos(self, bus, message):	
		""" Handler for the GStreamer End Of Stream message. Currently
			used when the file is loading and is being rendered. This
			function is called at the end of the file loading process and
			finalises the rendering.
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
		""" Handler for the GStreamer statechange message.
		"""
		# state has changed
		try:
			q = self.bin.query_duration(gst.FORMAT_TIME)
			if self.duration == 0:
				self.duration = float(q[0] / float(gst.SECOND))
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
		""" Handler for when things go completely wrong with GStreamer.
		"""
		Globals.debug("bus error")
		self.StateChanged(self.CORRUPT)
	
	#_____________________________________________________________________
	
	def GenerateWaveform(self):
		""" Renders the level information for the GUI.
		"""
		pipe = """filesrc name=src location=%s ! decodebin ! audioconvert ! 
		level interval=100000000 message=true ! fakesink""" % self.file.replace(" ", "\ ")
		self.bin = gst.parse_launch(pipe)

		self.bus = self.bin.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)
		self.bus.connect("message::state-changed", self.bus_message_statechange)
		self.bus.connect("message::eos", self.bus_eos)
		self.bus.connect("message::error", self.bus_error)

		self.levels = []
		self.isLoading = True

		self.bin.set_state(gst.STATE_PLAYING)

	#_____________________________________________________________________

	def SetSelected(self, sel):
		""" Enables or disables the selection state for this event.

			sel
				The new selection state (Should be True or False).
		"""
		# No need to call StateChanged when there is no change in selection state
		if self.isSelected is not sel:
			self.isSelected = sel
			self.StateChanged()
	
	#_____________________________________________________________________
	
	def MayPlace(self, xpos):
		""" Checks if this event could be placed at xpos without 
			overlapping another Event on the same Instrument.

			xpos
				The potential start position to check
			Returns
				True if it's OK to place the Event at xpos, false if not.
		"""
		for e in self.instrument.events:
			if e is self:
				continue
			if not (e.start + e.duration <= xpos or e.start >= xpos + self.duration):
				return False
		return True
		
	#_____________________________________________________________________
	
	def MoveButDoNotOverlap(self, xpos):
		"""This method will attempt to move this event to the given position (xpos)
		   If the position requires overlapping, this event will be put flush
		   against the closest side of the event which is in the way.
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
	
	def AddAudioFadePoints(self, firstPoint, secondPoint, firstVolume, secondVolume):
		"""
		   Add the two passed points to the audioFadePoints list.
		   If either point exists already, replace it, and resort
		   the list by time.
		   
		   undo : RemoveAudioFadePoints: temp, temp2, temp3, temp4
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
	
	def RemoveAudioFadePoints(self, firstPoint, secondPoint, firstOldVolume=None, secondOldVolume=None):
		"""
		   Removed a point with values from the fade list.
		   If firstOldVolume and secondOldVolume are given,
		   the levels at the two points will be replaces with the
		   old volumes instead of being removed.
		    
		   undo : AddAudioFadePoints: temp, temp2, temp3, temp4
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
		   Returns a list of levels, the same length as the levels list.
		   The only difference between this list and the levels list is
		   that the levels in this list are scaled according to and fade
		   curves applied to the current event.
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
		   Returns the level of the audio in percent (0-1)
		   at the point given my time (in seconds)
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
