export PYTHONPATH=../../Jokosher
for doc in `ls ../../Jokosher/*.py | cut -d / -f 4 | cut -d . -f 1`
do
	pydoc -w $doc
done
