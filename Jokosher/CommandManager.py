#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	CommandManager.py
#
#	Intercepts function calls to Jokosher objects that required undo,
#	and adds a record of the performed action to the undo stack.
#
#-------------------------------------------------------------------------------

import types
import Project, Globals

#=========================================================================

class CommandManaged(object):
	"""
	   Each object which does undoable things should inherit from CommandManaged.
	   This overrides __getattribute__, which is called any time anyone wants
	   to access any method or property of that class. Our override __getattribute__
	   looks to see if the thing that's being accessed is a function (callable()),
	   if it has a docstring (__doc__), and if that docstring has "undo" in it.
	   If all of those things apply, then it's an undoable function, and so should
	   be added to the undo stack. If it's not, we just return the actual thing,
	   so it works invisibly.
	   If it *is* part of the undo stack, then what we return is a function that
	   (a) manages the undo stack and then (b) calls the actual function they wanted.
	   (This is what the CommandManagerFunctionCurry stuff is about.) They get back,
	   instead of the function they wanted, a wrapperFunction() which is particular
	   to the function they wanted. (But they don't know this has happened.) When
	   they call the function, it grabs the undo data out of the docstring, adds
	   that undo data to the undo stack, and then calls the function they wanted;
	   again, it's all invisible, so we get undo functionality for free and no-one
	   ever has to worry about it.
	   
	   Undo functions are defined in the docstring with parameters; these parameters
	   are attributes of the object they're called on, as formatstring items. So,
	   looking at Event.Move():
	   
	def Move(self, frm, to):
		'''	Moves this Event.

			frm
				The time we're moving from.
			to
				The time we're moving to.

			undo : Move(%(start)f, %(temp)f)
		'''
		self.temp = frm
		self.start = to
		self.SetProperties()	   
		
		The undo method for a Move is defined as Move(%(start)f, %(temp)f), and
		the start and temp variables are defined in the function itself. These
		variables are then substituted in before the command is put on the undo stack.
	   
	   
	"""
	
	#_____________________________________________________________________
	
	def __getattribute__(self,attr):
		if attr == "__class__":
			return type(self)
		
		actual = super(CommandManaged,self).__getattribute__(attr)
		
		if not callable(actual) or (not actual.__doc__) or (not "undo : " in actual.__doc__):
			return actual
		else:
			return CommandManagerFunctionCurry(self.wrapperFunction,actual)

	#_____________________________________________________________________
	
	def wrapperFunction(self,func,*args,**kwargs):
		out = func(*args,**kwargs)
		d = func.__doc__
		
		undo = d[d.find("undo : ") + 7:].split("\n")[0]
		cmd = undo % makeDict(func.im_self)
		
		obj = ""
		if type(self) == Project.Project:
			obj = "P"
		elif type(self) == Project.Instrument:
			obj = "I%d"%self.id
		elif type(self) == Project.Event:
			obj = "E%d"%self.id
		Globals.debug("LOG COMMAND: ",obj, cmd)
		Project.GlobalProjectObject.AppendToCurrentStack("%s %s" % (obj, cmd))
		
		return out

	#_____________________________________________________________________

#=========================================================================

class makeDict(dict):
	
	#_____________________________________________________________________
	
	def __init__(self,obj):
		self.obj = obj
		
	#_____________________________________________________________________
		
	def __getitem__(self,item):
		return getattr(self.obj,item)
	
	#_____________________________________________________________________

#=========================================================================
	
class CommandManagerFunctionCurry:
	
	#_____________________________________________________________________
	
	def __init__(self, fun, *args, **kwargs):
		self.fun = fun
		self.pending = args[:]
		self.kwargs = kwargs.copy()

	#_____________________________________________________________________

	def __call__(self, *args, **kwargs):
		if kwargs and self.kwargs:
			kw = self.kwargs.copy()
			kw.update(kwargs)
		else:
			kw = kwargs or self.kwargs

		return self.fun(*(self.pending + args), **kw)
	
	#_____________________________________________________________________

#=========================================================================
