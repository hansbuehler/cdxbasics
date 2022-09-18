
python git_message.py >.tmp.txt
set /p MESSAGE=< .tmp.txt
echo "%MESSAGE%"

