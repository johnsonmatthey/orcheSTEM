cd path_to_app\orcheSTEM
@REM start cmd.exe /k call run_backend.bat
@REM start cmd.exe /k call run_frontend.bat

@REM call run_backend.bat
start "Frontend" cmd /k "%~dp0run_frontend.bat"
start "Backend" cmd /k "%~dp0run_backend.bat"

