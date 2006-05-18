from Event import *
from CommandManager import *
import Project
import xml.dom.minidom as xml
import pygst
pygst.require("0.10")
import gst
import os
import time
from Monitored import *
import gobject
import AddInstrumentDialog
import Globals

#=========================================================================	

class Instrument(Monitored, CommandManaged):
	
	#_____________________________________________________________________
	
	def __init__(self, project, name, pixbuf, pixbufPath, id=None):
		Monitored.__init__(self)
		
		self.project = project
		
		self.path = ""
		self.events = []				# List of events attached to this instrument
		self.name = name				# Name of this instrument
		self.pixbuf = pixbuf			# The icon pixbuf resource
		self.pixbufPath = pixbufPath	# The path to the icon
		self.isArmed = False			# True if the instrument is armed for recording
		self.isMuted = False			# True if the "mute" button is toggled on
		self.actuallyIsMuted = False		# True if the instrument is muted (silent)
		self.isSolo = False				# True if the instrument is solo'd (only instrument active)
		self.isVisible = True			# True if the instrument should be displayed in the mixer views
		self.level = 0.0				# Current audio level in range 0..1
		self.volume = 0.5				# Gain of the current instrument in range 0..1
		
		try:
			indevice = Globals.settings.recording["devicecardnum"]
		except:
			indevice =  "default"
		self.input = "alsasrc device=" + indevice
		self.output = ""
		self.effects = " ! "
		self.bin = None
		if id:
			self.id = id				# Unique object ID
		else:
			self.id = Project.GenerateUniqueID()
		self.isSelected = False			# True if the instrument is currently selected
		
		# GStreamer pipeline elements for this instrument		
		self.volumeElement = gst.element_factory_make("volume", "Instrument_Volume_%d"%self.id)
		self.converterElement = gst.element_factory_make("audioconvert", "Instrument_Converter_%d"%self.id)
		self.levelElement = gst.element_factory_make("level", "Instrument_Level_%d"%self.id)
		self.levelElement.set_property("interval", gst.SECOND / 50)
		self.levelElement.set_property("message", True)
		self.levelElement.set_property("peak-ttl", 0)
		self.levelElement.set_property("peak-falloff", 20)

		self.project.bin.add(self.volumeElement)
		print "added volume (instrument)"

		self.project.bin.add(self.levelElement)
		print "added level (instrument)"

		self.project.bin.add(self.converterElement)
		print "added audioconvert (instrument)"
		
		self.composition = gst.element_factory_make("gnlcomposition")

		self.project.bin.add(self.composition)
		print "added composition (instrument)"

		# link elements
		
		self.converterElement.link(self.volumeElement)
		print "linked instrument audioconvert to instrument volume (project)"

		self.volumeElement.link(self.levelElement)
		print "linked instrument volume to instrument level (project)"

		self.levelElement.link(self.project.adder)
		print "linked instrument level to adder (project)"

		self.composition.connect("pad-added", self.project.newPad, self)
		self.composition.connect("pad-removed", self.project.removePad, self)
		
		#mute this instrument if another one is solo
		self.OnMute()
		
	#_____________________________________________________________________
	
	def __repr__(self):
		return "Instrument [%d] %s"%(self.id, self.name)
		
	#_____________________________________________________________________
		
	def StoreToXML(self, doc, parent):
		ins = doc.createElement("Instrument")
		parent.appendChild(ins)
		
		items = ["id", "path", "name", "isArmed", 
				  "isMuted", "isSolo", "input", "output", "effects",
				  "isSelected", "pixbufPath", "isVisible"]
		
		params = doc.createElement("Parameters")
		ins.appendChild(params)
		
		for i in items:
			node = doc.createElement(i)
			
			if type(getattr(self, i)) == int:
				node.setAttribute("type", "int")
			elif type(getattr(self, i)) == float:
				node.setAttribute("type", "float")
			elif type(getattr(self, i)) == bool:
				node.setAttribute("type", "bool")
			else:
				node.setAttribute("type", "str")
			
			node.setAttribute("value", str(getattr(self, i)))
			params.appendChild(node)
			
		for e in self.events:
			e.StoreToXML(doc, ins)
			
	#_____________________________________________________________________	
			
	def LoadFromXML(self, node):
		
		params = node.getElementsByTagName("Parameters")[0]
		
		for n in params.childNodes:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				if n.getAttribute("type") == "int":
					setattr(self, n.tagName, int(n.getAttribute("value")))
				elif n.getAttribute("type") == "float":
					setattr(self, n.tagName, float(n.getAttribute("value")))
				elif n.getAttribute("type") == "bool":
					if n.getAttribute("value") == "True":
						setattr(self, n.tagName, True)
					elif n.getAttribute("value") == "False":
						setattr(self, n.tagName, False)
				else:
					setattr(self, n.tagName, n.getAttribute("value"))
					
		events = node.getElementsByTagName("Event")
		for ev in events:
			e = Event(None)
			e.instrument = self
			e.LoadFromXML(ev)
			self.events.append(e)
		
		#load image from file based on saved path
		#TODO replace this with proper cache manager
		for i in AddInstrumentDialog.getCachedInstruments():
			if self.pixbufPath == i[4]:
				self.pixbuf = i[1]
				break
		if not self.pixbuf:
			print "Error, could not load image:", pixbufPath
			
		#initialize the actuallyIsMuted variable
		self.checkActuallyIsMuted()

	#_____________________________________________________________________

	def addEffect(self, effect):
		'''Add instrument specific gstreamer elements'''
		self.effects += effect + " ! "
	
	#_____________________________________________________________________
	
	def record(self):
		'''Record to this instrument's temporary file.'''
		if self.input == "alsasrc device=value":
			self.input = "alsasrc device=default"

		#Create event file based on timestamp
		file = "%s_%d_%d.ogg"%(os.path.join(self.path, self.name), self.id, int(time.time()))
		self.tmpe = Event(self)
		self.tmpe.start = 0
		self.tmpe.name = "Recorded audio"
		self.tmpe.file = file

		self.output = "audioconvert ! vorbisenc ! oggmux ! filesink location=" + file
		print "Using pipeline:", self.input + self.effects + self.output

		self.bin = gst.parse_launch(self.input + self.effects + self.output)
		self.bin.set_state(gst.STATE_PLAYING)
		gobject.idle_add(self.bin.elements)


	#_____________________________________________________________________

	def stop(self):
		if self.bin:
			self.bin.set_state(gst.STATE_NULL)
			self.events.append(self.tmpe)
			self.tmpe.GenerateWaveform()
			self.temp = self.tmpe.id
			self.StateChanged()
			
	#_____________________________________________________________________
	
	def addEventFromFile(self, start, file):
		''' Adds an event to this instrument, and attaches the specified
			file to it. 
			
			start - The offset time in seconds
			file - file path
		
			undo : DeleteEvent(%(temp)d)
		'''
		
		e = Event(self)
		e.start = start
		e.name = file.split(os.sep)[-1]
		e.file = file
		self.events.append(e)
		e.GenerateWaveform()

		self.temp = e.id
		
		self.StateChanged()
		
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
		self.StateChanged()
	
	#_____________________________________________________________________

	def SetVolume(self, volume):
		"""Sets the volume of the instrument in the range 0..1
		"""
		self.volume = volume
		self.volumeElement.set_property("volume", volume)

	#_____________________________________________________________________
	
	def SetName(self, name):
		"""Sets the instrument to the given name
		   so it can be registered in the undo stack
		
		   undo : SetName("%(temp)s")
		"""
		self.temp = self.name
		self.name = name
		self.StateChanged()
	
	#_____________________________________________________________________
	
	def ToggleArmed(self):
		"""Toggles the instrument to be armed for recording
		
		   undo : ToggleArmed()
		"""
		self.isArmed = not self.isArmed
		self.StateChanged()
		
	#_____________________________________________________________________
	
	def ToggleMuted(self, wasSolo):
		"""Toggles the instrument to be muted
		
		   undo : ToggleMuted(%(temp)d)
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
	
	def ToggleSolo(self, wasMuted):
		"""Toggles the all the other instruments muted
		
		   undo : ToggleSolo(%(temp)d)
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
	
	def SetVisible(self, visible):
		"""Sets wheather the instrument is minimized in CompactMixView
		
		   undo : SetVisible(%(temp)d)
		"""
		self.temp = self.isVisible
		self.isVisible = visible
		self.StateChanged()
	
	#_____________________________________________________________________
	
	def SetSelected(self):
		"""Sets the instrument to be highlighted 
		   and receive keyboard actions
		"""
		self.project.ClearInstrumentSelections()
		self.project.ClearEventSelections()
		self.isSelected = True
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
#=========================================================================	
