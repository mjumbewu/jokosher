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
%.pot: ../../gtk-builder-ui/*.ui ../../Jokosher/*.py ../../Jokosher/Jokosher ../../Instruments/*.instr
	############
	#CREATING $@
	############
	python i18nReadInstr.py ../../Instruments/*.instr > i18n.instr.h
	xgettext -o $@ --language=glade ../../gtk-builder-ui/*.ui
	xgettext -o $@ --join-existing --language=python -k_ -kN_ ../../Jokosher/Jokosher
	xgettext -o $@ --join-existing --from-code=utf-8 -k_ -kN_ ../../Jokosher/*.py  i18n.instr.h

update: $(shell ls *.po)

all: $(subst .po,.mo,$(shell ls *.po))

clean:
	rm *.mo i18n.instr.h

