REM https://packaging.python.org/tutorials/packaging-projects/
REM Must be called from Anaconda

cd C:\Users\hansb\iCloudDrive\Python3\packages\cdxbasics
del /Q dist\*.*
python setup.py sdist bdist_wheel
python -m twine upload dist/*
del /Q dist\*.*

echo "Upgrading cdxbasics locally"
pip install --upgrade cdxbasics
