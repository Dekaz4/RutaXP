@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
title Instalador automatico de RutaXP
if exist "%~dp0Instalador_RutaXP.exe" goto executable
if not exist "%~dp0Instalar.ps1" goto missing
echo Iniciando instalador de RutaXP para WoW Forever...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Instalar.ps1"
set "RUTAXP_EXIT=%ERRORLEVEL%"
goto finish
:executable
"%~dp0Instalador_RutaXP.exe"
set "RUTAXP_EXIT=%ERRORLEVEL%"
goto finish
:missing
echo [!] Falta Instalar.ps1. Extrae el ZIP completo antes de instalar.
set "RUTAXP_EXIT=1"
:finish
if "%RUTAXP_EXIT%"=="0" goto done
echo [!] No se ha completado la instalacion. Revisa el error anterior.
pause
:done
exit /b %RUTAXP_EXIT%
