
import Event
import Utils
import os.path
import xml.dom.minidom as xml

#=========================================================================

class NewEvent:
	def __init__(self, instr_id, filename, event_start):
		self.instr_id = instr_id
		self.filename = filename
		self.event_start = event_start
		
	def Execute(self, project):
		instr = project.JokosherObjectFromString("I" + str(self.instr_id))
		
		filename = self.filename
		if not os.path.isabs(filename):
			# If there is a relative path for filename, this means it is in the project's audio dir
			filename = os.path.join(project.audio_path, filename)
			
		instr.addEventFromFile(self.event_start, filename, copyfile=False)
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("NewEvent")
		doc.appendChild(node)
		
		node.setAttribute("instrument_id", str(self.instr_id))
		node.setAttribute("file", self.filename)
		node.setAttribute("start", str(self.event_start))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "NewEvent"
		
		instr_id = int(node.getAttribute("instrument_id"))
		filename = node.getAttribute("file")
		event_start = float(node.getAttribute("start"))
		
		return NewEvent(instr_id, filename, event_start)

#=========================================================================

class StartDownload:
	def __init__(self, instr_id, url, save_file, event_start, id):
		self.instr_id = instr_id
		self.url = url
		self.save_file = save_file
		self.event_start = event_start
		self.id = id
		
	def Execute(self, project):
		instr = project.JokosherObjectFromString("I" + str(self.instr_id))
		instr.addEventFromURL(self.event_start, self.url)
		
	def GetNewEventAction(self):
		return NewEvent(self.instr_id, self.save_file, self.event_start)
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("StartDownload")
		doc.appendChild(node)
		
		node.setAttribute("instrument_id", str(self.instr_id))
		node.setAttribute("url", self.url)
		node.setAttribute("save_file", self.save_file)
		node.setAttribute("start", str(self.event_start))
		node.setAttribute("action_id", str(self.id))
				
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
		id = int(node.getAttribute("action_id"))
		
		return StartDownload(instr_id, url, save_file, event_start, id)

#=========================================================================

class CompleteDownload:
	def __init__(self, id):
		self.id = id
		
	def Execute(self, project):
		pass
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("CompleteDownload")
		doc.appendChild(node)
		node.setAttribute("action_id", str(self.id))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "CompleteDownload"
		
		id = int(node.getAttribute("action_id"))
		
		return CompleteDownload(id)

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
		
		# tell the incremental system not to log these actions; they are already in the incremental file
		kwargs["_incrementalRestore_"] = True
		
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
				
		for key, value in self.kwargs:
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

def LoadFromString(string):
	doc = xml.parseString(string)
	node = doc.firstChild.nodeName
	if node == "Action":
		return Action.LoadFromString(string)
	elif node == "NewEvent":
		return NewEvent.LoadFromString(string)
	elif node == "StartDownload":
		return StartDownload.LoadFromString(string)
	elif node == "CompleteDownload":
		return CompleteDownload.LoadFromString(string)
	
	raise AssertionError("Unknown IncrementalSave node " + node)
	
#=========================================================================

def FilterAndExecuteAll(save_action_list, project):
	complete_download_ids = [x.id for x in save_action_list if isinstance(x, CompleteDownload)]
	
	for action in save_action_list:
		if isinstance(action, StartDownload) \
				and action.id in complete_download_ids:
			# download has completed. Instead of re-downloading just restore
			# as a standard new event action
			action = action.GetNewEventAction()
			
		action.Execute(project)
			
#=========================================================================

class MockEvent:
	def __init__(self, string):
		self.id = int(string[1:])
		self.event_string = string


#=========================================================================
