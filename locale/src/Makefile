#German
de:
	msgfmt de.po -o ../de/LC_MESSAGES/jokosher.mo

#Russian
ru:
	msgfmt ru.po -o ../ru/LC_MESSAGES/jokosher.mo
	

update:
	intltool-extract --type=gettext/glade ../../Jokosher.glade	
	xgettext -k_ -kN_ -o messages.pot ../../Jokosher.glade.h ../../*.py
	#German
	msgmerge de.po messages.pot > tmp
	mv tmp de.po
	#Russian
	msgmerge ru.po messages.pot > tmp
	mv tmp ru.po

all: de ru
