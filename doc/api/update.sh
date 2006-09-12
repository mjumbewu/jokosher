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

