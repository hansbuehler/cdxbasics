@echo off
REM before using this script, update the version string in setup.py and __init__.py

echo =====================================================================================
echo PIP build
echo =====================================================================================

REM https://packaging.python.org/tutorials/packaging-projects/
REM cd C:\Users\hansb\iCloudDrive\Python3\packages\cdxbasics
REM del /Q dist\*.*
REM python setup.py sdist bdist_wheel
REM python -m twine upload dist/*
REM del /Q dist\*.*

echo =====================================================================================
echo Conda install: uninstall; build; install
echo =====================================================================================

REM https://docs.conda.io/projects/conda-build/en/latest/user-guide/tutorials/build-pkgs-skeleton.html#troubleshooting
rmdir /Q /S conda
mkdir conda
cp conda_exists.py conda/
cd conda
python -m conda_exists.py
if not %ERRORLEVEL% == 0 goto NOTFOUND
	echo Removing existing conda package
	call conda uninstall -y cdxbasics
	goto FOUND
:NOTFOUND
	echo No existing cdxbasics installation found
:FOUND
echo Generating new conda package
call conda skeleton pypi cdxbasics
call conda build cdxbasics
echo Purging build
call conda build purge
cd ..
rmdir /Q /S conda
echo Attempting conda install
call conda install -y cdxbasics -c hansbuehler

echo =====================================================================================
echo GIT upload
echo =====================================================================================

python git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
del /q .tmp.txt
echo "Python test showed %MESSAGE%"
git commit -a -m "%MESSAGE%"
git push

echo =====================================================================================
echo cdxbasics pip, conda, git done
echo =====================================================================================



