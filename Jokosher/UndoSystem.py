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

import Project, Globals

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
			try:
				result = func(funcSelf, *args, **kwargs)
			except CancelUndoCommand, e:
				return e.result
			
			cmdList = []
			
			if isinstance(funcSelf, Project.Project):
				cmdList.append("P")
			elif isinstance(funcSelf, Project.Instrument):
				cmdList.append("I%d" % funcSelf.id)
			elif isinstance(funcSelf, Project.Event):
				cmdList.append("E%d" % funcSelf.id)
			
			cmdList.append(command[0])
			
			for cmd in command[1:]:
				try:
					value = getattr(funcSelf, cmd)
				except:
					continue
				else:
					cmdList.append(value)
				
			Globals.debug("LOG COMMAND: ", cmdList)
			Project.GlobalProjectObject.AppendToCurrentStack(cmdList)
			
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
	def __init__(self, result):
		"""
		Creates a new instance of CancelUndoCommand.
		
		Parameters:
			result -- value the wrapped function intended to return,
						but failed and called this exception.
		"""
		Exception.__init__(self)
		self.result = result

#=========================================================================
