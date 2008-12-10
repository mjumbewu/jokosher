import platform, os, os.path

system = platform.system()

if system == "Windows":
	pass	
else:
	import pwd


def getFullName():
	if system == "Windows":
		return __WINDOWS_getFullName()
	else:
		return __UNIX_getFullName()


def __UNIX_getFullName():
	try:
		# Try to get the full name if it exists
		fullname = pwd.getpwuid(os.getuid())[4].split(",")[0]
		if fullname == "":
			fullname = pwd.getpwuid(os.getuid())[0]
		return fullname
	except:
		# If we can't get the fullname, then just use the login
		return pwd.getpwuid(os.getuid())[0]


def __WINDOWS_getFullName():
	#TODO: Work out how to get the fullname in windows
	return ""


def samefile(path1, path2):
	if system == "Windows":
		return __WINDOWS_samefile(path1, path2)
	else:
		return __UNIX_samefile(path1, path2)


def __WINDOWS_samefile(path1, path2):
	return path1 == path2


def __UNIX_samefile(path1, path2):
	return os.path.samefile(path1, path2)
