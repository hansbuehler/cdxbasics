
python -m conda_exists
if %ERRORLEVEL% == 0 echo "No error"
python -m conda_exists
if not %ERRORLEVEL% == 0 echo "Error"

