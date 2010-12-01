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
		
	def set_last_used_now(self):
		self.last_used_time = time.time()
		
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
	
	project_items = []
	for path, name, create_time, last_used_time in items:
		if path and name and create_time and last_used_time:
			ob = ProjectItem(path, name, create_time, last_used_time)
			project_items.append(ob)
	
	return project_items

def StoreProjectItems(items):
	settings = Globals.settings.recentprojects
	
	paths = []
	names = []
	create_times = []
	last_used_times = []
	
	for item in items:
		paths.append(item.path)
		names.append(item.name)
		create_times.append(str(item.create_time))
		last_used_times.append(str(item.last_used_time))
	
	settings['paths'] = "|".join(paths)
	settings['names'] = "|".join(names)
	settings['create_times'] = "|".join(create_times)
	settings['last_used_times'] = "|".join(last_used_times)
	
	Globals.settings.write()
	
def NewProjectItem(path, name):
	now = time.time()
	return ProjectItem(path, name, now, now)
	
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
		
	

