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
	   Method to take in the undo command, and return a decorator 
	   for functions that need to be logged in the undo stack.
	   
	   command - the undo command list of strings
	"""
	def UndoFunction(func):
		"""
		   This is the actual decorator function. When decorated,
		   this function will be called with func as the function to
		   be decorated. We will return UndoWrapper to replace the
		   function so that when the function is called, UndoWrapper
		   will be called instead and will 1)log function call to the undo
		  stack and 2) call the function they originally wanted.
		  
		   func - the funciton that we are decorating
		"""
		def UndoWrapper(funcSelf, *args, **kwargs):
			"""
			   This function will wrap and take the place of the function
			   that is being decorated. We must take in all arguments
			   and replay them when we call the decorated function.
			   We must have funcSelf as the first parameter because
			   the first parameter will always be self, and we need a reference
			   to the function's class.
			   NOTE: all decorated undo functions *must* be in a class or this will fail.
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
			
			for i in command[1:]:
				try:
					value = getattr(funcSelf, i)
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
		Exception.__init__(self)
		self.result = result

#=========================================================================
