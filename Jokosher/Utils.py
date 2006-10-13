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
import math

#_____________________________________________________________________

def DbToFloat(f):
	"""Converts f from the decibel scale to a 0..1 float"""
	
	return pow(10., f / 20.)

#_____________________________________________________________________

def floatRange(start, end=None, inc=None):
	"""A range function, that does accept float increments..."""
	
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
	"""Saves a list of variable names (parameters)
	   in an XML document (doc) with the parent XML tag (parent)"""
	   
	for i in parameters:
		node = doc.createElement(i)
		StoreVariableToNode(getattr(self, i), node)
		parent.appendChild(node)

#_____________________________________________________________________

def LoadParametersFromXML(self, parentElement):
	"""Loads parameters from the XML and fills variables of the same name
	in that module. The parentElement is the block of XML with the
	parameters."""
	
	for n in parentElement.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			value = LoadVariableFromNode(n)
			setattr(self, n.tagName, value)
			
#_____________________________________________________________________

def StoreDictionaryToXML(doc, parent, dict):
	"""Saves a dictionary of settings
	   in an XML document (doc) with the parent XML tag (parent)"""
	   
	for key, value in dict.iteritems():
		node = doc.createElement("Item")
		StoreVariableToNode(key, node, "keytype", "keyvalue")
		StoreVariableToNode(value, node, "type", "value")
		parent.appendChild(node)

#_____________________________________________________________________

def LoadDictionaryFromXML(parentElement):
	"""For those times when you don't want to fill module variables with
	parameters from the XML but just want to fill a dictionary instead."""
	
	dictionary = {}
	
	for n in parentElement.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			key = LoadVariableFromNode(n, "keytype", "keyvalue")
			value = LoadVariableFromNode(n, "type", "value")
			dictionary[key] = value
	
	return dictionary

#_____________________________________________________________________

def StoreListToXML(doc, parent, itemList, tagName):
	for value in itemList:
		node = doc.createElement(tagName)
		StoreVariableToNode(value, node)
		parent.appendChild(node)

#_____________________________________________________________________

def LoadListFromXML(parentElement):
	itemList = []
	
	for n in parentElement.childNodes:
		if n.nodeType == xml.Node.ELEMENT_NODE:
			value = LoadVariableFromNode(n)
			itemList.append(value)
	
	return itemList

#_____________________________________________________________________

def LoadVariableFromNode(node, typeAttr="type", valueAttr="value"):
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
