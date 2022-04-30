@echo off
SET user=smoke
SET ip=192.168.0.1
SET pw=password
SET winuser=username

putty -ssh %user%@%ip% -pw %pw% -m C:\Users\%winuser%\Documents\AQI\putty_command.txt
::plink -ssh %user%@%ip% -pw %pw echo hi

exit