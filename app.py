# app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import subprocess
import threading
import shlex
import re
import yaml

app = Flask(__name__)
socketio = SocketIO(app)

running_commands = {}

# Load allowed tools from YAML file
with open('allowed_tools.yaml', 'r') as f:
    config = yaml.safe_load(f)
    allowed_tools = set(config['allowed_tools'])

def clean_output(output):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', output)
    return ''.join(char for char in cleaned if ord(char) >= 32 or char in '\n\r\t')

def is_tool_allowed(command):
    tool = command.split()[0]
    return tool in allowed_tools

def run_command(command_id, command):
    process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
    running_commands[command_id] = process
    
    tool = command.split()[0]  # Extract the tool name from the command
    socketio.emit('command_started', {'id': command_id, 'command': command, 'tool': tool})

    for line in process.stdout:
        cleaned_line = clean_output(line.strip())
        if cleaned_line:
            socketio.emit('command_output', {'id': command_id, 'output': cleaned_line})

    process.wait()
    if process.returncode == 0:
        socketio.emit('command_completed', {'id': command_id, 'status': 'completed'})
    else:
        socketio.emit('command_completed', {'id': command_id, 'status': 'error'})

    del running_commands[command_id]

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('run_command')
def handle_command(data):
    command_id = data['id']
    command = data['command']

    if is_tool_allowed(command):
        threading.Thread(target=run_command, args=(command_id, command)).start()
    else:
        tool = command.split()[0]
        socketio.emit('command_error', {'id': command_id, 'error': f"Tool '{tool}' is not allowed to run."})

@socketio.on('stop_command')
def stop_command(data):
    command_id = data['id']
    if command_id in running_commands:
        running_commands[command_id].terminate()
        socketio.emit('command_stopped', {'id': command_id})

if __name__ == '__main__':
    socketio.run(app, debug=True)