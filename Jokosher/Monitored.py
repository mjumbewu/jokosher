#
#       THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#       THE 'COPYING' FILE FOR DETAILS
#
#       Monitored.py
#       
#       Offers an abstract class for reporting changes to other objects
#
#-------------------------------------------------------------------------------


#=========================================================================

class Monitored:
	""" This class defines a set of functions to allow derived classes to
		have attached monitor objects, which should be signaled if the 
		monitored objects state changes.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		self.listeners = []
		
	#_____________________________________________________________________
		
	def AddListener(self, obj):
		"""Adds an object to report changes too.
		
		Keyword arguments:
		obj -- An object to inform when StateChanged is called."""

		if not obj in self.listeners:
			self.listeners.append(obj)
			
	#_____________________________________________________________________
			
	def RemoveListener(self, obj):
		"""Stop reporting changes to the specified object.
		
		Keyword arguments:
		obj -- The object which should no longer receive change updates."""

		if obj in self.listeners:
			self.listeners.remove(obj)
			
	#_____________________________________________________________________
	
	def ClearListeners(self):
		"""Remove all listeners to allow them to be destroyed."""
		self.listeners = []
	
	#_____________________________________________________________________
	
	def StateChanged(self, change=None, *extra):
		"""This function should be called when we want a change to be reported to all objects previously added by AddListener. 
		
		Keyword arguments:
		change -- The change which has occured (optional).
		extra -- Any extra parameters that should be passed (optional).
		"""
		
		for obj in self.listeners:
			obj.OnStateChanged(self, change, *extra)
			
	#_____________________________________________________________________
	
#=========================================================================
