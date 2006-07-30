import xml.dom.minidom as xml
import math

#_____________________________________________________________________

def DbToFloat(f):
	''' Converts f from the decibel scale to a 0..1 float
	'''
	return pow(10., f / 20.)

#_____________________________________________________________________

def StoreParametersToXML(self, doc, parent, parameters):
	'''Saves a list of variable names (parameters)
	   in an XML document (doc) with the parent XML tag (parent)
	'''
	for i in parameters:
		node = doc.createElement(i)
			
		if type(getattr(self, i)) == int:
			node.setAttribute("type", "int")
		elif type(getattr(self, i)) == float:
			node.setAttribute("type", "float")
		elif type(getattr(self, i)) == bool:
			node.setAttribute("type", "bool")
		else:
			node.setAttribute("type", "str")
		
		node.setAttribute("value", str(getattr(self, i)))
		parent.appendChild(node)

#_____________________________________________________________________

def LoadParametersFromXML(self, parentElement):
	for n in parentElement.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			if n.getAttribute("type") == "int":
				setattr(self, n.tagName, int(n.getAttribute("value")))
			elif n.getAttribute("type") == "float":
				setattr(self, n.tagName, float(n.getAttribute("value")))
			elif n.getAttribute("type") == "bool":
				value = (n.getAttribute("value") == "True")
				setattr(self, n.tagName, value)
			else:
				setattr(self, n.tagName, n.getAttribute("value"))

#_____________________________________________________________________

def floatRange(start, end=None, inc=None):
	"""A range function, that does accept float increments..."""

	if end == None:
		end = start + 0.0
		start = 0.0
	else:
		start += 0.0 # force it to be a float

	if inc == None:
		inc = 1.0
	count = int(math.ceil((end - start) / inc))

	L = [None,] * count

	L[0] = start
	for i in xrange(1,count):
		L[i] = L[i-1] + inc
	
	return L

#_____________________________________________________________________

def StoreDictionaryToXML(self, doc, parent, dict):
	'''Saves a dictionary of settings
	   in an XML document (doc) with the parent XML tag (parent)
	'''
	for key, value in dict.iteritems():
		node = doc.createElement(key)
			
		if type(value) == int:
			node.setAttribute("type", "int")
		elif type(value) == float:
			node.setAttribute("type", "float")
		elif type(value) == bool:
			node.setAttribute("type", "bool")
		else:
			node.setAttribute("type", "str")
		
		node.setAttribute("value", str(value))
		parent.appendChild(node)
		
#_____________________________________________________________________
		
def LoadDictionaryFromXML(parentElement):
	dictionary = {}
	for n in parentElement.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			if n.getAttribute("type") == "int":
				dictionary[n.tagName] = int(n.getAttribute("value"))
			elif n.getAttribute("type") == "float":
				dictionary[n.tagName] = float(n.getAttribute("value"))
			elif n.getAttribute("type") == "bool":
				value = (n.getAttribute("value") == "True")
				dictionary[n.tagName] = value
			else:
				dictionary[n.tagName] = n.getAttribute("value")
				
	return dictionary

#_____________________________________________________________________
