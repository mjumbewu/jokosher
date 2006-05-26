
import gobject
import gtk
import pygst
pygst.require("0.10")
import gst
import os
import sys
from math import *
import gzip
import TransportManager
import ConfigParser
import traceback
import tempfile
from CommandManager import *
import Globals
import xml.dom.minidom as xml
from Instrument import *
from Monitored import *
from Utils import *

#=========================================================================

___id_counter = 0

#_____________________________________________________________________

def GenerateUniqueID():
	global ___id_counter
	___id_counter += 1
	return ___id_counter

#_____________________________________________________________________

def LoadFromFile(file):	
	p = Project()
	try:
		gzipfile = gzip.GzipFile(file, "r")
		doc = xml.parse(gzipfile)
	except Exception, e:
		print e.__class__, e
		raise OpenProjectError
	
	p.projectfile = file
	
	params = doc.getElementsByTagName("Parameters")[0]
	for n in params.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			if n.getAttribute("type") == "int":
				setattr(p, n.tagName, int(n.getAttribute("value")))
			elif n.getAttribute("type") == "float":
				setattr(p, n.tagName, float(n.getAttribute("value")))
			elif n.getAttribute("type") == "bool":
				if n.getAttribute("value") == "True":
					setattr(p, n.tagName, True)
				elif n.getAttribute("value") == "False":
					setattr(p, n.tagName, False)
			else:
				setattr(p, n.tagName, n.getAttribute("value"))
	
	try:
		undo = doc.getElementsByTagName("Undo")[0]
	except IndexError:
		print "No saved undo in project file"
	else:
		for n in undo.childNodes:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				p.savedUndoStack.append(str(n.getAttribute("value")))
	
	try:
		redo = doc.getElementsByTagName("Redo")[0]
	except IndexError:
		print "No saved redo in project file"
	else:
		for n in redo.childNodes:
			if n.nodeType == xml.Node.ELEMENT_NODE:
				p.redoStack.append(str(n.getAttribute("value")))
	
	for instr in doc.getElementsByTagName("Instrument"):
		i = Instrument(p, None, None, None)
		i.LoadFromXML(instr)
		p.instruments.append(i)
		if i.isSolo:
			p.soloInstrCount += 1
		

	p.startTransportThread()
	return p

#_____________________________________________________________________	

#=========================================================================

class Project(Monitored, CommandManaged):
	
	""" This class maintains all of the information required about single
		project.
	"""
	
	VERSION = 0.1	# The project structure version. Will be useful for handling old save files

	#_____________________________________________________________________

	def __init__(self):
		global GlobalProjectObject
		
		Monitored.__init__(self)
		
		# set up some important lists and dictionaries:
		self.instruments = []
		
		self.author = "<none>"
		self.name = "<no project loaded>"
		
		# the name of the project file, complete with path
		self.projectfile = ""
		
		self.bin = None
		
		#mode for transport manager that hasn't been initialized yet
		self.transportMode = TransportManager.TransportManager.MODE_BARS_BEATS
		
		# View scale as pixels per second
		self.viewScale = 25.
		
		# View offset in seconds
		self.viewStart= 0.
		
		#number of solo instruments (to know if others must be muted)
		self.soloInstrCount = 0
		
		# The place where deleted objects go
		self.graveyard = []
		
		#This is to indicate that something which is not 
		#on the undo/redo stack needs to be saved
		self.unsavedChanges = False
		
		# Storage for the undo/redo states
		self.undoStack = []
		self.redoStack = []
		self.savedUndoStack = []
		self.savedRedoStack = []
		self.performingUndo = False
		self.performingRedo = False
		self.savedUndo = False

		self.IsPlaying = False
		
		self.RedrawTimeLine = False

		self.bin = gst.Pipeline("timeline")
		print "created pipeline (project)"
		
		self.adder = gst.element_factory_make("adder")
		self.bin.add(self.adder)
		print "added adder (project)"

		self.convert = gst.element_factory_make("audioconvert")
		self.bin.add(self.convert)
		# need to restrict the format on adder's output
		caps = gst.caps_from_string ("audio/x-raw-int,"
		    "rate=44100,channels=2,endianness=1234,width=16,depth=16,signed=(boolean)true")
		self.adder.link(self.convert, caps)
		print "added audioconvert (project)"

		self.level = gst.element_factory_make("level", "MasterLevel")
		self.level.set_property("interval", gst.SECOND / 50)
		self.level.set_property("message", True)
		self.bin.add(self.level)
		print "added master level (project)"

		self.convert.link(self.level)

		self.out = gst.element_factory_make("alsasink")
		
		try:
			outdevice = Globals.settings.playback["devicecardnum"]
		except:
			outdevice =  "default"
		if outdevice == "value":
			outdevice = "default"
		self.out.set_property("device", outdevice)

		self.bin.add(self.out)
		print "added alsasink (project)"

		self.level.link(self.out)
		self.bus = self.bin.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect("message::element", self.bus_message)


		# [DEBUG]
		# This debug block will be removed when we release. If you see this in a release version, we
		# obviously suck. Please email us and tell us about how shit we are.

		try:
			if os.environ['JOKOSHER_DEBUG']:
				print "Enabling Jokosher Debugging..."
				import JokDebug
				self.debug = JokDebug.JokDebug()
		except:
			pass
		# [/DEBUG]


	#_____________________________________________________________________
	
	def startTransportThread(self):
		self.transport = TransportManager.TransportManager(self.transportMode)
	
	#_____________________________________________________________________
		
	def record(self):
		'''Start all selected instruments recording'''
		for instr in self.instruments:
			if instr.isArmed:
				instr.record()
				
	#_____________________________________________________________________
				
	def play(self, export=False, filename=None):
		'''Set all instruments playing'''
		
		if len(self.instruments) > 0:

			if export:
				#Create pipeline for exporting to file
				if filename[-3:] == "ogg":
					encode = gst.element_factory_make("vorbisenc")
					encode.set_property("quality", 1);
					mux = gst.element_factory_make("oggmux")
					self.bin.add(mux)
				elif filename[-3:] == "mp3":
					encode = gst.element_factory_make("lame")
				else:
					print "Unknown filetype for export"
					self.stop()
					return
				self.bin.add(encode)
				convert.link(encode)
				if filename[-3:] == "ogg":
					encode.link(mux)
					mux.link(self.out)
				else:
					encode.link(self.out)
			else:
				pass
				

			gst.debug("Play pressed, about to set state to PLAYING")
			
			# And set it going
			self.bin.set_state(gst.STATE_PLAYING)
			self.IsPlaying = True

			gst.debug("just set state to PLAYING")

			# [DEBUG]
			# This debug block will be removed when we release. If you see this in a release version, we
			# obviously suck. Please email us and tell us about how shit we are.
			try:
				if os.environ['JOKOSHER_DEBUG']:
					print "Play Pipeline:"
					self.debug.ShowPipelineTree(self.bin)
			except:
				pass
			# [/DEBUG]


	#_____________________________________________________________________

	def bus_message(self, bus, message):
		#print bus, message
		st = message.structure
		if st:
			if st.get_name() == "level":
				if message.src.get_name() == "MasterLevel":
					position = float(st["endtime"]) / gst.SECOND
					self.transport.SetPosition(position)
				else:
					id = int(message.src.get_name().split("_")[-1])
					for instr in self.instruments:
						if instr.id == id:
							instr.SetLevel(DbToFloat(st["decay"][0]))
							break
		return True

	#_____________________________________________________________________
				
	def newPad(self, element, pad, instrument):
		print "before new pad"
		print pad
		convpad = instrument.converterElement.get_compatible_pad(pad, pad.get_caps())
		pad.link(convpad)
		print "linked composition to instrument audioconvert (project)"
		
		#instrument.converterElement.link(instrument.volumeElement)
		#print "linked instrument audioconvert to instrument volume (project)"

		#instrument.volumeElement.link(instrument.levelElement)
		#print "linked instrument volume to instrument level (project)"

		#instrument.levelElement.link(self.adder)
		#print "linked instrument level to adder (project)"

	#_____________________________________________________________________

	def removePad(self, element, pad, instrument):
		print "pad removed"
#		print pad
#		convpad = instrument.converterElement.get_compatible_pad(pad, pad.get_caps())
#		pad.unlink(convpad)
		instrument.composition.set_state(gst.STATE_READY)

	#_____________________________________________________________________

	#Alias to self.play
	def export(self, filename):
		'''Export to ogg/mp3'''
		self.play(True, filename)

	#_____________________________________________________________________
	
	def stop(self):
		'''Stop playing or recording'''
		for instr in self.instruments:
			instr.stop()

		if self.bin:
			#self.bin.remove(instr.converterElement)
			#print "removed instrument audioconvert (project)"
			
			#self.bin.remove(instr.volumeElement)
			#print "removed instrument volume (project)"

			#self.bin.remove(instr.levelElement)
			#print "removed instrument level (project)"

			gst.debug("Stop pressed, about to set state to PAUSED")

			self.bin.set_state(gst.STATE_PAUSED)
			self.IsPlaying = False
			
			gst.debug("Stop pressed, state just set to PAUSED")

			print "PIPELINE AFTER STOP:"
			# [DEBUG]
			# This debug block will be removed when we release. If you see this in a release version, we
			# obviously suck. Please email us and tell us about how shit we are.
			try:
				if os.environ['JOKOSHER_DEBUG']:
					print "Play Pipeline:"
					self.debug.ShowPipelineTree(self.bin)
			except:
				pass
			# [/DEBUG]
			
		self.transport.Stop()
			
	#_____________________________________________________________________
	
	def saveProjectFile(self, path=None):
		""" Saves the project and its children as an XML file 
			to the path specified by file.
		"""
		
		if not path:
			if not self.projectfile:
				raise "No save path specified!"
			path = self.projectfile
			
		#sync the transport's mode with the one which will be saved
		self.transportMode = self.transport.mode
		
		self.unsavedChanges = False
		#purge main undo stack so that it will not prompt to save on exit
		self.savedUndoStack.extend(self.undoStack)
		self.undoStack = []
		#purge savedRedoStack so that it will not prompt to save on exit
		self.redoStack.extend(self.savedRedoStack)
		self.savedRedoStack = []
		
		doc = xml.Document()
		head = doc.createElement("JokosherProject")
		doc.appendChild(head)
		
		vers = doc.createElement("Version")
		vers.appendChild(doc.createTextNode(str(self.VERSION)))
		head.appendChild(vers)
		
		params = doc.createElement("Parameters")
		head.appendChild(params)
		
		items = ["viewScale", "viewStart", "name", "author", "transportMode"]
		
		for i in items:
			e = doc.createElement(i)
			if type(getattr(self, i)) == int:
				e.setAttribute("type", "int")
			elif type(getattr(self, i)) == float:
				e.setAttribute("type", "float")
			elif type(getattr(self, i)) == bool:
				e.setAttribute("type", "bool")
			else:
				e.setAttribute("type", "str")
			e.setAttribute("value", str(getattr(self, i)))
			params.appendChild(e)
			
		undo = doc.createElement("Undo")
		head.appendChild(undo)
		for cmd in self.savedUndoStack:
			e = doc.createElement("Command")
			e.setAttribute("value", str(cmd))
			undo.appendChild(e)
		
		redo = doc.createElement("Redo")
		head.appendChild(redo)
		for cmd in self.redoStack:
			e = doc.createElement("Command")
			e.setAttribute("value", str(cmd))
			redo.appendChild(e)
			
		for i in self.instruments:
			i.StoreToXML(doc, head)
			
		f = gzip.GzipFile(path, "w")
		f.write(doc.toprettyxml())
		f.close()
		
		self.StateChanged()
	
	#_____________________________________________________________________

	def closeProject(self):
		global GlobalProjectObject
		GlobalProjectObject = None
		
		if self.transport:
			self.transport.Destroy()
		self.instruments = []
		self.metadata = {}
		self.projectfile = ""
		self.projectdir = ""
		self.name = ""
		self.listeners = []
		
	#_____________________________________________________________________
	
	def Undo(self):
		self.performingUndo = True
		
		if len(self.undoStack):
			cmd = self.undoStack.pop()
			self.ExecuteCommand(cmd)
			
		elif len(self.savedUndoStack):
			self.savedUndo = True
			cmd = self.savedUndoStack.pop()
			self.ExecuteCommand(cmd)
			self.savedUndo = False
			
		self.performingUndo = False
	
	#_____________________________________________________________________
	
	def Redo(self):
		self.performingRedo = True
		
		if len(self.savedRedoStack):
			self.savedUndo = True
			cmd = self.savedRedoStack.pop()
			self.ExecuteCommand(cmd)
			self.savedUndo = False
			
		elif len(self.redoStack):
			cmd = self.redoStack.pop()
			self.ExecuteCommand(cmd)
			
		self.performingRedo = False

	#_____________________________________________________________________
	
	def AppendToCurrentStack(self, object):
		if self.savedUndo and self.performingUndo:
			self.savedRedoStack.append(object)
		elif self.savedUndo and self.performingRedo:
			self.savedUndoStack.append(object)
		elif self.performingUndo:
			self.redoStack.append(object)
		elif self.performingRedo:
			self.undoStack.append(object)
		else:
			self.undoStack.append(object)
			self.redoStack = []
			#if we have undone anything that was previously saved
			if len(self.savedRedoStack):
				self.savedRedoStack = []
				#since there is no other record that something has 
				#changed after savedRedoStack is purged
				self.unsavedChanges = True
		self.StateChanged()
	
	#_____________________________________________________________________
	
	def CheckUnsavedChanges(self):
		"""Uses boolean self.unsavedChanges and Undo/Redo to 
		   determine if the program needs to save anything on exit
		"""
		return self.unsavedChanges or \
			len(self.undoStack) > 0 or \
			len(self.savedRedoStack) > 0
	
	#_____________________________________________________________________
	
	def ExecuteCommand(self, cmd):
		""" This function executes the string cmd from the undo/redo stack.
			Commands are made up of 2 parts - the object (and it's ID if
			relevant), and the function to call.

			i.e.
				E2 Delete()
				which means 'Call Delete()' on the Event with ID=2
		"""
		global GlobalProjectObject
	
		# Split the call into the object and function
		obj = cmd.split()[0]
		func = cmd[len(obj)+1:]
		
		target_object = None
		
		if obj[0] == "P":		# Check if the object is a Project
			target_object = self
			
		elif obj[0] == "I":		# Check if the object is an Instrument
			id = int(obj[1:])
			target_object = [x for x in self.instruments if x.id==id][0]
			
		elif obj[0] == "E":		# Check if the object is an Event
			id = int(obj[1:])

			# First of all see if it's alive on an instrument
			for i in self.instruments:
				l = [x for x in i.events if x.id==id]
				if l and len(l):
					target_object = l[0]
					break

			# If not, check the graveyard
			if not target_object:
				for dead in GlobalProjectObject.graveyard:
					if dead.id == id:
						target_object = dead

		exec("target_object.%s"%func)
				

	#_____________________________________________________________________
	
	def AddInstrument(self, name, pixbuf, pixbufPath):
		''' Adds a new instrument to the project
		
			undo : DeleteInstrument(%(temp)d)
		'''
			
		instr = Instrument(self, name, pixbuf, pixbufPath)
		audio_dir = os.path.join(os.path.split(self.projectfile)[0], "audio")
		instr.path = os.path.join(audio_dir)
		
		self.temp = instr.id
		self.instruments.append(instr)	
		
	#_____________________________________________________________________	
		
	def DeleteInstrument(self, id):
		'''
			undo : ResurrectInstrument(%(temp)d)
		'''
		
		instr = [x for x in self.instruments if x.id == id][0]
		self.graveyard.append(instr)
		self.instruments.remove(instr)
		if instr.isSolo:
			self.soloInstrCount -= 1
			self.OnAllInstrumentsMute()
			
		self.temp = id
	
	#_____________________________________________________________________
	
	def ResurrectInstrument(self, id):
		'''
			undo : DeleteInstrument(%(temp)d)
		'''
		instr = [x for x in self.graveyard if x.id == id][0]
		self.instruments.append(instr)
		if instr.isSolo:
			self.soloInstrCount += 1
			self.OnAllInstrumentsMute()
		instr.isVisible = True
		self.graveyard.remove(instr)
		self.temp = id
		
	#_____________________________________________________________________
	
	def ClearEventSelections(self):
		''' Clears the selection of any events '''
		for instr in self.instruments:
			for ev in instr.events:
				ev.SetSelected(False)

	#_____________________________________________________________________

	def ClearInstrumentSelections(self):
		''' Clears the selection of any instruments '''
		for instr in self.instruments:
			instr.isSelected = False
			
	#_____________________________________________________________________
	
	def SetViewStart(self, start):
		self.viewStart = start
		self.RedrawTimeLine = True
		self.StateChanged()
		
	#_____________________________________________________________________
	
	def SetViewScale(self, scale):
		self.viewScale = scale
		self.RedrawTimeLine = True
		self.StateChanged()
		
	#_____________________________________________________________________

	def GetProjectLength(self):
		length = 0
		for instr in self.instruments:
			for ev in instr.events:
				size = ev.start + ev.duration
				length = max(length, size)
		return length

	#_____________________________________________________________________
	
	def OnAllInstrumentsMute(self):
		for instr in self.instruments:
			instr.OnMute()
			
	#_____________________________________________________________________
#=========================================================================
	
class OpenProjectError(EnvironmentError):
		def __init__(self):
			pass

#=========================================================================

GlobalProjectObject = None
