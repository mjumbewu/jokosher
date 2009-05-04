#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	Utils.py
#	
#	This module contains a bunch of useful helper methods used elsewhere in
#	the code, that are not specific to any particular class.
#
#-------------------------------------------------------------------------------

import xml.dom.minidom as xml
import math, os.path, sys
import gtk, gobject
import webbrowser
import Globals

import gst
try:	
	import gst.pbutils
	have_pbutils = True
except:
	have_pbutils = False

# the highest range in decibels there can be between any two levels
DECIBEL_RANGE = 80

NANO_TO_MILLI_DIVISOR = gst.SECOND / 1000

#_____________________________________________________________________

def OpenExternalURL(url, message, parent, timestamp=0):
	"""
	Opens a given url in the user's default web browser.
		
	Parameters:
		url -- the url the user's default web browser will open.
		message -- the error message in the dialog window. the error message dialog will show if a link cannot be opened.
		parent -- parent window of the error message dialog.
	"""
		
	screen = gtk.gdk.screen_get_default()
	ret = False
	try:
		ret = gtk.show_uri(screen, url, timestamp)
	except:
		ret = webbrowser.open(url)
	
	if not ret and message:
		dlg = gtk.MessageDialog(parent,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR,
				gtk.BUTTONS_CLOSE)
		dlg.set_markup(message % url)
		dlg.run()
		dlg.destroy()
	
	return ret
#_____________________________________________________________________

def GetIconThatMayBeMissing(iconName, iconSize, returnGtkImage=True):
	"""
	First tries to get the icon with the given name from the icon theme.
	If that fails, it will try and load it from the Jokosher image directory.
	
	Parameters:
		iconName -- the string of the icon's name
		iconSize -- an icon size from the gtk.
		returnGtkImage -- If True, this method will return a gtk.Image.
				If False it will return a gtk.gdk.Pixbuf.
	
	Returns:
		an instance of gtk.gdk.Pixbuf that contains the requested image.
	"""
	pixbuf = None
	try:
		pixbuf = gtk.icon_theme_get_default().load_icon(iconName, iconSize, 0)
	except gobject.GError:
		path = os.path.join(Globals.IMAGE_PATH, "%s.png" % iconName)
		try:
			pixbuf = gtk.gdk.pixbuf_new_from_file(path)
		except:
			pass
	
	if not returnGtkImage:
		return pixbuf
	
	if pixbuf:
		image = gtk.Image()
		image.set_from_pixbuf(pixbuf)
	else:
		image = gtk.image_new_from_stock(gtk.STOCK_MISSING_IMAGE, iconSize)
	
	return image

#_____________________________________________________________________

def DbToFloat(f):
	"""
	Converts f from the decibel scale to a float.
	
	Parameters:
		f -- number in decibel format.
	
	Returns:
		a float in the [0,1] range.
	"""
	return pow(10., f / 20.)

#_____________________________________________________________________

def CalculateAudioLevelFromStructure(structure):
	"""
	Calculates an average for all channel levels.
	
	Parameters:
		channelLevels -- list of levels from each channel.
		
	Returns:
		an average level, also taking into account negative infinity numbers,
		which will be discarded in the average.
	"""
	# FIXME: currently everything is being averaged to a single channel
	channelLevels = structure["rms"]

	negInf = -1E+5000
	peaktotal = 0
	for peak in channelLevels:
		#if peak > 0.001:
		#	print channelLevels
		#don't add -inf values cause 500 + -inf is still -inf
		if peak != negInf:
			peaktotal += peak
		else:
			peaktotal -= DECIBEL_RANGE
	
	peaktotal /= len(channelLevels)
	
	peaktotal += DECIBEL_RANGE
	#convert to an integer
	peaktotal = min(peaktotal, DECIBEL_RANGE)
	peaktotal = max(peaktotal, -DECIBEL_RANGE)
	peakint = int((peaktotal / DECIBEL_RANGE) * sys.maxint)

	endtime = structure["endtime"]
	#convert number from gst.SECOND (i.e. nanoseconds) to milliseconds
	endtime_millis = int(endtime / NANO_TO_MILLI_DIVISOR)

	return (endtime_millis, [peakint])

#_____________________________________________________________________

def floatRange(start, end=None, inc=None):
	"""
	A range function capable of performing float increments.
	
	Parameters:
		start -- minimum value of the range list.
		end -- maximum value of the range list.
		inc -- delta between values in the range list.
	
	Considerations:
		If start is the only parameter given, the range goes from [0.0, start].
	
	Returns:
		A list with the range [start, end] in inc increments.
	"""
	if end == None:
		end = float(start)
		start = 0.0
	else:
		start = float(start)
	if not inc:
		inc = 1.0
	#check if the increment has the wrong sign
	#if it does, it may decrement instead of increment and we will get an infinite loop
	elif (start > end and inc > 0) or (start <= end and inc < 0):
		inc = -inc
		
	count = int(math.ceil((end - start) / inc))
	L = [None,] * max(count, 1)

	L[0] = start
	for i in xrange(1, count):
		L[i] = L[i-1] + inc
		
	return L

#_____________________________________________________________________

def StoreParametersToXML(self, doc, parent, parameters):
	"""
	Saves the variables indicated by the parameters in an XML document.
	
	Parameters:
		doc -- name of the XML document to save the settings into.
		parent -- XML parent tag to use in doc.
		parameters -- list of variable names whose value, save in doc.
	"""	   
	for param in parameters:
		node = doc.createElement(param)
		StoreVariableToNode(getattr(self, param), node)
		parent.appendChild(node)

#_____________________________________________________________________

def LoadParametersFromXML(self, parentElement):
	"""
	Loads parameters from an XML and fills variables of the same name
	in that module.
	
	Parameters:
		parentElement -- block of XML with the parameters.
	"""
	for node in parentElement.childNodes:
		if node.nodeType == xml.Node.ELEMENT_NODE:
			value = LoadVariableFromNode(node)
			setattr(self, node.tagName, value)
			
#_____________________________________________________________________

def StoreDictionaryToXML(doc, parent, dict, tagName=None):
	"""
	Saves a dictionary of settings in an XML document.
	
	Parameters:
		doc -- name of the XML document to save the settings into.
		parent -- XML parent tag to use in doc.
		dict -- dictionary to be saved in doc.
		tagName -- name used for all tag names.
		
	Considerations:
		If tagName is not given, the dictionary keys will be used for the tag names.
		This means that the keys must all be strings and can't have any invalid XML
		characters in them.
		If tagName is given, it is used for all the tag names, and the key is stored
		in the keyvalue attribute and its type in the keytype attribute.
	"""
	for key, value in dict.iteritems():
		if tagName:
			node = doc.createElement(tagName)
			StoreVariableToNode(key, node, "keytype", "keyvalue")
		#if no tag name was provided, use the key
		else:
			node = doc.createElement(key)
		
		StoreVariableToNode(value, node, "type", "value")
		parent.appendChild(node)

#_____________________________________________________________________

def LoadDictionaryFromXML(parentElement):
	"""
	For those times when you don't want to fill module variables with
	parameters from the XML but just want to fill a dictionary instead.
	
	Parameters:
		parentElement -- XML element from which the dictionary is loaded.
	
	Returns:
		a dictionary with the loaded values in (type, value) format.
	"""
	dictionary = {}
	
	for node in parentElement.childNodes:
		if node.nodeType == xml.Node.ELEMENT_NODE:
			if node.hasAttribute("keytype") and node.hasAttribute("keyvalue"):
				key = LoadVariableFromNode(node, "keytype", "keyvalue")
			else:
				key = node.tagName
			value = LoadVariableFromNode(node, "type", "value")
			dictionary[key] = value
	
	return dictionary

#_____________________________________________________________________

def StoreListToXML(doc, parent, itemList, tagName):
	"""
	Saves a list of items in an XML document.
	
	Parameters:
		doc -- name of the XML document to save the items into.
		parent -- XML parent tag to use in doc.
		itemList -- list of items to be saved in doc.
		tagName -- name used for all tag names.
	"""
	for value in itemList:
		node = doc.createElement(tagName)
		StoreVariableToNode(value, node)
		parent.appendChild(node)

#_____________________________________________________________________

def LoadListFromXML(parentElement):
	"""
	Loads a list from an XML file.
	
	Parameters:
		parentElement -- block of XML with the list nodes.
		
	Returns:
		a list with the loaded values.
	"""
	itemList = []
	
	for node in parentElement.childNodes:
		if node.nodeType == xml.Node.ELEMENT_NODE:
			value = LoadVariableFromNode(node)
			itemList.append(value)
	
	return itemList

#_____________________________________________________________________

def LoadVariableFromNode(node, typeAttr="type", valueAttr="value"):
	"""
	Loads a variable from an specific XML node.
	
	Example:
		Please refer to the StoreVariableToNode example
		for the explanation of the typeAttr and valueAttr
		parameters.
	
	Parameters:
		node -- node from which the variable is loaded.
		typeAttr -- string of the attribute name that the
					variable's type will be saved under.
		valueAttr -- string of the attribute name that the
					variable's value will be saved under.
	
	Returns:
		the loaded variable.
	"""
	if node.getAttribute(typeAttr) == "int":
		variable = int(node.getAttribute(valueAttr))
	elif node.getAttribute(typeAttr) == "float":
		variable = float(node.getAttribute(valueAttr))
	elif node.getAttribute(typeAttr) == "bool":
		variable = (node.getAttribute(valueAttr) == "True")
	elif node.getAttribute(typeAttr) == "NoneType":
		variable = None
	else:
		variable = node.getAttribute(valueAttr)
	
	return variable

#_____________________________________________________________________

def StoreVariableToNode(value, node, typeAttr="type", valueAttr="value"):
	"""
	Saves a variable to an specific XML node.
	
	Example:
		typeAttr = "foo"
		valueAttr = "bar"
		value = "mystring"
		
		would result in the following XML code:
			<foo="str" bar="mystring" />
	
	Parameters:
		value -- the value of the variable.
		node -- node to save the variable value to.
		typeAttr -- type of the variable to be saved.
		valueAttr -- value of the variable to be loaded.
	"""
	if type(value) == int:
		node.setAttribute(typeAttr, "int")
	elif type(value) == float:
		node.setAttribute(typeAttr, "float")
	elif type(value) == bool:
		node.setAttribute(typeAttr, "bool")
	elif value == None:
		node.setAttribute(typeAttr, "NoneType")
	else:
		node.setAttribute(typeAttr, "str")
		
	node.setAttribute(valueAttr, str(value))

#_____________________________________________________________________

def HandleGstPbutilsMissingMessage(message, callback, x_window_id=0):
	# Not all platforms have pbutils
	if not have_pbutils:
		return False

	#self._installing_plugins = True
	
	detail = gst.pbutils.missing_plugin_message_get_installer_detail(message)
	ctx = gst.pbutils.InstallPluginsContext()
	Globals.debug(detail)
	if x_window_id:
		ctx.set_x_id(x_window_id)
	
	ret = gst.pbutils.install_plugins_async([detail], ctx, callback)
	return True

#_____________________________________________________________________

def StringUnRepr(s):
	if sys.version > (2, 6, 0):
		import ast
		try:
			return ast.literal_eval(s)
		except ValueError, e:
			return ""
	
	if len(s) < 2:
		return ""

	quote = s[0]
	s = s[1:-1].replace("\\\\", "\\") \
	           .replace("\\t", "\t") \
	           .replace("\\n", "\n") \
	           .replace("\\r", "\r") \
	           .replace("\\" + quote, quote)
	
	strings = s.split("\\x")
	replace = strings[0]
	for string in strings[1:]:
		hex_str = string[:2]
		char = chr(int(hex_str, 16))
		replace += char + string[2:]

	return replace

#_____________________________________________________________________
