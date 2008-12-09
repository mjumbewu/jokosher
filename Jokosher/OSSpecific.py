import platform, os

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
