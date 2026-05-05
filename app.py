from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
import subprocess
import random
import string
import uuid
from datetime import datetime, timedelta
import sys
import shutil
import threading
import time
import zipfile

app = Flask(__name__)
app.secret_key = 'jubayer-super-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

USERS_FILE = 'users.json'
BOTS_DIR = 'bots'

def load_users():
    if not os.path.exists(USERS_FILE):
        default = {
            "admin": {
                "password": "admin123",
                "role": "admin"
            }
        }
        save_users(default)
        return default
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def generate_server_link():
    p1 = random.randint(10, 99)
    p2 = random.randint(100, 999)
    p3 = random.randint(100, 999)
    p4 = random.randint(10, 99)
    code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{p1}-{p2}-{p3}-{p4}-{code}"

def clean_path(path):
    """পাথ ক্লিন করে - শুধু শেষ অংশ নেয়"""
    return os.path.basename(str(path))

def get_user_server_dir(server_id):
    """সঠিক পাথ ফেরত দেয় - bots/clean_id/"""
    clean_id = clean_path(server_id)
    server_dir = os.path.join(BOTS_DIR, clean_id)
    os.makedirs(server_dir, exist_ok=True)
    return server_dir

def create_default_files(server_dir):
    main_path = os.path.join(server_dir, 'main.py')
    if not os.path.exists(main_path):
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write('''# JUBAYER HOSTING - Default Bot
print("Bot is running on JUBAYER HOSTING")
print("Server is ready!")

import time
while True:
    print(f"Server active at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    time.sleep(30)
''')
    
    req_path = os.path.join(server_dir, 'requirements.txt')
    if not os.path.exists(req_path):
        with open(req_path, 'w', encoding='utf-8') as f:
            f.write('# Add your pip packages here\n')

def run_user_bot(server_id, main_file, requirements_file=None):
    """ইউজারের বট রান করায় - subprocess ফিক্স সহ"""
    # আইডি ক্লিন করো
    clean_id = clean_path(server_id)
    server_dir = get_user_server_dir(clean_id)
    main_file_clean = clean_path(main_file.strip())
    main_path = os.path.join(server_dir, main_file_clean)
    log_file = os.path.join(server_dir, 'output.log')
    
    print(f"[DEBUG] ========== BOT START ==========")
    print(f"[DEBUG] Original ID: {server_id}")
    print(f"[DEBUG] Clean ID: {clean_id}")
    print(f"[DEBUG] Server Dir: {server_dir}")
    print(f"[DEBUG] Main File: {main_file_clean}")
    print(f"[DEBUG] Main Path: {main_path}")
    print(f"[DEBUG] File exists: {os.path.exists(main_path)}")
    
    if not os.path.exists(main_path):
        if os.path.exists(server_dir):
            print(f"[DEBUG] Files in {server_dir}: {os.listdir(server_dir)}")
        return None, f"Main file '{main_file_clean}' not found at {main_path}"
    
    # Requirements install
    if requirements_file:
        req_file_clean = clean_path(requirements_file)
        req_path = os.path.join(server_dir, req_file_clean)
        if os.path.exists(req_path):
            try:
                subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_path], 
                             capture_output=True, text=True, cwd=server_dir, timeout=60)
            except:
                pass
    
    # পুরনো লগ ডিলিট
    if os.path.exists(log_file):
        os.remove(log_file)
    
    # 🔥 ফিক্সড: শুধু লিস্ট পাস করো, ডাবল পাথ হবে না
    try:
        # বট রান করার কমান্ড - শুধু লিস্ট ফরম্যাট
        cmd = [sys.executable, main_path]
        print(f"[DEBUG] Running command: {' '.join(cmd)}")
        print(f"[DEBUG] Working directory: {server_dir}")
        
        if sys.platform == 'win32':
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=server_dir,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=server_dir,
                text=True,
                bufsize=1
            )
        
        print(f"[DEBUG] Process started with PID: {proc.pid}")
        
        def capture_output():
            with open(log_file, 'a', encoding='utf-8') as log_f:
                for line in iter(proc.stdout.readline, ''):
                    if line:
                        line = line.rstrip('\n\r')
                        if line:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            log_f.write(f"[{timestamp}] {line}\n")
                            log_f.flush()
                proc.stdout.close()
        
        thread = threading.Thread(target=capture_output)
        thread.daemon = True
        thread.start()
        
        return proc.pid, None
    except Exception as e:
        print(f"[DEBUG] ERROR starting process: {str(e)}")
        return None, str(e)

def monitor_process(server_id, pid):
    while True:
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                       capture_output=True, text=True)
                if str(pid) not in result.stdout:
                    break
            else:
                os.kill(pid, 0)
        except:
            break
        time.sleep(5)
    
    users = load_users()
    for uname, data in users.items():
        for server in data.get('servers', []):
            if server['server_id'] == server_id:
                server['status'] = 'stopped'
                server['pid'] = None
                save_users(users)
                break
        break

def check_server_exists(server_link):
    users = load_users()
    for uname, data in users.items():
        if uname != 'admin' and data.get('role') == 'user':
            for server in data.get('servers', []):
                if server['link'] == server_link:
                    expiry_str = server.get('expiry', '')
                    if expiry_str and expiry_str != 'N/A':
                        try:
                            expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S.%f')
                            if datetime.now() > expiry_date:
                                return False, "expired"
                        except:
                            pass
                    return True, server
    return False, None

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    server_link = request.args.get('server', None)
    
    if server_link:
        exists, result = check_server_exists(server_link)
        if not exists:
            if result == "expired":
                return render_template('error.html', error_type="expired", server_link=server_link)
            else:
                return render_template('error.html', error_type="deleted", server_link=server_link)
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        
        if not server_link and username == 'admin' and password == users.get('admin', {}).get('password'):
            session['user'] = 'admin'
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        
        if server_link:
            for uname, data in users.items():
                if uname != 'admin' and data.get('role') == 'user':
                    for server in data.get('servers', []):
                        if server['link'] == server_link:
                            if username == uname and password == data.get('password'):
                                session['user'] = uname
                                session['role'] = 'user'
                                session['current_server_link'] = server_link
                                session['current_server_id'] = server['server_id']
                                return redirect(url_for('server_dashboard', server_link=server_link))
                            else:
                                return render_template('login.html', error="Invalid credentials", server_link=server_link)
        
        return render_template('login.html', error="Invalid username or password", server_link=server_link)
    
    return render_template('login.html', error=None, server_link=server_link)

@app.route('/server/<server_link>')
def server_dashboard(server_link):
    exists, result = check_server_exists(server_link)
    if not exists:
        if result == "expired":
            return render_template('error.html', error_type="expired", server_link=server_link)
        else:
            return render_template('error.html', error_type="deleted", server_link=server_link)
    
    if 'user' in session and session.get('role') == 'user':
        users = load_users()
        user_data = users.get(session['user'], {})
        for server in user_data.get('servers', []):
            if server['link'] == server_link:
                session['current_server_link'] = server_link
                session['current_server_id'] = server['server_id']
                return render_user_panel(server_link)
    
    return redirect(url_for('login', server=server_link))

def render_user_panel(server_link):
    users = load_users()
    current_server = None
    username = None
    
    for uname, data in users.items():
        if uname != 'admin' and data.get('role') == 'user':
            for server in data.get('servers', []):
                if server['link'] == server_link:
                    current_server = server
                    username = uname
                    break
        if current_server:
            break
    
    if not current_server:
        return render_template('error.html', error_type="deleted", server_link=server_link)
    
    return render_template('index.html',
                         username=username,
                         current_server=current_server,
                         server_link=server_link)

@app.route('/logout')
def logout():
    server_link = session.get('current_server_link')
    session.clear()
    if server_link:
        return redirect(url_for('login', server=server_link))
    return redirect(url_for('login'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    users = load_users()
    user_list = []
    total_servers = 0
    total_running = 0
    
    for username, data in users.items():
        if username != 'admin' and data.get('role') == 'user':
            servers = data.get('servers', [])
            running_count = sum(1 for s in servers if s.get('status') == 'running')
            total_servers += len(servers)
            total_running += running_count
            user_list.append({
                'username': username,
                'password': data.get('password'),
                'servers': servers,
                'server_count': len(servers),
                'running_count': running_count,
                'expiry': data.get('expiry', 'N/A'),
                'created_at': data.get('created_at', 'N/A')
            })
    
    return render_template('admin.html', users=user_list, total_servers=total_servers, total_running=total_running)

@app.route('/admin/create_server', methods=['POST'])
def create_server():
    if 'user' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    server_type = data.get('server_type')
    ram = data.get('ram')
    disk = data.get('disk')
    expiry_days = int(data.get('expiry_days', 30))
    
    users = load_users()
    
    server_link = generate_server_link()
    server_id = str(uuid.uuid4())[:8]
    
    # সার্ভার ডিরেক্টরি ক্রিয়েট
    server_dir = get_user_server_dir(server_id)
    create_default_files(server_dir)
    
    print(f"[DEBUG] Created server - ID: {server_id}, Dir: {server_dir}")
    
    expiry_date = datetime.now() + timedelta(days=expiry_days)
    
    new_server = {
        'server_id': server_id,
        'link': server_link,
        'dashboard_url': f"/server/{server_link}",
        'login_url': f"/login?server={server_link}",
        'full_link': f"https://{server_link}",
        'type': server_type,
        'ram': ram,
        'disk': disk,
        'status': 'stopped',
        'created': str(datetime.now()),
        'expiry': str(expiry_date),
        'expiry_days': expiry_days,
        'main_file': 'main.py',
        'requirements_file': 'requirements.txt',
        'pid': None,
        'started_at': None
    }
    
    if username not in users:
        users[username] = {
            'password': password,
            'role': 'user',
            'created_at': str(datetime.now()),
            'expiry': str(expiry_date),
            'servers': []
        }
    else:
        users[username]['password'] = password
    
    users[username]['servers'].append(new_server)
    save_users(users)
    
    return jsonify({
        'success': True,
        'hostname': f"https://{server_link}",
        'login_url': f"/login?server={server_link}",
        'dashboard_url': f"/server/{server_link}",
        'username': username,
        'password': password,
        'server_id': server_id
    })

@app.route('/admin/delete_server/<username>/<server_id>', methods=['POST'])
def delete_server(username, server_id):
    if 'user' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    users = load_users()
    if username in users:
        servers = users[username].get('servers', [])
        for server in servers:
            if server['server_id'] == server_id:
                if server.get('pid'):
                    try:
                        if sys.platform == 'win32':
                            subprocess.run(['taskkill', '/F', '/PID', str(server['pid'])], capture_output=True)
                        else:
                            os.kill(server['pid'], 15)
                    except:
                        pass
                server_dir = os.path.join(BOTS_DIR, clean_path(server_id))
                if os.path.exists(server_dir):
                    shutil.rmtree(server_dir)
                break
        
        users[username]['servers'] = [s for s in servers if s['server_id'] != server_id]
        
        if len(users[username]['servers']) == 0:
            del users[username]
        
        save_users(users)
    return jsonify({'success': True})

# ==================== FILE MANAGEMENT API ====================

@app.route('/api/files/<server_id>')
def list_files(server_id):
    server_dir = get_user_server_dir(server_id)
    files = []
    try:
        for item in os.listdir(server_dir):
            item_path = os.path.join(server_dir, item)
            files.append({
                'name': item,
                'is_dir': os.path.isdir(item_path),
                'size': os.path.getsize(item_path) if os.path.isfile(item_path) else 0,
                'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    except:
        pass
    return jsonify({'files': files})

@app.route('/api/file/<server_id>', methods=['GET'])
def get_file(server_id):
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'No filename'}), 400
    
    server_dir = get_user_server_dir(server_id)
    filepath = os.path.join(server_dir, filename)
    
    if not os.path.exists(filepath) or os.path.isdir(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'content': content, 'filename': filename})

@app.route('/api/file/<server_id>', methods=['POST'])
def save_file(server_id):
    data = request.get_json()
    filename = data.get('filename')
    content = data.get('content')
    
    server_dir = get_user_server_dir(server_id)
    filepath = os.path.join(server_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return jsonify({'success': True})

@app.route('/api/file/<server_id>', methods=['DELETE'])
def delete_file(server_id):
    data = request.get_json()
    filename = data.get('filename')
    
    server_dir = get_user_server_dir(server_id)
    filepath = os.path.join(server_dir, filename)
    
    if os.path.exists(filepath):
        if os.path.isdir(filepath):
            shutil.rmtree(filepath)
        else:
            os.remove(filepath)
    
    return jsonify({'success': True})

@app.route('/api/upload/<server_id>', methods=['POST'])
def upload_file(server_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    server_dir = get_user_server_dir(server_id)
    filepath = os.path.join(server_dir, file.filename)
    file.save(filepath)
    
    return jsonify({'success': True, 'filename': file.filename})

@app.route('/api/create_folder/<server_id>', methods=['POST'])
def create_folder(server_id):
    data = request.get_json()
    foldername = data.get('foldername')
    
    server_dir = get_user_server_dir(server_id)
    folderpath = os.path.join(server_dir, foldername)
    os.makedirs(folderpath, exist_ok=True)
    
    return jsonify({'success': True})

@app.route('/api/rename/<server_id>', methods=['POST'])
def rename_file(server_id):
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')
    
    server_dir = get_user_server_dir(server_id)
    old_path = os.path.join(server_dir, old_name)
    new_path = os.path.join(server_dir, new_name)
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        return jsonify({'success': True})
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/unzip/<server_id>', methods=['POST'])
def unzip_file(server_id):
    data = request.get_json()
    filename = data.get('filename')
    
    server_dir = get_user_server_dir(server_id)
    zip_path = os.path.join(server_dir, filename)
    
    if not os.path.exists(zip_path) or not filename.endswith('.zip'):
        return jsonify({'status': 'error', 'msg': 'Invalid zip file'}), 400
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(server_dir)
        return jsonify({'status': 'success', 'msg': 'File unzipped successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

# ==================== STARTUP & RUN API ====================

@app.route('/api/get_startup/<server_id>')
def get_startup(server_id):
    users = load_users()
    for uname, data in users.items():
        for server in data.get('servers', []):
            if server['server_id'] == server_id:
                return jsonify({
                    'main_file': server.get('main_file', 'main.py'),
                    'requirements_file': server.get('requirements_file', 'requirements.txt')
                })
    return jsonify({'main_file': 'main.py', 'requirements_file': 'requirements.txt'})

@app.route('/api/set_startup/<server_id>', methods=['POST'])
def set_startup(server_id):
    data = request.get_json()
    main_file = data.get('main_file')
    requirements_file = data.get('requirements_file')
    
    users = load_users()
    for uname, udata in users.items():
        for server in udata.get('servers', []):
            if server['server_id'] == server_id:
                server['main_file'] = main_file
                server['requirements_file'] = requirements_file if requirements_file else None
                save_users(users)
                return jsonify({'success': True})
    
    return jsonify({'error': 'Server not found'}), 404

@app.route('/api/run/<server_id>', methods=['POST'])
def run_server(server_id):
    users = load_users()
    for uname, udata in users.items():
        for server in udata.get('servers', []):
            if server['server_id'] == server_id:
                if server.get('status') == 'running':
                    return jsonify({'status': 'error', 'msg': 'Server already running'})
                
                main_file = server.get('main_file', 'main.py')
                req_file = server.get('requirements_file')
                
                pid, error = run_user_bot(server_id, main_file, req_file)
                if pid:
                    server['status'] = 'running'
                    server['pid'] = pid
                    server['started_at'] = str(datetime.now())
                    save_users(users)
                    
                    monitor_thread = threading.Thread(target=monitor_process, args=(server_id, pid))
                    monitor_thread.daemon = True
                    monitor_thread.start()
                    
                    return jsonify({'status': 'success', 'msg': 'Server started'})
                else:
                    return jsonify({'status': 'error', 'msg': error or 'Failed to start'})
    
    return jsonify({'status': 'error', 'msg': 'Server not found'})

@app.route('/api/stop/<server_id>', methods=['POST'])
def stop_server_api(server_id):
    users = load_users()
    for uname, udata in users.items():
        for server in udata.get('servers', []):
            if server['server_id'] == server_id:
                if server.get('status') == 'running' and server.get('pid'):
                    try:
                        if sys.platform == 'win32':
                            subprocess.run(['taskkill', '/F', '/PID', str(server['pid'])], capture_output=True)
                        else:
                            os.kill(server['pid'], 15)
                    except:
                        pass
                    server['status'] = 'stopped'
                    server['pid'] = None
                    save_users(users)
                    return jsonify({'status': 'success', 'msg': 'Server stopped'})
                else:
                    return jsonify({'status': 'error', 'msg': 'Server already stopped'})
    
    return jsonify({'status': 'error', 'msg': 'Server not found'})

@app.route('/api/logs/<server_id>')
def get_logs(server_id):
    server_dir = get_user_server_dir(server_id)
    log_file = os.path.join(server_dir, 'output.log')
    
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
    else:
        logs = ""
    
    return jsonify({'logs': logs})

@app.route('/api/clear_logs/<server_id>', methods=['POST'])
def clear_logs(server_id):
    server_dir = get_user_server_dir(server_id)
    log_file = os.path.join(server_dir, 'output.log')
    
    if os.path.exists(log_file):
        os.remove(log_file)
    
    return jsonify({'status': 'success', 'msg': 'Logs cleared'})

@app.route('/api/command', methods=['POST'])
def run_command():
    data = request.get_json()
    cmd = data.get('cmd', '')
    server_id = data.get('server_id', '')
    
    server_dir = get_user_server_dir(server_id)
    log_file = os.path.join(server_dir, 'output.log')
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=server_dir, timeout=30)
        output = result.stdout + result.stderr
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] $ {cmd}\n")
            for line in output.split('\n'):
                if line.strip():
                    f.write(f"[{timestamp}] {line}\n")
        
        return jsonify({'status': 'success', 'output': output[:500]})
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'msg': 'Command timeout'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

@app.route('/api/stats/<server_id>')
def get_stats(server_id):
    users = load_users()
    for uname, udata in users.items():
        for server in udata.get('servers', []):
            if server['server_id'] == server_id:
                uptime = "0h 0m 0s"
                if server.get('status') == 'running' and server.get('started_at'):
                    try:
                        start = datetime.strptime(server['started_at'], '%Y-%m-%d %H:%M:%S.%f')
                        diff = datetime.now() - start
                        hours = diff.seconds // 3600
                        minutes = (diff.seconds % 3600) // 60
                        seconds = diff.seconds % 60
                        days = diff.days
                        if days > 0:
                            uptime = f"{days}d {hours}h {minutes}m"
                        else:
                            uptime = f"{hours}h {minutes}m {seconds}s"
                    except:
                        pass
                
                return jsonify({
                    'cpu': '0.5%',
                    'ram': server.get('ram', '128 MiB'),
                    'uptime': uptime,
                    'net_in': '0.00 MiB',
                    'net_out': '0.00 MiB',
                    'status': server.get('status', 'stopped')
                })
    
    return jsonify({'cpu': '0%', 'ram': '0 MiB', 'uptime': '0h 0m 0s', 'net_in': '0 MiB', 'net_out': '0 MiB', 'status': 'unknown'})

if __name__ == '__main__':
    print("=" * 60)
    print("🔥 JUBAYER HOSTING - FULLY FIXED VERSION 🔥")
    print("=" * 60)
    print("📍 Admin Login: http://localhost:5000/login")
    print("👤 Username: admin")
    print("🔑 Password: admin123")
    print("=" * 60)
    print("✅ ALL FIXES APPLIED:")
    print("   - Double path error: FIXED")
    print("   - Subprocess Popen: CORRECTED")
    print("   - Main file path: CLEANED")
    print("   - Debug logging: ENHANCED")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)