#Generic rule for MO files
%.mo: DIR1 = ../$(basename $@)
%.mo: DIR2 = $(DIR1)/LC_MESSAGES
%.mo: %.po
	##############
	#GENERATING $@
	##############
	if [ ! -d $(DIR1) ]; then mkdir $(DIR1); fi
	if [ ! -d $(DIR2) ]; then mkdir $(DIR2); fi
	msgfmt $< -o $@
	cp $@ $(DIR2)/jokosher.mo

#Generic rule for PO files
%.po: messages.pot
	##################
	#MERGING $@ AND $<
	##################
	msgmerge $@ messages.pot > tmp
	mv tmp $@

#Generic rule for POT files
%.pot: ../../Jokosher.glade.h ../../*.py
	############
	#CREATING $@
	############
	intltool-extract --type=gettext/glade ../../Jokosher.glade	
	xgettext -k_ -kN_ -o $@ $^

update: $(shell ls *.po)

all: $(subst .po,.mo,$(shell ls *.po))
