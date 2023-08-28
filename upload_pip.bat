#@echo off

echo =====================================================================================
echo PIP build
echo =====================================================================================

REM https://packaging.python.org/tutorials/packaging-projects/
cd C:\Users\hansb\OneDrive\Python3\packages\cdxbasics
if exist dist rmdir /Q /S dist
mkdir dist
call conda activate base
call conda install twine -y
call python pip_modify_setup.py 
call python setup.py sdist bdist_wheel
call python -m twine upload dist\*
rmdir /Q /S dist

pip install --upgrade cdxbasics

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



