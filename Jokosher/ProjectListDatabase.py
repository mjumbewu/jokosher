#
#		THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#		THE 'COPYING' FILE FOR DETAILS
#
#		ProjectDatabase.py
#
#		This file maintains the list of all projects in the home folder.
#
#-------------------------------------------------------------------------------

import os
import time
import Globals

#=========================================================================

class ProjectItem:
	def __init__(self, path, name, create_time, last_used_time):
		self.path = path
		self.name = name
		self.create_time = int(create_time)
		self.last_used_time = int(last_used_time)
		
	def get_last_used(self):
		return self.last_used_time
		
	def set_name(self, name):
		self.name = name

def LoadProjectItems():
	settings = Globals.settings.recentprojects
	
	paths = settings['paths'].split("|")
	names = settings['names'].split("|")
	create_times = settings['create_times'].split("|")
	last_used_times = settings['last_used_times'].split("|")
	
	assert len(paths) == len(names) == len(create_times) == len(last_used_times)
	
	items = zip(paths, names, create_times, last_used_times)
	
	project_list = ProjectItemList()
	for path, name, create_time, last_used_time in items:
		if path and name and create_time and last_used_time:
			project_list.AddProjectItem(path, name, create_time, last_used_time)
	
	return project_list

def StoreProjectItems(items):
	settings = Globals.settings.recentprojects
	
	paths = []
	names = []
	create_times = []
	last_used_times = []
	
	for item in items:
		paths.append(item.path)
		names.append(item.name)
		create_times.append(str(int(item.create_time)))
		last_used_times.append(str(int(item.last_used_time)))
	
	settings['paths'] = "|".join(paths)
	settings['names'] = "|".join(names)
	settings['create_times'] = "|".join(create_times)
	settings['last_used_times'] = "|".join(last_used_times)
	
	Globals.settings.write()
	
def GetOldRecentProjects():
	output_list = []
	
	if Globals.settings.general.has_key("recentprojects"):
		filestring = Globals.settings.general["recentprojects"]
		filestring = filestring.split(",")
		recentprojectitems = []
		for i in filestring:
			if len(i.split("|")) == 2:
				recentprojectitems.append(i.split("|"))	
				
		for path, name in recentprojectitems:
			if not os.path.exists(path):
				Globals.debug("Error: Couldn't open recent project", path)
			else:
				output_list.append((path, name))
				
	return output_list
		

class ProjectItemList:
	def __init__(self):
		self.items = {}
		
	def __iter__(self):
		return self.items.itervalues()
		
	def __len__(self):
		return len(self.items)
		
	def Contains(self, path):
		return path in self.items
	
	def AddProjectItem(self, path, name, created=None, last_used=None):
		now = time.time()

		if path in self.items:
			# if the item already exists, just update values
			# and don't change the times unless explicitly given
			item = self.items[path]
			item.name = name
			if created is not None:
				item.create_time = int(created)
			if last_used is not None:
				item.last_used_time = now
		else:
			if created is None:
				created = now
			if last_used is None:
				last_used = now
			item = ProjectItem(path, name, created, last_used)
			self.items[path] = item
		
	def RemoveProjectItem(self, path):
		if path in self.items:
			del self.items[path]
	
	def UpdateLastUsedTime(self, path, new_time=None):
		if new_time is None:
			new_time = time.time()
	
		self.items[path].last_used_time = new_time
	
	def UpdateName(self, path, new_name):
		self.items[path].name = new_name
	
	def GetOrderedItems(self):
		return sorted(self.items.itervalues(), key=lambda x: x.last_used_time, reverse=True)
		
	def PurgeNonExistantPaths(self):
		non_existant = []
		for item in self.items.itervalues():
			if not os.path.exists(item.path):
				non_existant.append(item.path)
				
		for path in non_existant:
			del self.items[path]
	
	

