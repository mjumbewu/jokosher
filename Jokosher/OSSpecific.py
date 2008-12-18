import platform, os, os.path, urllib

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


def url2pathname(url):
	if system == "Windows":
		return __WINDOWS_url2pathname(url)
	else:
		return __UNIX_url2pathname(url)


def __WINDOWS_url2pathname(url):
	return urllib.url2pathname(url).replace("\\", "\\\\")


def __UNIX_url2pathname(url):
	return urllib.url2pathname(url)


def pathname2url(path):
	if system == "Windows":
		return __WINDOWS_pathname2url(path)
	else:
		return __UNIX_pathname2url(path)


def __WINDOWS_pathname2url(path):
	#Windows pathname2url appends // to the front of the path
	return "file:%s" % urllib.pathname2url(path)


def __UNIX_pathname2url(path):
	return "file://%s" % urllib.pathname2url(path)
