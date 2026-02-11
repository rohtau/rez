::
:: Script to install Rez with correct permissions in Windows
::

:: Make easy install when no argument is submitted:
:: Ask for parent location. /studio/tools or /opt
:: Ask for version
:: If version exists ask for another version or remove current install

:: Run install as rohtau\Admin
@echo off

set _rezversion=%1
IF "%~1" == "" (
    echo Please specify the version name to install
    echo This version:
    head -n 3 %CD%\src\rez\utils\_version.py | tail -n1
    exit /b 1
)
echo Install Rez %_rt_version% in C:\studio\tools\rez\%_rezversion%
runas.exe /env /user:rohtau\Admin  "cmd.exe /t0:2 /k python %CD%\install.py -v C:\studio\tools\rez\%_rezversion%"
