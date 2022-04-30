@echo off
SET user=smoke
SET ip=192.168.0.1
SET pw=password
SET winuser=username

::might work, not tested: putty -ssh -t %user%@%ip% -pw %pw% -m C:\Users\%winuser%\Documents\AQI\putty_command.txt
plink -ssh -t %user%@%ip% -pw %pw% -m C:\Users\%winuser%\Documents\AQI\putty_command.txt

exit