@echo off
setlocal

echo ================================
echo  Instalador de code-context
echo ================================
echo.

:: Verificar que el script exista
if not exist "code_context.py" (
    echo No se encontro code_context.py en esta carpeta.
    echo Ejecuta el instalador desde la raiz del proyecto.
    pause
    exit /b
)

:: Detectar Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo Python no esta instalado.
        echo Descargalo desde https://www.python.org/downloads/
        pause
        exit /b
    )
)

:: Carpeta destino
set INSTALL_DIR=%USERPROFILE%\code-context

echo Creando carpeta en %INSTALL_DIR%
mkdir "%INSTALL_DIR%" >nul 2>nul

:: Copiar script
copy "code_context.py" "%INSTALL_DIR%\code_context.py" >nul

:: Crear wrapper
echo @echo off > "%INSTALL_DIR%\contexto.bat"
echo %PYTHON_CMD% "%INSTALL_DIR%\code_context.py" %%* >> "%INSTALL_DIR%\contexto.bat"

:: Verificar si ya esta en PATH del usuario
echo Verificando PATH...

echo %PATH% | find /I "%INSTALL_DIR%" >nul
if %errorlevel% neq 0 (
    echo Agregando al PATH del usuario...
    setx PATH "%PATH%;%INSTALL_DIR%" >nul
    echo PATH actualizado.
    echo Es necesario cerrar y abrir la terminal.
) else (
    echo La ruta ya esta en el PATH.
)

echo.
echo ======================================
echo Instalacion completada.
echo.
echo Luego podes usar:
echo.
echo contexto .
echo ======================================
echo.
pause