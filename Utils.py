import xml.dom.minidom as xml

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
