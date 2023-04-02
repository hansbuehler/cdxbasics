#@echo off

echo =====================================================================================
echo PIP build
echo =====================================================================================

REM https://packaging.python.org/tutorials/packaging-projects/
cd C:\Users\hansb\iCloudDrive\Python3\packages\cdxbasics
if exist dist rmdir /Q /S dist
mkdir dist
call conda activate base
call conda install twine -y
call python pip_modify_setup.py 
call python setup.py sdist bdist_wheel
call python -m twine upload dist\*
rmdir /Q /S dist

echo =====================================================================================
echo Conda install: uninstall; build; install
echo =====================================================================================

REM https://docs.conda.io/projects/conda-build/en/latest/user-guide/tutorials/build-pkgs-skeleton.html#troubleshooting
if exist conda rmdir /Q /S conda
mkdir conda
echo Creating intermediate conda environment to work in
call conda create -y -n cdxbasics_upload
call conda activate cdxbasics_upload
call conda install -y "python>=3.9"
copy conda_exists.py conda\
copy conda_modify_yaml.py conda\
cd conda
python -m conda_exists.py
if not %ERRORLEVEL% == 0 goto NOTFOUND
	echo Removing existing conda package from installation. That may take a while
	call conda uninstall -y cdxbasics
	goto FOUND
:NOTFOUND
	echo No existing cdxbasics installation found
:FOUND
echo Generating new conda skeleton package
call conda skeleton pypi cdxbasics
echo Making package platform independent
python -m conda_modify_yaml.py cdxbasics/meta.yaml
echo Building package. That may take a while
call conda build cdxbasics
echo Cleaning upcall 
call conda build purge
cd ..
rmdir /Q /S conda
echo Deleting conda environment
call conda activate base
call conda remove -y -n cdxbasics_upload --all

echo Attempting conda install
python -m conda_exists.py
if not %ERRORLEVEL% == 0 goto NOTFOUND2
	call conda upgrade -y cdxbasics -c hansbuehler
	goto FOUND2
:NOTFOUND2
	call conda install -y cdxbasics -c hansbuehler
:FOUND2

echo =====================================================================================
echo GIT upload
echo =====================================================================================

echo GIT upload
python git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
del /q .tmp.txt
REM echo Python test showed %MESSAGE%
git commit -a -m "%MESSAGE%"
git push

echo =====================================================================================
echo cdxbasics pip, conda, git done
echo =====================================================================================



