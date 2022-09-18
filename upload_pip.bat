@echo off
REM https://packaging.python.org/tutorials/packaging-projects/
REM Must be called from Anaconda

echo "====================================================================================="
echo "PIP build"
echo "====================================================================================="

cd C:\Users\hansb\iCloudDrive\Python3\packages\cdxbasics
del /Q dist\*.*
python setup.py sdist bdist_wheel
python -m twine upload dist/*
del /Q dist\*.*

echo "Upgrading cdxbasics locally"
pip install --upgrade cdxbasics

echo "====================================================================================="
echo "Now attempting conda upload. If this does not work, try 'anaconda login' first"
echo "====================================================================================="

cd conda
conda build .

echo "====================================================================================="
echo "GIT upload"
echo "====================================================================================="

cd ..
python git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
del /q .tmp.txt
git commit -a -m "%MESSAGE%"
git push

