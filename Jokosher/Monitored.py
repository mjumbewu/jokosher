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
	"""
	This class defines a set of functions to allow derived classes to
	have attached monitor objects, which should be signaled if the 
	monitored objects state changes.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self):
		"""
		Creates a new instance of Monitored.
		"""
		self.listeners = []
		
	#_____________________________________________________________________
		
	def AddListener(self, obj):
		"""
		Adds an object to report changes to.
		
		Parameters:
			obj -- an object to inform when StateChanged is called.
		"""

		if not obj in self.listeners:
			self.listeners.append(obj)
			
	#_____________________________________________________________________
			
	def RemoveListener(self, obj):
		"""
		Stop reporting changes to the specified object.
		
		Parameters:
			obj -- the object which should no longer receive change updates.
		"""

		if obj in self.listeners:
			self.listeners.remove(obj)
			
	#_____________________________________________________________________
	
	def ClearListeners(self):
		"""
		Remove all listeners to allow them to be destroyed.
		"""
		self.listeners = []
	
	#_____________________________________________________________________
	
	def StateChanged(self, change=None, *extra):
		"""
		This method should be called when we want a change to be reported
		to all objects previously added by AddListener. 
		
		Parameters:
			change -- the change which has occured.
			extra -- any extra parameters that should be passed.
		"""
		for obj in self.listeners:
			obj.OnStateChanged(self, change, *extra)
			
	#_____________________________________________________________________
	
#=========================================================================
