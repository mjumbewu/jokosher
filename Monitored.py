
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
		if not obj in self.listeners:
			self.listeners.append(obj)
			
	#_____________________________________________________________________
			
	def RemoveListener(self, obj):
		if obj in self.listeners:
			self.listeners.remove(obj)
			
	#_____________________________________________________________________
			
	def StateChanged(self):
		for obj in self.listeners:
			obj.OnStateChanged(self)
			
	#_____________________________________________________________________
	
#=========================================================================