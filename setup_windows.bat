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
    if /I not "%~1"=="--no-pause" pause
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
        if /I not "%~1"=="--no-pause" pause
        exit /b
    )
)

:: Carpeta destino
set INSTALL_DIR=%USERPROFILE%\code-context

echo Creando carpeta en %INSTALL_DIR%
mkdir "%INSTALL_DIR%" >nul 2>nul

:: Copiar script + modulo (code_context.py importa modules.*)
copy "code_context.py" "%INSTALL_DIR%\code_context.py" >nul
if exist "%INSTALL_DIR%\modules" rmdir /S /Q "%INSTALL_DIR%\modules"
xcopy "modules" "%INSTALL_DIR%\modules\" /E /I /Y >nul
for /D /R "%INSTALL_DIR%\modules" %%D in (__pycache__) do if exist "%%D" rmdir /S /Q "%%D"

:: Instalar skill de opencode para agentes IA
set SKILL_DIR=%USERPROFILE%\.config\opencode\skills\contexto
if exist "skills\contexto\SKILL.md" (
    mkdir "%SKILL_DIR%" >nul 2>nul
    copy /Y "skills\contexto\SKILL.md" "%SKILL_DIR%\SKILL.md" >nul
    echo Skill de opencode instalada en %SKILL_DIR%
) else (
    echo No se encontro skills\contexto\SKILL.md, se omite la skill.
)

:: Crear wrapper
echo @echo off > "%INSTALL_DIR%\contexto.bat"
echo %PYTHON_CMD% "%INSTALL_DIR%\code_context.py" %%* >> "%INSTALL_DIR%\contexto.bat"

:: Verificar si ya esta en PATH del usuario
echo Verificando PATH...
echo %PATH% | find /I "%INSTALL_DIR%" >nul
if %errorlevel% neq 0 (
    echo Agregando al PATH del usuario...
    :: PowerShell en vez de setx: setx trunca el PATH a 1024 caracteres
    powershell -NoProfile -Command "$d='%INSTALL_DIR%'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if ([string]::IsNullOrEmpty($p)) { $new=$d } elseif (($p -split ';') -notcontains $d) { $new=$p.TrimEnd(';') + ';' + $d } else { $new=$p }; [Environment]::SetEnvironmentVariable('Path', $new, 'User')"
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
if /I not "%~1"=="--no-pause" pause
