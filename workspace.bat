@echo off
set PYTHONPATH=%CD%
echo Building Desktop App...
call apps\desktop\build_desktop.bat
echo Building CLI App...
call apps\cli\build_cli.bat
echo Monorepo build complete. Output is in the 'dist' directory.