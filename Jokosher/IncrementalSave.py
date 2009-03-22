
import Event
import Utils
import os.path
import xml.dom.minidom as xml

import gettext
_ = gettext.gettext

#=========================================================================

class NewEvent:
	def __init__(self, instr_id, filename, event_start, event_id, recording=False):
		self.instr_id = instr_id
		self.filename = filename
		self.event_start = event_start
		self.id = event_id
		self.recording = recording
		
	def Execute(self, project, event_duration=None, event_levels_file=None):
		instr = project.JokosherObjectFromString("I" + str(self.instr_id))
		
		filename = self.filename
		if not os.path.isabs(filename):
			# If there is a relative path for filename, this means it is in the project's audio dir
			filename = os.path.join(project.audio_path, filename)
		
		if self.recording:
			event_name = _("Recorded audio")
		else:
			event_name = None
			
		instr.addEventFromFile(self.event_start, filename, copyfile=False,
		              name=event_name, duration=event_duration, levels_file=event_levels_file)
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("NewEvent")
		doc.appendChild(node)
		
		node.setAttribute("instrument_id", str(self.instr_id))
		node.setAttribute("file", self.filename)
		node.setAttribute("start", str(self.event_start))
		node.setAttribute("event_id", str(self.id))
		node.setAttribute("recording", str(self.recording))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "NewEvent"
		
		instr_id = int(node.getAttribute("instrument_id"))
		filename = node.getAttribute("file")
		event_start = float(node.getAttribute("start"))
		id = int(node.getAttribute("event_id"))
		recording = (node.getAttribute("recording").lower() == "true")
		
		return NewEvent(instr_id, filename, event_start, id, recording)

#=========================================================================

class StartDownload:
	def __init__(self, instr_id, url, save_file, event_start, event_id):
		self.instr_id = instr_id
		self.url = url
		self.save_file = save_file
		self.event_start = event_start
		self.id = event_id
		
	def Execute(self, project):
		instr = project.JokosherObjectFromString("I" + str(self.instr_id))
		instr.addEventFromURL(self.event_start, self.url)
		
	def GetNewEventAction(self):
		return NewEvent(self.instr_id, self.save_file, self.event_start, self.id)
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("StartDownload")
		doc.appendChild(node)
		
		node.setAttribute("instrument_id", str(self.instr_id))
		node.setAttribute("url", self.url)
		node.setAttribute("save_file", self.save_file)
		node.setAttribute("start", str(self.event_start))
		node.setAttribute("event_id", str(self.id))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "StartDownload"
		
		instr_id = int(node.getAttribute("instrument_id"))
		url = node.getAttribute("url")
		save_file = node.getAttribute("save_file")
		event_start = float(node.getAttribute("start"))
		id = int(node.getAttribute("event_id"))
		
		return StartDownload(instr_id, url, save_file, event_start, id)

#=========================================================================

class CompleteLoading:
	def __init__(self, event_id, duration, levels_file):
		self.id = event_id
		self.duration = duration
		self.levels_file = levels_file
		
	def Execute(self, project):
		pass
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("CompleteLoading")
		doc.appendChild(node)
		node.setAttribute("event_id", str(self.id))
		node.setAttribute("duration", str(self.duration))
		node.setAttribute("levels_file", self.levels_file)
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "CompleteLoading"
		
		id = int(node.getAttribute("event_id"))
		duration = float(node.getAttribute("duration"))
		levels_file = node.getAttribute("levels_file")
		
		return CompleteLoading(id, duration, levels_file)

#=========================================================================

class Action:
	def __init__(self, objectString, func_name, args, kwargs):
		self.objectString = objectString
		self.func_name = func_name
		self.args = args
		self.kwargs = kwargs
			
	def Execute(self, project):
		target_object = project.JokosherObjectFromString(self.objectString)
		args = []
		kwargs = {}
		
		for obj in self.args:
			if isinstance(obj, MockEvent):
				obj = project.JokosherObjectFromString(obj.event_string)
			args.append(obj)
			
		for key, value in self.kwargs.iteritems():
			if isinstance(value, MockEvent):
				value = project.JokosherObjectFromString(value.event_string)
			kwargs[key] = value
		
		getattr(target_object, self.func_name)(*args, **kwargs)

		
	def StoreToString(self):
		doc = xml.Document()
		action = doc.createElement("Action")
		doc.appendChild(action)
		
		action.setAttribute("object", self.objectString)
		action.setAttribute("function", self.func_name)
		
		for arg in self.args:
			node = doc.createElement("Argument")
			action.appendChild(node)
			self.WriteToXMLAttributes(None, arg, node)
				
		for key, value in self.kwargs.iteritems():
			node = doc.createElement("NamedArgument")
			action.appendChild(node)
			self.WriteToXMLAttributes(key, value, node)
				
		return doc.toxml()
	
	def WriteToXMLAttributes(self, key, value, node):
		if key:
			node.setAttribute("key", key)
		
		if isinstance(value, Event.Event) or isinstance(value, MockEvent):
			node.setAttribute("type", "Event")
			node.setAttribute("value", str(value.id))
		else:
			Utils.StoreVariableToNode(value, node, "type", "value")
	
	@staticmethod
	def ReadFromXMLAttributes(node):
		type = node.getAttribute("type")
		if type == "Event":
			event_id = node.getAttribute("value")
			value = MockEvent("E" + event_id)
			assert value is not None
		else:
			value = Utils.LoadVariableFromNode(node, "type", "value")
			
		return value
				
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		actionNode = doc.firstChild
		assert actionNode.nodeName == "Action"
		
		function_name = actionNode.getAttribute("function")
		object_string = actionNode.getAttribute("object")
		
		argsList = []
		kwArgsDict = {}
		
		for argNode in actionNode.childNodes:
			value = Action.ReadFromXMLAttributes(argNode)
			if argNode.nodeName == "Argument":
				argsList.append(value)
			elif argNode.nodeName == "NamedArgument":
				key = str(argNode.getAttribute("key"))
				kwArgsDict[key] = value

		return Action(object_string, function_name, argsList, kwArgsDict)

#=========================================================================

class SetNotes:
	def __init__(self, notes):
		self.notes = notes
		
	def Execute(self, project):
		project.SetNotes(self.notes)
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("SetNotes")
		doc.appendChild(node)
		
		node.setAttribute("notes", repr(self.notes))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "SetNotes"
		
		notes = Utils.StringUnRepr(node.getAttribute("notes"))
		
		return SetNotes(notes)

#=========================================================================
# Helper functions for Project related Actions

def Undo():
	return Action("P", "Undo", tuple(), dict())

def Redo():
	return Action("P", "Redo", tuple(), dict())

def SetName(name):
	return Action("P", "SetName", (name,), dict())

def SetAuthor(author):
	return Action("P", "SetAuthor", (author,), dict())

def InstrumentSetInput(id, device, inTrack):
	return Action("I" + str(id), "SetInput", (device, inTrack), dict())

def InstrumentSetVolume(id, volume):
	return Action("I" + str(id), "SetVolume", (volume,), dict())

#=========================================================================

def LoadFromString(string):
	doc = xml.parseString(string)
	node = doc.firstChild.nodeName
	
	action_dict = {
		"Action" : Action,
		"NewEvent" : NewEvent,
		"StartDownload" : StartDownload,
		"CompleteLoading" : CompleteLoading,
		"SetNotes" : SetNotes,
	}
	
	if node in action_dict:
		return action_dict[node].LoadFromString(string)
	
	raise AssertionError("Unknown IncrementalSave node " + node)
	
#=========================================================================

def FilterAndExecuteAll(save_action_list, project):
	complete_load_ids = {}
	for action in save_action_list:
		if isinstance(action, CompleteLoading):
			complete_load_ids[action.id] = action
	
	for action in save_action_list:
		loading_type = isinstance(action, StartDownload) or isinstance(action, NewEvent)
		if loading_type and action.id in complete_load_ids:
			# convert to a NewEvent command, skip redownload
			if isinstance(action, StartDownload):
				action = action.GetNewEventAction()
			# loading has completed. Instead of re-downloading or reloading levels
			# just restore from the data on disk
			complete_load = complete_load_ids[action.id]
			action.Execute(project, complete_load.duration, complete_load.levels_file)
		else:
			action.Execute(project)
			
#=========================================================================

class MockEvent:
	def __init__(self, string):
		self.id = int(string[1:])
		self.event_string = string


#=========================================================================
