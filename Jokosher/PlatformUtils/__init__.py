
import platform

system = platform.system()

if system == "Windows":
	from Windows import *
else:
	from Unix import *

