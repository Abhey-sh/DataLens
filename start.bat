@echo off
setlocal
cd /d "%~dp0"

if /I "%~1"=="--setup" goto setup
if not exist "node_modules\" goto setup
goto run

:setup
echo Running first-time setup...
call npm run setup
if errorlevel 1 exit /b %errorlevel%

:run
echo.
echo Starting DataLens...
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API docs: http://localhost:8000/docs
echo.
call npm start
exit /b %errorlevel%
