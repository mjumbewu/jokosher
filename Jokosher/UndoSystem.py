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

import Project, Globals, Utils

def UndoCommand(*command):
	"""
	Decorates functions, enabling them to be logged in the undo stack.
	The decorating process is transparent to the clients.
	
	Parameters:
		command -- the undo command list of strings.
		
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
				**kwargs -- dictionary of keyword:value parameters meant
							for the decorated function.
			
			Returns:
				the wrapped function resulting value.
			"""
			atomicUndoObject = None
			if kwargs.has_key("_undoAction_"):
				atomicUndoObject = kwargs["_undoAction_"]
				#remove the keyword from kwargs so it doesn't get passed to the function
				del kwargs["_undoAction_"]
			
			try:
				result = func(funcSelf, *args, **kwargs)
			except CancelUndoCommand, e:
				return e.result
			
			# initialize the AtomicUndoAction object *after* we call the function,
			# so that if CancelUndoCommand is raise, nothing is appended to the stack
			if not atomicUndoObject:
				#if we were not provided one, create a default atomic undo object 
				atomicUndoObject = AtomicUndoAction()
			
			if isinstance(funcSelf, Project.Project):
				objectString = "P"
			elif isinstance(funcSelf, Project.Instrument):
				objectString = "I%d" % funcSelf.id
			elif isinstance(funcSelf, Project.Event):
				objectString = "E%d" % funcSelf.id
			
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
		return UndoWrapper
		#_____________________________________________________________________
	return UndoFunction
	#_____________________________________________________________________
	
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

#=========================================================================

class AtomicUndoAction:
	"""
	This object is a container for many separate undo command,
	which will be treated as a single undo action. For example, after
	deleting many instruments at once, an AtomicUndoAction object
	will be stored containing the commands to resurrect all the
	instruments. When the user performs an undo, all of the commands
	stored by this object will be executed together. This will make many
	separate commands appear to be atomic from the user's perspective.
	"""
	
	def __init__(self, addToStack=True):
		"""
		Create a new AtomicUndoAction and optionally add it to the undo stack.
		
		Parameters:
			addToStack -- If True, this instance will be added to the currently active undo/redo stack.
		"""
		self.commandList = []
		if addToStack:
			# add ourselves to the undo stack for the current project.
			Project.GlobalProjectObject.AppendToCurrentStack(self)
	
	#_____________________________________________________________________
	
	def AddUndoCommand(self, objectString, function, paramList):
		"""
		Add a new undo command to this AtomicUndoAction.
		
		Parameters:
			objectString -- The string representing the object and its ID (ie "E2" for Event with ID == 2).
			function -- The name of the function to be called on the object.
			paramList -- A list of values to be passed to the function as parameters.
					Key, value parameters are not supported.
		"""
		newTuple = (objectString, function, paramList)
		self.commandList.append(newTuple)
		Globals.debug("LOG COMMAND: ", newTuple, "from", id(self))
	
	#_____________________________________________________________________
	
	def GetUndoCommands(self):
		"""
		Get the list of undo commands that are held by this instance.
		
		Return:
			A list of tuples, each of which contains a single undo command.
		"""
		return self.commandList
	
	#_____________________________________________________________________
	
	def StoreToXML(self, doc, parent):
		"""
		Store this instance of AtomicUndoAction to an XML node.
		
		Parameters:
			doc -- The XML document that it will be stored to.
			parent -- The parent node of our XML tags.
		"""
		for cmd in self.GetUndoCommands():
			commandXML = doc.createElement("Command")
			parent.appendChild(commandXML)
			commandXML.setAttribute("object", cmd[0])
			commandXML.setAttribute("function", cmd[1])
			Utils.StoreListToXML(doc, commandXML, cmd[2], "Parameter")
		
	#_____________________________________________________________________
#=========================================================================

def LoadUndoActionFromXML(node):
	"""
	Return an instance of AtomicUndoAction, loaded from an XML node.
	
	Parameters:
		node -- the XML "<Action>" node.
	Return:
		The new AtomicUndoAction instance loaded from the XML.
	"""
	# Don't add to stack because the project is being loaded
	undoAction = AtomicUndoAction(addToStack=False)
	for cmdNode in node.childNodes:
		if cmdNode.nodeName == "Command":
			objectString = str(cmdNode.getAttribute("object"))
			functionString = str(cmdNode.getAttribute("function"))
			paramList = Utils.LoadListFromXML(cmdNode)
			
			undoAction.AddUndoCommand(objectString, functionString, paramList)
	
	return undoAction

#=========================================================================
