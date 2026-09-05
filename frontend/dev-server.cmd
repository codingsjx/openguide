@echo off
REM Dev launcher for the OpenGuide frontend (Vite).
REM Ensures `node` is on PATH for Vite and any child processes, since the
REM Node install dir may not be in the current session's PATH yet.
set "PATH=C:\Users\sjx11\node\node-v24.20.0-win-x64;%PATH%"
node "%~dp0..\node_modules\vite\bin\vite.js" %*
