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
import pango

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
		# gtk.Statusbar contains a label somewhere inside itself
		self.label = self.get_label_in_hierarchy()
		if self.label:
			self.label.set_use_markup(True)
		
	#_____________________________________________________________________
	
	def get_label_in_hierarchy(self):
		"""
		In Gtk+ 2.19 Statusbar was changed to keep a the Label inside an
		HBox inside a frame. In previous versions the Label was directly
		inside the frame. 
		
		Here we search the entire container hierarchy and hope it will
		continue to work even if another container is added in the
		future.
		"""
		unchecked = [self]
		while unchecked:
			widget = unchecked.pop(0)
			if isinstance(widget, gtk.Label):
				return widget
			elif isinstance(widget, gtk.Container):
				unchecked.extend(widget.get_children())
			
		return None
		
	#_____________________________________________________________________

	def Push(self, message):
		"""
		Insert a new message into the messages stack.
		
		Parameters:
			message -- string containing the new message to be added to the StatusBar.
			
		Return:
			the value of the next valid message ID.
		"""
		if not self.label:
			pango_attr_list, text_without_markup, accel_char = pango.parse_markup(message)
			message = text_without_markup
		
		message_id = self.push(0, message)
		if self.label:
			self.label.set_use_markup(True)
		return message_id
	
	#_____________________________________________________________________

	def Remove(self, message_id):
		"""
		Removes a new message from the messages stack.
		
		Parameters:
			message_id -- numerical id of the message to be removed from the StatusBar.
		"""
		self.remove_message(0, message_id)
		if self.label:
			self.label.set_use_markup(True)
		
	#_____________________________________________________________________

#=========================================================================
