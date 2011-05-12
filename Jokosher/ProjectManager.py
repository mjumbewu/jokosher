#
#	THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#	THE 'COPYING' FILE FOR DETAILS
#
#	ProjectManager.py
#
#	Contains various helper classes for the Project class as well as
#	all of the loading and saving to and from project files.
#
#=========================================================================

import urlparse, os, gzip, shutil, gst
import itertools, datetime, errno
import Globals, Utils, UndoSystem, LevelsList, IncrementalSave
import Project, Instrument, Event
import xml.dom.minidom as xml
import traceback
import PlatformUtils
import gio

#_____________________________________________________________________

def CreateNewProject(name, author, projecturi=None):
	"""
	Creates a new Project.

	Parameters:
		name --	the name of the Project.
		author - the name of the Project's author.
		projecturi -- the filesystem location for the new Project.
						Currently, only file:// URIs are considered valid.
		
	Returns:
		the newly created Project object.
	"""
	
	if not projecturi:
		projecturi = PlatformUtils.pathname2url(Globals.PROJECTS_PATH)
		
	project = InitProjectLocation(projecturi)
	project.name = name
	project.author = author
	
	project.SaveProjectFile(project.projectfile)
	return project
	
#_____________________________________________________________________
	
def InitProjectLocation(projecturi):
	"""
	Initialises the folder structure on disk for a Project.
	If no project is provided, a new one is created.
	Otherwise the given project is essentially moved to the new location.

	Parameters:
		projecturi -- the filesystem location for the new Project.
						Currently, only file:// URIs are considered valid.
	Returns:
		the given Project, or the newly created Project object.
	"""
	if not projecturi:
		raise CreateProjectError(4)
	
	(scheme, domain,folder, params, query, fragment) = urlparse.urlparse(projecturi, "file", False)

	folder = PlatformUtils.url2pathname(folder)

	if scheme != "file":
		# raise "The URI scheme used is invalid." message
		raise CreateProjectError(5)

	filename = "project.jokosher"
	folder_name_template = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
	projectdir = os.path.join(folder, folder_name_template)

	try:
		project = Project.Project()
	except gst.PluginNotFoundError, e:
		Globals.debug("Missing Gstreamer plugin:", e)
		raise CreateProjectError(6, str(e))
	except Exception, e:
		Globals.debug("Could not initialize project object:", e)
		raise CreateProjectError(1)

	unique_suffix = ""
	for count in itertools.count(1):
		try:
			os.mkdir(projectdir + unique_suffix)
		except OSError, e:
			if e.errno == errno.EEXIST:
				unique_suffix = "_%d" % count
				continue
			else:
				raise CreateProjectError(3)
		
		projectdir = projectdir + unique_suffix
		break
	
	project.projectfile = os.path.join(projectdir, filename)
	project.audio_path = os.path.join(projectdir, "audio")
	project.levels_path = os.path.join(projectdir, "levels")
	
	project.newly_created_project = True
	
	try:
		os.mkdir(project.audio_path)
		os.mkdir(project.levels_path)
	except:
		raise CreateProjectError(3)
		

	return project

#_____________________________________________________________________

def DeleteProjectLocation(project):
	main_dir = os.path.dirname(project.projectfile)
	try:
		if os.path.exists(project.audio_path):
			for file_name in os.listdir(project.audio_path):
				os.remove(os.path.join(project.audio_path, file_name))
			os.rmdir(project.audio_path)

		if os.path.exists(project.levels_path):
			for file_name in os.listdir(project.levels_path):
				os.remove(os.path.join(project.levels_path, file_name))
			os.rmdir(project.levels_path)
	
		if os.path.exists(main_dir):
			for file_name in os.listdir(main_dir):
				os.remove(os.path.join(main_dir, file_name))
			os.rmdir(main_dir)
	except OSError, e:
		Globals.debug("Cannot remove project. Have the permissions been changed, or other directories created inside the project folder?:\n\t%s" % main_dir)

#_____________________________________________________________________

def ImportProject(project_uri):
	try:
		old_project = LoadProjectFile(project_uri)
	except OpenProjectError, e:
		raise
		
	all_files = old_project.GetAudioAndLevelsFilenames(include_deleted=True)
	abs_audio_files, rel_audio_files, levels_files = all_files
	
	try:
		new_project = InitProjectLocation(PlatformUtils.pathname2url(Globals.PROJECTS_PATH))
	except CreateProjectError, e:
		return None
	
	delete_on_fail_list = []
	
	try:
		for audio_filename in rel_audio_files:
			src = gio.File(path=old_project.audio_path).get_child(audio_filename)
			dst = gio.File(path=new_project.audio_path).get_child(audio_filename)
		
			src.copy(dst)
			delete_on_fail_list.append(dst.get_uri())
		
			Globals.debug("Copy:\n\t" + src.get_uri() + "\n\t" + dst.get_uri())
		
		for level_filename in levels_files:
			src = gio.File(path=old_project.levels_path).get_child(level_filename)
			dst = gio.File(path=new_project.levels_path).get_child(level_filename)
		
			src.copy(dst)
			delete_on_fail_list.append(dst.get_uri())
		
			Globals.debug("Copy:\n\t" + src.get_uri() + "\n\t" + dst.get_uri())
		
		path, ext = os.path.splitext(old_project.projectfile)
		project_incremental_path = path + old_project.INCREMENTAL_SAVE_EXT
		path, ext = os.path.splitext(new_project.projectfile)
		new_project_incremental_path = path + new_project.INCREMENTAL_SAVE_EXT
		src = gio.File(project_incremental_path)
		dst = gio.File(new_project_incremental_path)
		
		try:
			src.copy(dst)
			delete_on_fail_list.append(dst.get_uri())
		except gio.Error, e:
			# If the project was closed properly, there will be no
			# .incremental file. This is not a problem.
			pass
		
		old_project.audio_path = new_project.audio_path
		old_project.levels_path = new_project.levels_path
		old_project.projectfile = new_project.projectfile
		old_project.SaveProjectFile(new_project.projectfile)
		return new_project.projectfile
	except gio.Error, gio_error:
		Globals.debug("Unable to import project; copying failed:\n\t%s" % gio_error.message)
		project_dir = gio.File(path=new_project.projectfile).get_parent().get_path()
		ImportCleanUpFiles(delete_on_fail_list, new_project.audio_path,
		        new_project.levels_path, project_dir)

		if gio_error.code == gio.ERROR_NOT_FOUND:
			# Ask user if they would like to continue even though
			# some files are missing
			pass
		elif gio_error.code == gio.ERROR_EXISTS:
			pass
		elif gio_error.code == gio.ERROR_IS_DIRECTORY:
			pass
		
		return None


#_____________________________________________________________________

def ImportCleanUpFiles(uris_to_delete, audio_path, levels_path, project_folder):
	for uri in uris_to_delete:
		try:
			gio.File(uri=uri).delete()
		except gio.Error, e:
			Globals.debug("ImportCleanUpFiles: " + repr(e))
	
	for path in (audio_path, levels_path, project_folder):
		try:
			gio.File(path=path).delete()
		except gio.Error, e:
			Globals.debug("ImportCleanUpFiles: " + repr(e))
			Gloabls.debug(path)

#_____________________________________________________________________

def ValidateProject(project):
	"""
	Checks that the Project is valid - i.e. that the files and 
	images it references can be found.
	
	Parameters:
		project -- The project to validate.
	
	Returns:
		True -- the Project is valid.
		False -- the Project contains non-existant files and/or images.
	"""
	unknownfiles=[]
	unknownimages=[]

	for instr in project.instruments:
		for event in instr.events:
			file = event.GetAbsFile()
			if file and (not os.path.exists(file)) and (not file in unknownfiles):
				unknownfiles.append(file)
	if len(unknownfiles) > 0 or len(unknownimages) > 0:
		raise InvalidProjectError(unknownfiles,unknownimages)

	return True
	
#_____________________________________________________________________

def LoadProjectFile(uri):
	"""
	Loads a Project from a saved file on disk.

	Parameters:
		uri -- the filesystem location of the Project file to load. 
				Currently only file:// URIs are considered valid.
				
	Returns:
		the loaded Project object.
	"""
	
	(scheme, domain, projectfile, params, query, fragment) = urlparse.urlparse(uri, "file", False)
	if scheme != "file":
		# raise "The URI scheme used is invalid." message
		raise OpenProjectError(1, scheme)

	projectfile = PlatformUtils.url2pathname(projectfile)

	Globals.debug("Attempting to open:", projectfile)

	if not os.path.exists(projectfile):
		raise OpenProjectError(4, projectfile)

	try:
		try:
			gzipfile = gzip.GzipFile(projectfile, "r")
			doc = xml.parse(gzipfile)
		except IOError, e:
			if e.message == "Not a gzipped file":
				# starting from 0.10, we accept both gzipped xml and plain xml
				file_ = open(projectfile, "r")
				doc = xml.parse(file_)
			else:
				raise e
	except Exception, e:
		Globals.debug(e.__class__, e)
		# raise "This file doesn't unzip" message
		raise OpenProjectError(2, projectfile)
	
	project = Project.Project()
	project.projectfile = projectfile
	projectdir = os.path.split(projectfile)[0]
	project.audio_path = os.path.join(projectdir, "audio")
	project.levels_path = os.path.join(projectdir, "levels")
	try:
		if not os.path.exists(project.audio_path):
			os.mkdir(project.audio_path)
		if not os.path.exists(project.levels_path):
			os.mkdir(project.levels_path)
	except OSError:
		raise OpenProjectError(0)
	
	#only open projects with the proper version number
	version = None
	if doc and doc.firstChild:
		version = doc.firstChild.getAttribute("version")

	if JOKOSHER_VERSION_FUNCTIONS.has_key(version):
		loaderClass = JOKOSHER_VERSION_FUNCTIONS[version]
		Globals.debug("Loading project file version", version)
		try:
			loaderClass(project, doc)
		except:
			tb = traceback.format_exc()
			Globals.debug("Loading project failed", tb)
			raise OpenProjectError(5, tb)
			
		if version != Globals.VERSION:
			#if we're loading an old version copy the project so that it is not overwritten when the user clicks save
			withoutExt = os.path.splitext(projectfile)[0]
			shutil.copy(projectfile, "%s.%s.jokosher" % (withoutExt, version))
		
		project.projectfile = projectfile
		return project
	else:
		# raise a "this project was created in an incompatible version of Jokosher" message
		raise OpenProjectError(3, version)

#=========================================================================

class _LoadZPOFile:
	def __init__(self, project, xmlDoc):
		"""
		Loads a project from a Jokosher 0.1 (Zero Point One) Project file into
		the given Project object using the given XML document.
		
		Parameters:
			project -- the Project instance to apply loaded properties to.
			xmlDoc -- the XML file document to read data from.
		"""
		params = xmlDoc.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(project, params)
		
		for instr in xmlDoc.getElementsByTagName("Instrument"):
			try:
				id = int(instr.getAttribute("id"))
			except ValueError:
				id = None
			i = Instrument.Instrument(project, None, None, None, id)
			self.LoadInstrument(i, instr)
			project.instruments.append(i)
			if i.isSolo:
				project.soloInstrCount += 1
	
	#_____________________________________________________________________
	
	def LoadInstrument(self, instr, xmlNode):
		"""
		Loads instrument properties from a Jokosher 0.1 XML node
		and saves them to the given Instrument instance.
		
		Parameters:
			instr -- the Instrument instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		Utils.LoadParametersFromXML(instr, params)
		#work around because in >0.2 instr.effects is a list not a string.
		instr.effects = []
		
		for ev in xmlNode.getElementsByTagName("Event"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			e = Event.Event(instr, None, id)
			self.LoadEvent(e, ev)
			e.levels_file = e.GetFilename() + Event.Event.LEVELS_FILE_EXTENSION
			instr.events.append(e)
		
		pixbufFilename = os.path.basename(instr.pixbufPath)
		instr.instrType = os.path.splitext(pixbufFilename)[0]
			
		instr.pixbuf = Globals.getCachedInstrumentPixbuf(instr.instrType)
		if not instr.pixbuf:
			Globals.debug("Error, could not load image:", instr.instrType)
			
		#initialize the actuallyIsMuted variable
		instr.OnMute()
		
	#_____________________________________________________________________
	
	def LoadEvent(self, event, xmlNode):
		"""
		Loads event properties from a Jokosher 0.1 XML node
		and saves then to the given Event instance.
		
		Parameters:
			event -- the Event instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		Utils.LoadParametersFromXML(event, params)
		
		try:
			xmlPoints = xmlNode.getElementsByTagName("FadePoints")[0]
		except IndexError:
			Globals.debug("Missing FadePoints in Event XML")
		else:
			for n in xmlPoints.childNodes:
				if n.nodeType == xml.Node.ELEMENT_NODE:
					pos = float(n.getAttribute("position"))
					value = float(n.getAttribute("fade"))
					event._Event__fadePointsDict[pos] = value
		
		event.GenerateWaveform()
		event._Event__UpdateAudioFadePoints()
		event.CreateFilesource()
	
	#_____________________________________________________________________

#=========================================================================

class _LoadZPTFile:
	def __init__(self, project, xmlDoc):
		"""
		Loads a Jokosher version 0.2 (Zero Point Two) Project file into
		the given Project object using the given XML document.
		
		Parameters:
			project -- the Project instance to apply loaded properties to.
			xmlDoc -- the XML file document to read data from.
		"""
		self.project = project
		self.xmlDoc = xmlDoc
		
		params = self.xmlDoc.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(self.project, params)
		
		# Hack to set the transport mode
		self.project.transport.SetMode(self.project.transportMode)
		
		undoRedo = (("Undo", self.project._Project__savedUndoStack),  
		("Redo", self.project._Project__redoStack))  
		for tagName, stack in undoRedo:  
			try:  
				undo = self.xmlDoc.getElementsByTagName(tagName)[0]  
			except IndexError:  
				Globals.debug("No saved %s in project file" % tagName)  
			else:  
				for cmdNode in undo.childNodes:  
					if cmdNode.nodeName == "Command":  
						objectString = str(cmdNode.getAttribute("object"))  
						functionString = str(cmdNode.getAttribute("function"))  
						paramList = Utils.LoadListFromXML(cmdNode)  
					
						functionString = ApplyUndoCompat(objectString, functionString, "0.2")
						
						undoAction = UndoSystem.AtomicUndoAction()  
						undoAction.AddUndoCommand(objectString, functionString, paramList)  
						stack.append(undoAction)  
		
		for instrElement in self.xmlDoc.getElementsByTagName("Instrument"):
			try:
				id = int(instrElement.getAttribute("id"))
			except ValueError:
				id = None
			instr = Instrument.Instrument(self.project, None, None, None, id)
			self.LoadInstrument(instr, instrElement)
			self.project.instruments.append(instr)
			if instr.isSolo:
				self.project.soloInstrCount += 1
				
		for instrElement in self.xmlDoc.getElementsByTagName("DeadInstrument"):
			try:
				id = int(instrElement.getAttribute("id"))
			except ValueError:
				id = None
			instr = Instrument.Instrument(self.project, None, None, None, id)
			self.LoadInstrument(instr, instrElement)
			self.project.graveyard.append(instr)
			instr.RemoveAndUnlinkPlaybackbin()
	
	#_____________________________________________________________________
	
	def LoadInstrument(self, instr, xmlNode):
		"""
		Restores an Instrument from version 0.2 XML representation.
		
		Parameters:
			instr -- the Instrument instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(instr, params)
		
		globaleffect = xmlNode.getElementsByTagName("GlobalEffect")
		
		for effect in globaleffect:
			elementname = str(effect.getAttribute("element"))
			Globals.debug("Loading effect:", elementname)
			gstElement = instr.AddEffect(elementname)
			
			propsdict = Utils.LoadDictionaryFromXML(effect)
			for key, value in propsdict.iteritems():
				gstElement.set_property(key, value)		
			
		for ev in xmlNode.getElementsByTagName("Event"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			event = Event.Event(instr, None, id)
			self.LoadEvent(event, ev)
			event.levels_file = event.GetFilename() + Event.Event.LEVELS_FILE_EXTENSION
			instr.events.append(event)
		
		for ev in xmlNode.getElementsByTagName("DeadEvent"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			event = Event.Event(instr, None, id)
			self.LoadEvent(event, ev, True)
			event.levels_file = event.GetFilename() + Event.Event.LEVELS_FILE_EXTENSION
			instr.graveyard.append(event)


		#load image from file based on unique type
		instr.pixbuf = Globals.getCachedInstrumentPixbuf(instr.instrType)
		if not instr.pixbuf:
			Globals.debug("Error, could not load image:", instr.instrType)
		
		# load pan level
		instr.panElement.set_property("panorama", instr.pan)
		#check if instrument is muted and setup accordingly
		instr.OnMute()
		#update the volume element with the newly loaded value
		instr.UpdateVolume()
		
	#_____________________________________________________________________
		
	def LoadEvent(self, event, xmlNode, isDead=False):
		"""
		Restores an Event from its version 0.2 XML representation.
		
		Parameters:
			event -- the Event instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(event, params)
		
		try:
			xmlPoints = xmlNode.getElementsByTagName("FadePoints")[0]
		except IndexError:
			Globals.debug("Missing FadePoints in Event XML")
		else:
			event._Event__fadePointsDict = Utils.LoadDictionaryFromXML(xmlPoints)

		if not isDead:
			#if event.isLoading or event.isRecording:
			# we have to always generate waveform because 0.10 uses different levels format
			event.GenerateWaveform()
			event._Event__UpdateAudioFadePoints()
			event.CreateFilesource()
	
	#_____________________________________________________________________
#=========================================================================

class _LoadZPNFile(_LoadZPTFile):
	LOADING_VERSION = "0.9"
	
	def __init__(self, project, xmlDoc):
		"""
		Loads a Jokosher version 0.9 (Zero Point Nine) Project file into
		the given Project object using the given XML document.
		
		Parameters:
			project -- the Project instance to apply loaded properties to.
			xmlDoc -- the XML file document to read data from.
		"""
		self.project = project
		self.xmlDoc = xmlDoc
		
		# A project being opened is either:
		# --> A 0.11 or earlier project (all of which required a name on creation).
		# --> A project created by Jokosher >0.11 which will load the name_is_unset
		#     attribute from the project file in the LoadParametersFromXML() function.
		# In the latter case, this attribute is overwriten, so here we set it to False 
		# for the first case.
		self.project.name_is_unset = False
		
		params = self.xmlDoc.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(self.project, params)
		
		notesNode = self.xmlDoc.getElementsByTagName("Notes")
		if notesNode:
			notes = notesNode[0].getAttribute("text")
			# notes are encoded using repr() to preserver \n and \t.
			self.project.notes = Utils.StringUnRepr(notes)
		
		# Hack to set the transport mode
		self.project.transport.SetMode(self.project.transportMode)
		
		undoRedo = (("Undo", self.project._Project__savedUndoStack),
				("Redo", self.project._Project__redoStack))
		for tagName, stack in undoRedo:
			try:
				undo = self.xmlDoc.getElementsByTagName(tagName)[0]
			except IndexError:
				Globals.debug("No saved %s in project file" % tagName)
			else:
				for actionNode in undo.childNodes:
					if actionNode.nodeName == "Action":
						action = UndoSystem.AtomicUndoAction()
						self.LoadUndoAction(action, actionNode)
						stack.append(action)
		
		for instrElement in self.xmlDoc.getElementsByTagName("Instrument"):
			try:
				id = int(instrElement.getAttribute("id"))
			except ValueError:
				id = None
			instr = Instrument.Instrument(self.project, None, None, None, id)
			self.LoadInstrument(instr, instrElement)
			self.project.instruments.append(instr)
			if instr.isSolo:
				self.project.soloInstrCount += 1
		
		for instrElement in self.xmlDoc.getElementsByTagName("DeadInstrument"):
			try:
				id = int(instrElement.getAttribute("id"))
			except ValueError:
				id = None
			instr = Instrument.Instrument(self.project, None, None, None, id)
			self.LoadInstrument(instr, instrElement)
			self.project.graveyard.append(instr)
			instr.RemoveAndUnlinkPlaybackbin()
	
	#_____________________________________________________________________
	
	def LoadInstrument(self, instr, xmlNode):
		"""
		Restores an Instrument from version 0.2 XML representation.
		
		Parameters:
			instr -- the Instrument instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(instr, params)
		
		globaleffect = xmlNode.getElementsByTagName("GlobalEffect")
		
		for effect in globaleffect:
			elementname = str(effect.getAttribute("element"))
			Globals.debug("Loading effect:", elementname)
			gstElement = instr.AddEffect(elementname)
			
			propsdict = Utils.LoadDictionaryFromXML(effect)
			for key, value in propsdict.iteritems():
				gstElement.set_property(key, value)		
			
		for ev in xmlNode.getElementsByTagName("Event"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			event = Event.Event(instr, None, id)
			self.LoadEvent(event, ev)
			instr.events.append(event)
		
		for ev in xmlNode.getElementsByTagName("DeadEvent"):
			try:
				id = int(ev.getAttribute("id"))
			except ValueError:
				id = None
			event = Event.Event(instr, None, id)
			self.LoadEvent(event, ev, True)
			instr.graveyard.append(event)


		#load image from file based on unique type
		instr.pixbuf = Globals.getCachedInstrumentPixbuf(instr.instrType)
		if not instr.pixbuf:
			Globals.debug("Error, could not load image:", instr.instrType)
		
		# load pan level
		instr.panElement.set_property("panorama", instr.pan)
		#check if instrument is muted and setup accordingly
		instr.OnMute()
		#update the volume element with the newly loaded value
		instr.UpdateVolume()
		
	#_____________________________________________________________________

	def LoadUndoAction(self, undoAction, xmlNode):
		"""
		Loads an AtomicUndoAction from an XML node.
		
		Parameters:
			undoAction -- the AtomicUndoAction instance to save the loaded commands to.
			node -- XML node from which the AtomicUndoAction is loaded.
					Should be an "<Action>" node.
			
		Returns:
			the loaded AtomicUndoAction object.
		"""
		for cmdNode in xmlNode.childNodes:
			if cmdNode.nodeName == "Command":
				objectString = str(cmdNode.getAttribute("object"))
				functionString = str(cmdNode.getAttribute("function"))
				paramList = Utils.LoadListFromXML(cmdNode)
				
				functionString = ApplyUndoCompat(objectString, functionString, self.LOADING_VERSION)
				
				undoAction.AddUndoCommand(objectString, functionString, paramList)
		
	#_____________________________________________________________________
#=========================================================================

class _LoadZPTenFile(_LoadZPNFile):
	LOADING_VERSION = "0.10"
	
	def LoadEvent(self, event, xmlNode, isDead=False):
		"""
		Restores an Event from its version 0.10 XML representation.
		
		Parameters:
			event -- the Event instance to apply loaded properties to.
			xmlNode -- the XML node to retreive data from.
		"""
		params = xmlNode.getElementsByTagName("Parameters")[0]
		
		Utils.LoadParametersFromXML(event, params)
		
		try:
			xmlPoints = xmlNode.getElementsByTagName("FadePoints")[0]
		except IndexError:
			Globals.debug("Missing FadePoints in Event XML")
		else:
			event._Event__fadePointsDict = Utils.LoadDictionaryFromXML(xmlPoints)

		if not isDead:
			if event.isLoading or event.isRecording:  
				event.GenerateWaveform()
			else:
				levels_path = event.GetAbsLevelsFile()
				try:
					event.levels_list.fromfile(levels_path)
				except LevelsList.CorruptFileError:
					Globals.debug("Cannot load levels from file", levels_path)
				if not event.levels_list:
					event.GenerateWaveform()
			event._Event__UpdateAudioFadePoints()
			event.CreateFilesource()
	
	#_____________________________________________________________________

#=========================================================================

class OpenProjectError(EnvironmentError):
	"""
	This class will get created when a opening a Project fails.
	It's used for handling errors.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, errno, info = None):
		"""
		Creates a new instance of OpenProjectError.
		
		Parameters:
			errno -- number indicating the type of error:
					1 = invalid uri passed for the Project file.
					2 = unable to unzip the Project.
					3 = Project created by a different version of Jokosher.
					4 = Project file doesn't exist.
					5 = Loading process faild with traceback
			info -- version of Jokosher that created the Project.
					Will be present only along with error #3.
				OR traceback of thrown exception, which will be present with #5
		"""
		EnvironmentError.__init__(self)
		self.info = info
		self.errno = errno
	
	#_____________________________________________________________________
	
#=========================================================================

class CreateProjectError(Exception):
	"""
	This class will get created when creating a Project fails.
	It's used for handling errors.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, errno, message=None):
		"""
		Creates a new instance of CreateProjectError.
		
		Parameters:
			errno -- number indicating the type of error:
					1 = unable to create a Project object.
					2 = path for Project file already exists.
					3 = unable to create file. (Invalid permissions, read-only, or the disk is full).
					4 = invalid path, name or author.
					5 = invalid uri passed for the Project file.
					6 = unable to load a particular gstreamer plugin (message will be the plugin's name)
			message -- a string with more specific information about the error
		"""
		Exception.__init__(self)
		self.errno = errno
		self.message = message
		
	#_____________________________________________________________________

#=========================================================================

class InvalidProjectError(Exception):
	"""
	This class will get created when there's an invalid Project.
	It's used for handling errors.
	"""
	
	#_____________________________________________________________________
	
	def __init__(self, missingfiles, missingimages):
		"""
		Creates a new instance of InvalidProjectError.
		
		Parameters:
			missingfiles -- filenames of the missing files.
			missingimages -- filenames of the missing images.
		"""
		Exception.__init__(self)
		self.files=missingfiles
		self.images=missingimages
		
	#_____________________________________________________________________

#=========================================================================

class ProjectExportException(Exception):
	"""
	This class will get created when there are problems with the soundcard inputs.
	It's used for handling errors.

	Error Codes:
	MISSING_ELEMENT - incorrect element name or element not installed.
	INVALID_ENCODE_BIN - invalid bin description; invalid syntax, invalid properties, incompatible caps, etc.
	"""
	MISSING_ELEMENT, INVALID_ENCODE_BIN = range(2)
	
	#_____________________________________________________________________
	
	def __init__(self, errno, message):
		"""
		Parameters:
			errno -- number indicating the type of error. See error codes above.
		"""
		Exception.__init__(self)
		self.errno = errno
		self.message = message
		
	#_____________________________________________________________________

#=========================================================================

def ApplyUndoCompat(objectString, functionString, version):
	if UNDO_COMPAT_DICT.has_key(version):
		compact_dict = UNDO_COMPAT_DICT[version]
		tuple_ = (objectString[0], functionString)
		if compact_dict.has_key(tuple_):
			return compact_dict[tuple_]
	
	return functionString

#=========================================================================

JOKOSHER_VERSION_FUNCTIONS = {
	"0.1" : _LoadZPOFile, 
	"0.2" : _LoadZPTFile, 
	"0.9" : _LoadZPNFile,
	"1.0" : _LoadZPNFile,  # 1.0 was never used in a release, and it identical to 0.9
	"0.10" : _LoadZPTenFile,
	"0.11" : _LoadZPTenFile,	# 0.11 is identical to 0.10, exception for project notes, whose presence can be detected
	"0.11.1" : _LoadZPTenFile,
}

zero_nine_compat = {("E", "Move") : "_Compat09_Move"}
zero_two_compat = {
	("E", "Split") : "_Compat02_Split",
	("E", "Join") : "_Compat02_Join",
	("E", "UndoTrim") : "_Compat02_UndoTrim",
}
#we can't import undo from 0.1 because the storage of undo was revamped for version 0.2

#all the compat info from newer versions, also applies to older versions
for key, value in zero_nine_compat.iteritems():
	zero_two_compat.setdefault(key, value)

UNDO_COMPAT_DICT = {"0.2" : zero_two_compat, "0.9" : zero_nine_compat}

#=========================================================================
