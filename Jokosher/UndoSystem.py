#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	UndoSystem.py
#
#	Contains the decorator needed to allow other classes to hook specific
#	function calls into the undo stack.
#
#=========================================================================

def UndoCommand(*command, **command_options):
	"""
	Decorates functions, enabling them to be logged in the undo stack.
	The decorating process is transparent to the clients.
	
	Parameters:
		command -- the undo command list of strings.
		command_options -- key-value parameters to change options.
		
	Returns:
		an UndoFunction which decorates the original function.
	"""
	
	def UndoFunction(func):
		"""
		This is the actual decorator function. When decorated,
		this function will be called with func as the function to
		be decorated.
		
		Parameters:
			func -- the function to be decorated.
			
		Returns:
			an UndoWrapper to replace the function, so that when it
			is called, UndoWrapper will be called instead, and will:
				1)log the function call to the undo stack, and 
				2)call the function originally wanted.
		"""
		
		def UndoWrapper(funcSelf, *args, **kwargs):
			"""
			This function will wrap and take the place of the function
			that is being decorated. All arguments to the original function
			will be saved, and sent to the decorated function call.
			The funcSelf value must be the first parameter, because
			the first parameter will always be self, and it carries a
			reference to the decorated function's class.
			
			Considerations:
				All decorated undo functions *must* be in a class or this will fail.
				
			Parameters:
				funcSelf -- reference to the decorated function's class.
				*args -- parameters meant for the decorated function.
				**kwargs -- dictionary of keyword:value parameters
						containing the optional _undoAction_ parameter.
				_undoAction_ -- has to be passed as a key:value pair inside kwargs.
						The AtomicUndoAction object to append the 
						command to or None to create a default 
						AtomicUndoAction with only the one command.
			
			Returns:
				the wrapped function resulting value.
			"""
			if kwargs.has_key("_undoAction_"):
				atomicUndoObject = kwargs["_undoAction_"]
				del kwargs["_undoAction_"]
			else:
				atomicUndoObject = None
			
			do_incremental_save = True
			if command_options.has_key("incremental_save"):
				do_incremental_save = command_options["incremental_save"]
			
			if kwargs.has_key("_incrementalRestore_"):
				do_incremental_save = False
				del kwargs["_incrementalRestore_"]
				
			
			try:
				result = func(funcSelf, *args, **kwargs)
			except CancelUndoCommand, e:
				return e.result
			
			project = None
			if isinstance(funcSelf, Project.Project):
				project = funcSelf
				objectString = "P"
			elif isinstance(funcSelf, Instrument.Instrument):
				project = funcSelf.project
				objectString = "I%d" % funcSelf.id
			elif isinstance(funcSelf, Event.Event):
				project = funcSelf.instrument.project
				objectString = "E%d" % funcSelf.id
			
			if do_incremental_save:
				inc = IncrementalSaveAction(objectString, func.__name__, args, kwargs, result)
				project.SaveIncrementalAction(inc)
				# testing: make sure loading produces an identical result
				assert inc.StoreToString() == IncrementalSaveAction.LoadFromString(inc.StoreToString()).StoreToString()
			
			if not atomicUndoObject and project:
				atomicUndoObject = project.NewAtomicUndoAction()
				
			if atomicUndoObject:
				paramList = []
				for param in command[1:]:
					try:
						value = getattr(funcSelf, param)
					except:
						continue
					else:
						paramList.append(value)
				
				atomicUndoObject.AddUndoCommand(objectString, command[0], paramList)
			
			return result
		
			#_____________________________________________________________________
		
		UndoWrapper.wrapped_func = func
		return UndoWrapper
	
		#_____________________________________________________________________
		
	return UndoFunction

	#_____________________________________________________________________

#=========================================================================
"""
These import statements *must* be placed below the UndoCommand function because
decorators are called at import-time to decorate other functions. Project, Instrument
and Event classes all use the UndoCommand decorator. Therefore importing any of those
modules before UndoCommand is defined will cause a cyclic dependency in which
Event depends on UndoSystem and UndoSystem depends on Event. A cyclic import
dependency will stop the program before it even starts.
"""
import ProjectManager, Globals, Utils
import Project, Event, Instrument
import xml.dom.minidom as xml

#=========================================================================

class CancelUndoCommand(Exception):
	"""
	This exception can be thrown by a decorated undo
	function in order to tell the undo system to not
	log the current action. This is useful if something
	in the function fails and the action that would have
	been logged to the undo stack was never actually completed.
	"""
	def __init__(self, result=None):
		"""
		Creates a new instance of CancelUndoCommand.
		
		Parameters:
			result -- value the wrapped function intended to return,
						but failed and called this exception.
		"""
		Exception.__init__(self)
		self.result = result
	
	#_____________________________________________________________________

#=========================================================================

class AtomicUndoAction:
	"""
	Contains several undo commands to be treated as a single undoable operation.
	
	Example:
		When deleting several Instruments at once, an AtomicUndoAction
		containing the commands to resurrect the Instruments will be created.
		When the user requests an undo operation, all of the commands stored
		in this object will be rolled back, making the operation appear to be
		atomic from the user's perspective.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		"""
		Creates a new AtomicUndoAction instance.
		"""
		self.commandList = []
	
	#_____________________________________________________________________
	
	def AddUndoCommand(self, objectString, function, paramList):
		"""
		Adds a new undo command to this AtomicUndoAction.
		
		Example:
			The parameters passed to this function:
				"E2", "Move", [1, 2]
			means
				'Call Move(1, 2)' on the Event with ID=2
		
		Parameters:
			objectString -- the string representing the object and its ID
							(ie "E2" for Event with ID == 2).
			function -- the name of the function to be called on the object.
			paramList -- a list of values to be passed to the function as parameters.
						Key, value parameters are not supported.
		"""
		newTuple = (objectString, function, paramList)
		self.commandList.append(newTuple)
		Globals.debug("LOG COMMAND: ", newTuple, "from", id(self))
	
	#_____________________________________________________________________
	
	def GetUndoCommands(self):
		"""
		Obtains the list of undo commands held by this AtomicUndoAction.
		
		Returns:
			a list of tuples, each of which contains a single undo command.
		"""
		return self.commandList
	
	#_____________________________________________________________________
	
	def StoreToXML(self, doc, node):
		"""
		Stores this instance of AtomicUndoAction into an XML node.
		
		Example:
				doc = xml.Document()
				node = doc.createElement("Action")
				doc.appendChild(node)
				StoreToXml(doc, node)
				
			will save this AtomicUndoAction in doc, inside node.
		
		Parameters:
			doc -- XML document to save this AtomicUndoAction into.
			node -- XML node to store this AtomicUndoAction under.
					This node's name should be "Action".
		"""
		for cmd in self.GetUndoCommands():
			commandXML = doc.createElement("Command")
			node.appendChild(commandXML)
			commandXML.setAttribute("object", cmd[0])
			commandXML.setAttribute("function", cmd[1])
			Utils.StoreListToXML(doc, commandXML, cmd[2], "Parameter")
		
	#_____________________________________________________________________
	
#=========================================================================

class IncrementalNewEvent:
	def __init__(self, instr_id, filename, event_start, event_id):
		self.instr_id = instr_id
		self.filename = filename
		self.event_start = event_start
		self.event_id = event_id
		
	def StoreToString(self):
		doc = xml.Document()
		node = doc.createElement("NewEvent")
		doc.appendChild(node)
		
		node.setAttribute("instrument_id", str(self.instr_id))
		node.setAttribute("file", self.filename)
		node.setAttribute("start", str(self.event_start))
		node.setAttribute("event_id", str(self.event_id))
				
		return doc.toxml()
	
	@staticmethod
	def LoadFromString(string):
		doc = xml.parseString(string)
		node = doc.firstChild
		assert node.nodeName == "NewEvent"
		
		instr_id = int(node.getAttribute("instrument_id"))
		filename = node.getAttribute("file")
		event_start = float(node.getAttribute("start"))
		event_id = int(node.getAttribute("event_id"))
		
		return IncrementalNewEvent(instr_id, filename, event_start, event_id)

#=========================================================================

class IncrementalSaveAction:
	def __init__(self, objectString, func_name, args, kwargs, retval_event=None):
		self.objectString = objectString
		self.func_name = func_name
		self.args = args
		self.kwargs = kwargs
		
		# retval is either None or a MockEvent. We don't care about
		# the return value of functions which don't create Events.
		self.retval = None
		if isinstance(retval_event, Event.Event):
			self.retval = MockEvent("E" + str(retval_event.id))
		elif isinstance(retval_event, MockEvent):
			self.retval = retval_event

	def StoreToString(self):
		doc = xml.Document()
		action = doc.createElement("Action")
		doc.appendChild(action)
		
		action.setAttribute("object", self.objectString)
		action.setAttribute("function", self.func_name)
		if self.retval:
			action.setAttribute("retval", self.retval.event_string)
		
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
		retval_string = actionNode.getAttribute("retval")
		if retval_string.startswith("E"):
			retval = MockEvent(retval_string)
		else:
			retval = None
			
		
		argsList = []
		kwArgsDict = {}
		
		for argNode in actionNode.childNodes:
			value = IncrementalSaveAction.ReadFromXMLAttributes(argNode)
			if argNode.nodeName == "Argument":
				argsList.append(value)
			elif argNode.nodeName == "NamedArgument":
				key = str(argNode.getAttribute("key"))
				kwArgsDict[key] = value

		return IncrementalSaveAction(object_string, function_name, 
		                             argsList, kwArgsDict, retval_event=retval)
		

#=========================================================================

def LoadFromString(string):
	doc = xml.parseString(string)
	node = doc.firstChild
	if node == "Action":
		return IncrementalSaveAction.LoadFromString(string)
	elif node == "NewEvent":
		return IncrementalNewEvent.LoadFromString(string)
	
	return None
	
#=========================================================================

class MockEvent:
	def __init__(self, string):
		self.id = int(string[1:])
		self.event_string = string


#=========================================================================
