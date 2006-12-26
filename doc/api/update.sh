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
	sed 's|#7799ee|#fcbb58|' $doc -i
	
	#purple -> green (Modules)
	sed 's|#aa55cc|#4e9a06|' $doc -i
	
	#magenta -> blue (Classes)
	sed 's|#ee77aa|#3465a4|' $doc -i
	
	#pink -> light blue (Inside classes)
	sed 's|#ffc8d8|#729fcf|' $doc -i
	
	#papaya -> brown (Functions)
	sed 's|#eeaa77|#c17d11|' $doc -i
done