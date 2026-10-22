setlocal
call conda activate jm_dash
cd backend/api

:run_loop
python main.py
set rc=%ERRORLEVEL%
echo.
echo Python exited with %rc%.
echo Press R to rerun, Q to quit.
choice /c RQ /n >nul
if errorlevel 2 goto end
if errorlevel 1 (
    echo.
    echo Rerunning...
    echo.
    goto run_loop
)
:end
endlocal