
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

#_____________________________________________________________________

def CreateNew(folder,name,author):
	if name=="":
		name="NewProject"

	if author=="":
		author="Unknown"

	if folder=="":
		folder="~"

	filename = (name + ".jokosher")
	projectdir = os.path.join(folder, name)

	try:
		project = Project()
	except Exception, e:
		print "Could not make project object:", e
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

	project.startTransportThread()
	project.saveProjectFile(project.projectfile)

	return project

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
	
	LoadParametersFromXML(p, params)
	
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
		self.___id_list = []
		self.instruments = []
		
		self.author = "<none>"
		self.name = "<no project loaded>"
		
		# the name of the project file, complete with path
		self.projectfile = ""
		
		self.mainpipeline = None
		
		#mode for transport manager that hasn't been initialized yet
		self.transportMode = TransportManager.TransportManager.MODE_BARS_BEATS
		
		# View scale as pixels per second
		self.viewScale = 25.
		
		# View offset in seconds
		self.viewStart= 0.
		
		#number of solo instruments (to know if others must be muted)
		self.soloInstrCount = 0
		
		# The place where deleted instruments go
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
		self.IsExporting = False
		
		self.RedrawTimeLine = False

		self.mainpipeline = gst.Pipeline("timeline")
		print "created pipeline (project)"
		
		self.playbackbin = gst.Bin("playbackbin")
		
		self.adder = gst.element_factory_make("adder")
		self.playbackbin.add(self.adder)
		print "added adder (project)"

		self.level = gst.element_factory_make("level", "MasterLevel")
		self.level.set_property("interval", gst.SECOND / 50)
		self.level.set_property("message", True)
		self.playbackbin.add(self.level)
		print "added master level (project)"

		#Restrict adder's output caps due to adder bug
		self.levelcaps = gst.element_factory_make("capsfilter", "levelcaps")
		caps = gst.caps_from_string("audio/x-raw-int,rate=44100,channels=2,width=16,depth=16,signed=(boolean)true")
		self.levelcaps.set_property("caps", caps)
		self.playbackbin.add(self.levelcaps)
		
		self.adder.link(self.levelcaps)
		self.levelcaps.link(self.level)
		
		self.out = gst.element_factory_make("alsasink")
		
		try:
			outdevice = Globals.settings.playback["devicecardnum"]
		except:
			outdevice =  "default"
		if outdevice == "value":
			outdevice = "default"
		self.out.set_property("device", outdevice)

		self.playbackbin.add(self.out)
		print "added alsasink (project)"

		self.level.link(self.out)
		self.bus = self.mainpipeline.get_bus()
		self.bus.add_signal_watch()
		self.Mhandler = self.bus.connect("message", self.bus_message)
		self.EOShandler = self.bus.connect("message::eos", self.stop)
		
		self.mainpipeline.add(self.playbackbin)

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
		
		self.mainpipeline.set_state(gst.STATE_PAUSED)				
		self.state_id = self.bus.connect("message::state-changed", self.state_changed)

		# [DEBUG]
		# This debug block will be removed when we release. If you see this in a release version, we
		# obviously suck. Please email us and tell us about how shit we are.
		try:
			if os.environ['JOKOSHER_DEBUG']:
				print "Play Pipeline:"
				self.debug.ShowPipelineTree(self.mainpipeline)
		except:
			pass
		# [/DEBUG]
				
	#_____________________________________________________________________

	def state_changed(self, bus, message):
		old, new, pending = self.mainpipeline.get_state(0)
		#Move forward to playing when we reach paused (check pending to make sure this is the final destination)
		if new == gst.STATE_PAUSED and pending == gst.STATE_VOID_PENDING and self.IsPlaying == False:
			bus.disconnect(self.state_id)
			self.mainpipeline.set_state(gst.STATE_PLAYING)
			self.IsPlaying = True
			

	#_____________________________________________________________________
				
	def play(self):
		'''Set all instruments playing'''
		
		if len(self.instruments) > 0:
			gst.debug("Play pressed, about to set state to PLAYING")
			
			# And set it going
			self.mainpipeline.set_state(gst.STATE_PLAYING)
			self.IsPlaying = True

			gst.debug("just set state to PLAYING")

			# [DEBUG]
			# This debug block will be removed when we release. If you see this in a release version, we
			# obviously suck. Please email us and tell us about how shit we are.
			try:
				if os.environ['JOKOSHER_DEBUG']:
					print "Play Pipeline:"
					self.debug.ShowPipelineTree(self.mainpipeline)
			except:
				pass
			# [/DEBUG]

	#_____________________________________________________________________

	def bus_message(self, bus, message):
		st = message.structure
		if st and st.get_name() == "level":
			if message.src is self.level:
				position = float(st["endtime"]) / gst.SECOND
				self.transport.SetPosition(position)
			else:
				for instr in self.instruments:
					if message.src is instr.levelElement:
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
		#NULL is required because some elements will be destroyed when we remove the references
		self.mainpipeline.set_state(gst.STATE_NULL)
		#Create pipeline for exporting to file
		
		if filename[-3:] == "ogg":
			print "Export ogg:", filename
			#create filesink, and vorbis encoder
			self.outfile = gst.element_factory_make("filesink", "export_file")
			self.outfile.set_property("location", filename)
			self.encode = gst.element_factory_make("vorbisenc")
##			self.encode.set_property("quality", 1)
			self.mux = gst.element_factory_make("oggmux")
			
			#audioconvert is required because level and vorbisenc have different caps
			self.exportconvert = gst.element_factory_make("audioconvert", "export_convert")
		
			self.playbackbin.add(self.exportconvert, self.encode, self.mux, self.outfile)
			
			#remove and unlink the alsasink
			self.playbackbin.remove(self.out, self.level)
			self.levelcaps.unlink(self.level)
			
			caps = gst.caps_from_string ("audio/x-raw-float,rate=44100,channels=2,endianness=1234,width=32")
			
			self.levelcaps.link(self.exportconvert)
			self.exportconvert.link(self.encode)
			self.encode.link(self.mux)
			self.mux.link(self.outfile)
			
			#disconnect the bus_message() which will make the transport manager progress move
			self.bus.disconnect(self.Mhandler)
			self.bus.disconnect(self.EOShandler)
			self.EOShandler = self.bus.connect("message::eos", self.export_eos)
	
		else:
			print "Unknown filetype for export"
			return
		
		self.IsExporting = True
		#start the pipeline!
		self.play()

	#_____________________________________________________________________
	
	def export_eos(self, bus=None, message=None):
		#connected to eos on mainpipeline while export is taking place
		self.stop()
		self.IsExporting = False
		#NULL is required because some elements will be destroyed when we remove them
		self.mainpipeline.set_state(gst.STATE_NULL)
	
		self.bus.disconnect(self.EOShandler)
		self.Mhandler = self.bus.connect("message::element", self.bus_message)
		self.EOShandler = self.bus.connect("message::eos", self.stop)
		
		#remove all the export elements
		self.playbackbin.remove(self.exportconvert, self.encode, self.mux, self.outfile)
		
		#re-add all the alsa playback elements
		self.playbackbin.add(self.out, self.level)
		self.levelcaps.unlink(self.exportconvert)
		self.levelcaps.link(self.level)
		
		self.exportconvert.unlink(self.encode)
		self.encode.unlink(self.mux)
		self.mux.unlink(self.outfile)
	
	#_____________________________________________________________________
	
	def get_export_progress(self):
		#Returns tuple with number of seconds done, and number of total seconds
		if self.IsExporting:
			try:
				total = float(self.mainpipeline.query_duration(gst.FORMAT_TIME)[0])
				cur = float(self.mainpipeline.query_position(gst.FORMAT_TIME)[0])
				return (cur/gst.SECOND, total/gst.SECOND)
			except gst.QueryError:
				return (-1., -1.)
		else:
			return (100., 100.)
		
	#_____________________________________________________________________
	
	def stop(self, bus=None, message=None):
		'''Stop playing or recording'''
		for instr in self.instruments:
			instr.stop()

		if self.mainpipeline:
			#self.bin.remove(instr.converterElement)
			#print "removed instrument audioconvert (project)"
			
			#self.bin.remove(instr.volumeElement)
			#print "removed instrument volume (project)"

			#self.bin.remove(instr.levelElement)
			#print "removed instrument level (project)"

			gst.debug("Stop pressed, about to set state to READY")

			self.mainpipeline.set_state(gst.STATE_READY)
			self.IsPlaying = False
			
			gst.debug("Stop pressed, state just set to READY")

			print "PIPELINE AFTER STOP:"
			# [DEBUG]
			# This debug block will be removed when we release. If you see this in a release version, we
			# obviously suck. Please email us and tell us about how shit we are.
			try:
				if os.environ['JOKOSHER_DEBUG']:
					print "Play Pipeline:"
					self.debug.ShowPipelineTree(self.mainpipeline)
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
		
		StoreParametersToXML(self, doc, params, items)
			
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
			
		for i in self.graveyard:
			i.StoreToXML(doc, head, graveyard=True)
			
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
	
	def PurgeUndoHistory(self):
		"""Clears the undo/redo stacks as well as deletes
		   any objects in the graveyard
		"""
		self.performingUndo = False
		self.performingRedo = False
		self.savedUndo = False
		
		self.undoStack = []
		self.redoStack = []
		self.savedUndoStack = []
		self.savedRedoStack = []
		
		self.graveyard = []
		for instr in self.instruments:
			instr.graveyard = []
		
		#Now that everything is cleared, we should prompt to save
		self.unsavedChanges = True
		#Notify GUI to update undo/redo button
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

			for i in self.instruments:
				# First of all see if it's alive on an instrument
				n = [x for x in i.events if x.id==id]
				if not n:
					# If not, check the graveyard on each instrument
					n = [x for x in i.graveyard if x.id==id]
				if n:
					target_object = n[0]
					break

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
		
		instr.RemoveAndUnlinkPlaybackbin()
		
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
		
		instr.AddAndLinkPlaybackbin()
		
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
	
	def GenerateUniqueID(self, id = None):
		if id != None:
			if id in self.___id_list:
				print "Error: id", id, "already taken"
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
#=========================================================================
	
class OpenProjectError(EnvironmentError):
	def __init__(self):
		pass

#=========================================================================

class CreateProjectError(Exception):
	def __init__(self, errno):
		"""Error numbers:
		   1) Unable to create a project object
		   2) Path for project file already exists
		   3) Unable to create file. (Invalid permissions, read-only, or the disk is full)
		"""
		self.errno=errno

#=========================================================================

GlobalProjectObject = None
