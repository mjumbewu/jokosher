#
#	APIBrowserDialog
#	-----------
#	A graphical browser for the internal Jokosher API.
#-------------------------------------------------------------------------------

import inspect
import gtk
import re
import pkg_resources
import Jokosher.Project, Jokosher.Instrument, Jokosher.Event

#=========================================================================

class SearchDialog:
	
	SEARCHABLE_MODULES = {
		"Project" : (Jokosher.Project.Project,) ,
		"Instrument" : (Jokosher.Instrument.Instrument,) ,
		"Event" : (Jokosher.Event.Event,)
	}
	
	#_____________________________________________________________________
	
	def __init__(self, parent, writeCallback):
		self.parent = parent
		self.writeCallback = writeCallback
		
		xmlString = pkg_resources.resource_string(__name__, "SearchDialog.ui")
		self.gtkBuilder = gtk.Builder()
		self.gtkBuilder.add_from_string(xmlString)

		self.signals = {
			"OnAdd" : self.OnAdd,
			"OnClose" : self.OnClose,
			"OptionChanged" : self.OnSearchChange,
			"on_Selection_changed" : self.OnSelectionChange,
		}
		
		self.gtkBuilder.connect_signals(self.signals)
		
		self.dlg = self.gtkBuilder.get_object("SearchDialog")
		self.treeview = self.gtkBuilder.get_object("ResultsTreeview")
		self.searchCombo = self.gtkBuilder.get_object("searchComboEntry")
		self.moduleCombo = self.gtkBuilder.get_object("moduleCombo")
		self.regexCheckbox = self.gtkBuilder.get_object("regexCheckbox")
		self.docsCheckbox = self.gtkBuilder.get_object("docsCheckbox")
		self.argsCheckbox = self.gtkBuilder.get_object("argsCheckbox")
		self.privateCheckbox = self.gtkBuilder.get_object("privateCheckbox")
		self.documentationLabel = self.gtkBuilder.get_object("documentationLabel")
		
		self.model = gtk.ListStore(str, object)
		self.treeview.set_model(self.model)
		self.treeview.insert_column_with_attributes(-1, "Function", gtk.CellRendererText(), text=0)
		self.treeview.get_selection().set_mode(gtk.SELECTION_SINGLE)
		
		self.functionCacheDict = {}
		for name, moduleList in self.SEARCHABLE_MODULES.iteritems():
			self.functionCacheDict[name] = []
			list_ = self.functionCacheDict[name]
			
			for mod in moduleList:
				for func in mod.__dict__.itervalues():
					if callable(func):
						if func.func_name == "UndoWrapper":
							list_.append(func.wrapped_func)
						else:
							list_.append(func)
		
		for i in sorted(self.SEARCHABLE_MODULES.iterkeys()):
			self.moduleCombo.append_text(i)
		self.moduleCombo.set_active(0)
		
		self.UpdateTreeview()
		self.dlg.show_all()
		
	#_____________________________________________________________________
	
	def OnAdd(self, widget):
		"""
		Called when the user clicks on the add button.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		selection = self.treeview.get_selection().get_selected()
		if selection:
			func = self.model.get_value(selection[1], 1)
			self.writeCallback(GetFunctionRepr(func))
	#_____________________________________________________________________
	
	def OnClose(self, widget, event=None):
		"""
		Called when the user clicks on the close button either in the
		dialog, or on the window decorations.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		
		self.dlg.hide()
		return True
		
	#_____________________________________________________________________
	
	def OnSearchChange(self, widget, event=None):
		"""
		Called when some widget which effects the search result is changed.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		self.UpdateTreeview()
	#_____________________________________________________________________
	
	def OnSelectionChange(self, widget, event=None):
		"""
		Called when the function selected in the treeview changes.
		
		Parameters:
			widget -- reserved for GTK callbacks. Don't use it explicitly.
			event -- reserved for GTK callbacks. Don't use it explicitly.
		"""
		selection = self.treeview.get_selection().get_selected()
		if not selection:
			self.documentationLabel.hide()
		
		func = self.model.get_value(selection[1], 1)
		
		string = "%s\n\n%s" % (GetFunctionRepr(func), GetFormattedDoc(func))
		self.documentationLabel.set_text(string)
		self.documentationLabel.show()
	#_____________________________________________________________________
	
	def UpdateTreeview(self):
		showPrivate = self.privateCheckbox.get_active()
		searchDocs = self.docsCheckbox.get_active()
		searchArgs = self.argsCheckbox.get_active()
		useRegex = self.regexCheckbox.get_active()
		search = self.searchCombo.get_active_text()
		
		module = self.moduleCombo.get_active_text()
		if self.functionCacheDict.has_key(module):
			theList = self.functionCacheDict[module][:]
		else:
			theList = []
			for i in self.functionCacheDict.itervalues():
				theList.extend(i)
				
		finalList = []
		
		for func in theList:
			if not showPrivate and func.func_name.startswith("__"):
				continue
			
			if not search:
				finalList.append(func)
			elif useRegex:
				if re.match(search, func.func_name):
					finalList.append(func)
				elif searchDocs and re.match(search, func.__doc__):
					finalList.append(func)
				elif searchArgs and re.match(search, GetFunctionRepr(func)):
					finalList.append(func)
			else:
				if search in func.func_name:
					finalList.append(func)
				elif searchDocs and search in func.__doc__:
					finalList.append(func)
				elif searchArgs and search in GetFunctionRepr(func):
					finalList.append(func)
		
		finalList.sort(key=lambda x: x.func_name)
		self.model.clear()
		
		for func in finalList:
			self.model.append( (func.func_name, func) )
	
	#_____________________________________________________________________

#=========================================================================

def GetAPIFor(class_object):
	functionList = []
	for attr in class_object.__dict__.itervalues():
		if callable(attr) and not attr.func_name.startswith("_"):
			functionList.append( attr )
			
	return functionList
	
#_____________________________________________________________________
	
def GetFunctionRepr(func):
	argList = []
	argnames, vararg, kwarg, defaults = inspect.getargspec(func)
	
	if not argnames:
		argnames = []
	if not defaults:
		defaults = []
	
	def_start = len(argnames) - len(defaults)
	for index, i in enumerate(argnames):
		string = i
		if def_start <= index:
			string += "="
			string += str(defaults[ index - def_start ])
		argList.append(string)
	
	if vararg:
		argList.append("*" + vararg)
		
	if kwarg:
		argList.append("**" + kwarg)
	
	return func.func_name + "(" + ", ".join(argList) + ")"
	
#_____________________________________________________________________

def GetFormattedDoc(func):
	doc = func.__doc__
	if doc:
		num = 0
		for char in doc:
			if char == "\t":
				num += 1
			elif char.isspace():
				continue
			else:
				break
		
		doc = doc.strip()
		doc = ("\t" * num) + doc
		lineList = []
		for line in doc.split("\n"):
			lineList.append(line.replace("\t", "", num))
		
		return "\n".join(lineList)
		
	
	
#=========================================================================
