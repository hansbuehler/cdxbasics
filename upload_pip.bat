REM https://packaging.python.org/tutorials/packaging-projects/

python setup.py sdist bdist_wheel
python -m twine upload dist/*