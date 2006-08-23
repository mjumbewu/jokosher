"""
   This script takes in a list of .instr files as arguments
   and writes to stdout all the en_GB strings in C header
   file format. The header file can then be used to with
   xgettext to merge the strings into a POT file.
"""

import ConfigParser
import os, sys

#the section that contains the string to be translated
InstrSection = "i18n"
#the option in the above section whose value will be translated
InstrOption = "en_GB"
#the template string needed to make gettext able to parse the string
StringTemplate = 'char *s = N_("%s");'

#a list of strings collected from all files
listOfEnglishStrings = []

for path in sys.argv[1:]:
	if path.endswith(".instr"):
		config = ConfigParser.ConfigParser()
		
		if not os.path.exists(path):
			sys.stderr.write("Cannot find file %s\n" % path)
			continue
		
		config.read(path)
		if not config.has_option("i18n", "en"):
			sys.stderr.write("No en option in %s\n" % path)
			continue
		
		listOfEnglishStrings.append(config.get("i18n", "en"))
		
for string in listOfEnglishStrings:
	print StringTemplate % string
