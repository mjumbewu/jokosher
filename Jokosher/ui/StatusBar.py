#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	StatusBar.py
#	
#	This module is a better status bar than the one included
#	with gtk because it allows pango markup (bold, etc.).
#
#-------------------------------------------------------------------------------

import gtk

#=========================================================================

class StatusBar(gtk.Statusbar):
	"""
	Implements an improved status bar which allows pango markup styles (bold, italics, etc).
	"""
	#_____________________________________________________________________

	def __init__(self):
		"""
		Creates a new instance of StatusBar with no messages shown.
		"""
		gtk.Statusbar.__init__(self)
		# gtk.Statusbar contains a label inside a frame inside itself
		self.label = self.get_children()[0].get_children()[0]
		self.label.set_use_markup(True)
		
	#_____________________________________________________________________

	def Push(self, message):
		"""
		Insert a new message into the messages stack.
		
		Parameters:
			message -- string containing the new message to be added to the StatusBar.
			
		Return:
			the value of the next valid message ID.
		"""
		message_id = self.push(0, message)
		self.label.set_use_markup(True)
		return message_id
	
	#_____________________________________________________________________

	def Remove(self, message_id):
		"""
		Removes a new message from the messages stack.
		
		Parameters:
			message_id -- numerical id of the message to be removed from the StatusBar.
		"""
		self.remove(0, message_id)
		self.label.set_use_markup(True)
		
	#_____________________________________________________________________

#=========================================================================
