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
%.po: jokosher.pot
	##################
	#MERGING $@ AND $<
	##################
	msgmerge -UN $@ $<

#Generic rule for POT files
%.pot: ../../Jokosher/Jokosher.glade ../../Jokosher/*.py ../../Jokosher/Jokosher ../../Instruments/*.instr
	############
	#CREATING $@
	############
	intltool-extract --type=gettext/glade ../../Jokosher/Jokosher.glade
	python i18nReadInstr.py ../../Instruments/*.instr > i18n.instr.h
	xgettext --from-code=utf-8 -k_ -kN_ -o $@ ../../Jokosher/Jokosher.glade.h ../../Jokosher/*.py ../../Jokosher/Jokosher i18n.instr.h

update: $(shell ls *.po)

all: $(subst .po,.mo,$(shell ls *.po))

clean:
	rm *.mo i18n.instr.h ../../Jokosher/Jokosher.glade.h
