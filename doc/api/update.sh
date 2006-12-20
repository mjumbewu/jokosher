export PYTHONPATH=../../Jokosher
list="JokosherApp "
for module in ../../Jokosher/*.py; do
	name=`basename $module`
	name=${name%.py}
	if [ $name == "JokosherApp" ]; then continue; fi
	# skip Profiler as this borks pydoc 
	if [ $name == "Profiler" ]; then continue; fi 
	list=$list$name" "
done
pydoc -w $list

for doc in *.html; do
	echo Updating theme: $doc

	#grey -> white (Background)
	sed 's|#f0f0f8|#ffffff|' $doc -i
	
	#blue -> orange (Title)
	sed 's|#7799ee|#f2c66d|' $doc -i
	
	#purple -> green (Modules)
	sed 's|#aa55cc|#70b538|' $doc -i
	
	#magenta -> blue (Classes)
	sed 's|#ee77aa|#0462bf|' $doc -i
	
	#pink -> light blue (Inside classes)
	sed 's|#ffc8d8|#c7d7ff|' $doc -i
	
	#papaya -> brown (Functions)
	sed 's|#eeaa77|#9c7c3e|' $doc -i
done