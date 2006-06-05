from CommandManager import *
import Project
import xml.dom.minidom as xml
import pygst
pygst.require("0.10")
import gst
import gtk
import os, stat    #for file's timestamp
from Monitored import *
from Utils import *

#=========================================================================	

class Event(Monitored, CommandManaged):
	
	#_____________________________________________________________________
	
	def __init__(self, instrument, file=None, id=None):
		Monitored.__init__(self)
		
		self.start = 0.0			# Time in seconds at which the event begins
		self.duration = 0.0			# Duration in seconds of the event
		self.file = file			# The file this event should play
		self.colour = "#FFEEEE"
		self.isSelected = False		# True if the event is currently selected
		self.name = "New Event"		# Name of this event
		self.isLHSHot = False
		self.isRHSHot = False
		self.levels = []			# Array of audio levels to be drawn for this event
		
		self.id = instrument.project.GenerateUniqueID(id)  #check is id is already taken, then set it.
		self.instrument = instrument	# The parent instrument
		self.filesrc = None
		
		self.offset = 0.0			# Offset through the file in seconds
		self.isLoading = False		# True if the event is currently loading level data
		self.loadingLength = 0
		self.lastEnd = 0
		
		self.CreateFilesource()
	#_____________________________________________________________________
	
	def CreateFilesource(self):	
		print "create file source"
		if not self.filesrc:
			self.filesrc = gst.element_factory_make("gnlfilesource", "Event_%d"%self.id)
		if not self.filesrc in list(self.instrument.composition.elements()):
			self.instrument.composition.add(self.filesrc)
		
		self.SetProperties()
		
	#_____________________________________________________________________
		
	def SetProperties(self):
		if self.file:
			print "start set properties"
			gst.debug("setting event properties")
			self.filesrc.set_property("location", self.file)
			self.filesrc.set_property("start", long(self.start * gst.SECOND))
			self.filesrc.set_property("duration", long(self.duration * gst.SECOND))
			self.filesrc.set_property("media-start", long(self.offset * gst.SECOND))
			self.filesrc.set_property("media-duration", long(self.duration * gst.SECOND))
			
			print "event properties set"

	#_____________________________________________________________________

	def StoreToXML(self, doc, parent, graveyard=False):
		if graveyard:
			ev = doc.createElement("DeadEvent")
		else:
			ev = doc.createElement("Event")
		parent.appendChild(ev)
		ev.setAttribute("id", str(self.id))
		
		params = doc.createElement("Parameters")
		ev.appendChild(params)
		
		items = ["start", "duration", "colour", "isSelected", 
				  "name", "offset", "file"
				]
		
		StoreParametersToXML(self, doc, params, items)
		
		if self.levels:
			modified = doc.createElement("FileLastModified")
			ev.appendChild(modified)
			timestamp = str(os.stat(self.file)[stat.ST_MTIME])
			modified.setAttribute("value", timestamp)
			
			levelsXML = doc.createElement("Levels")
			ev.appendChild(levelsXML)
			stringList = map(str, self.levels)
			levelsXML.setAttribute("value", ",".join(stringList))
			
	#_____________________________________________________________________
			
	def LoadFromXML(self, node):
		params = node.getElementsByTagName("Parameters")[0]
		
		LoadParametersFromXML(self, params)
		
		fileModified = True
		try:
			n = node.getElementsByTagName("FileLastModified")[0]
		except IndexError:
			pass
		else:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				value = int(n.getAttribute("value"))
				timestamp = os.stat(self.file)[stat.ST_MTIME]
				fileModified = timestamp > value
		
		if fileModified:
			self.GenerateWaveform()
		else:
			try:	
				levelsXML = node.getElementsByTagName("Levels")[0]
			except IndexError:
				print "No event levels in project file"
				self.GenerateWaveform()
			else: 
				if levelsXML.nodeType == xml.Node.ELEMENT_NODE:
					value = str(levelsXML.getAttribute("value"))
					self.levels = map(float, value.split(","))
		
		self.CreateFilesource()
		
	#_____________________________________________________________________
		
	def __repr__(self):
		return "Event: '%s' (%d) : %d -> %d" % (self.name, self.id, self.start, self.duration)
		
	#_____________________________________________________________________
	
	def Move(self, frm, to):
		'''
			undo : Move(%(start)f, %(temp)f)
		'''
		self.temp = frm
		self.start = to
	
	#_____________________________________________________________________
	
	def Split(self, split_point, id=-1):
		'''
			Splits this event at time offset split_point in seconds. If
			id is specified, then the created event will be pulled from
			the graveyard (for undo/redo compatibility). Returns the
			newly created event, which is the one on the right (after the splitpoint).
		
			undo : Join(%(temp)d)
		'''
		d = self.duration
		self.duration = split_point
		
		if id == -1:
			e = Event(self.instrument, self.file)
			e.start = self.start + split_point
			e.offset = self.offset + split_point
			e.duration = d - split_point
			e.file = self.file
			nl = int(len(self.levels) * (split_point / d))
			e.levels = self.levels[nl:]
			self.levels = self.levels[:nl]
			e.name = self.name
			self.instrument.events.append(e)
			self.temp = e.id
			self.StateChanged()
			return e
		else:
			event = [x for x in self.instrument.graveyard if x.id == id][0]
			self.instrument.events.append(event)
			
			nl = int(len(self.levels) * (split_point / d))
			self.levels = self.levels[:nl]
			
			self.temp = event.id
			self.StateChanged()
		
	#_____________________________________________________________________

	def Join(self, joinEvent):
		''' Joins 2 events together. 

			undo : Split(%(temp)f, %(temp2)d)
		'''

		event = [x for x in self.instrument.events if x.id == joinEvent][0]

		# Note that at this point, the joined event will retain the name
		# and file of the leftEvent
		self.temp = self.duration
		self.duration = self.duration + event.duration
		self.levels = self.levels + event.levels

		# Now that they're joined, move rightEvent to the graveyard
		self.instrument.events.remove(event)
		self.instrument.graveyard.append(event)
		self.temp2 = event.id
		self.StateChanged()


	#_____________________________________________________________________
	
	def Delete(self):
		"""	
			undo : Resurrect()
		"""
		self.instrument.graveyard.append(self)
		self.instrument.events.remove(self)
		self.instrument.composition.remove(self.filesrc)

	#_____________________________________________________________________
	
	def Resurrect(self):
		"""
			undo : Delete()
		"""
		self.instrument.events.append(self)
		self.instrument.graveyard.remove(self)
		self.CreateFilesource()
		
	#______________________________________________________________________
				
	def bus_message(self, bus, message):
		if not self.isLoading:
			return False
		st = message.structure
		if st:
			if st.get_name() == "level":
				end = st["endtime"] / 1000000000.
				self.levels.append(DbToFloat(st["peak"][0]))
				self.loadingLength = int(end)
											
				# Only send events every second processed to reduce GUI load
				if self.loadingLength != self.lastEnd:
					self.lastEnd = self.loadingLength 
					self.StateChanged() # tell the GUI
		return True
		
	def bus_eos(self, bus, message):	
		if message.type == gst.MESSAGE_EOS:
			
			# Update levels for partial events
			q = self.bin.query_duration(gst.FORMAT_TIME)
			length = q[0] / 1000000000
			
			if self.offset > 0 or self.duration != length:
				dt = int(self.duration * len(self.levels) / length)
				start = int(self.offset * len(self.levels) / length)
				self.levels = self.levels[start:start+dt]
			
			# We're done with the bin so release it
			self.bin.set_state(gst.STATE_NULL)
			self.isLoading = False

			# Signal to interested objects that we've changed
			self.StateChanged()
			return False

	def bus_message_statechange(self, bus, message):	
		# state has changed
		try:
			q = self.bin.query_duration(gst.FORMAT_TIME)
			if self.duration == 0:
				self.duration = float(q[0] / 1000000000)
				self.SetProperties()
		except:
			# no size available yet
			pass
	
	def GenerateWaveform(self):
		""" Renders the level information for the GUI
		"""
		
		pipe = """filesrc name=src location=%s ! decodebin ! audioconvert ! 
		level interval=100000000 message=true ! 
		progressreport name=prog silent=true update-freq=1 ! fakesink""" % self.file
		self.bin = gst.parse_launch(pipe)

		src = self.bin.get_by_name("src")

		self.bus = self.bin.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)
		self.bus.connect("message::state-changed", self.bus_message_statechange)
		self.bus.connect("message::eos", self.bus_eos)
			 
		self.levels = []
		self.isLoading = True

		self.bin.set_state(gst.STATE_PLAYING)

		return	
	#_____________________________________________________________________

	def SetSelected(self, sel):
		self.isSelected = sel
		self.StateChanged()
	
	#_____________________________________________________________________


#=========================================================================	
