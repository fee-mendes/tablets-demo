from flask import Flask, render_template, request
from flask_socketio import SocketIO
import os
import subprocess
import configparser
import time
import json
import argparse

app = Flask(__name__)
socketio = SocketIO(app)

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"
env["ANSIBLE_FORCE_COLOR"] = "1"

@app.route("/")
def index():
    return render_template('index.html', monitoring_ip=args.monitoring_ip)

# Global process variable
globals()["process"] = None

@socketio.on('shell_command')
def handle_shell_command(command):
    # Change this line to run your desired command
    pre_cmd = "ssh ubuntu@" + args.seed_node + " nodetool " 
    try:
        # Run the command and capture output
        process = subprocess.Popen(pre_cmd + command.replace('nodetool', ''), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        # Emit output
        if stdout:
            socketio.emit("shell_output", {"output": stdout.decode()})
        if stderr:
            socketio.emit("shell_output", {"output": stderr.decode()})
    except Exception as e:
        socketio.emit("shell_output", {"output": f"Error: {str(e)}"})

@socketio.on('cqlsh_command')
def handle_cqlsh_command(command):
    command = "cqlsh -e " + json.dumps(command) + " " + args.seed_node
    print(command)
    try:
        # Run the command and capture output
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        # Emit output
        if stdout:
            socketio.emit("cqlsh_output", {"output": stdout.decode()})
        if stderr:
            socketio.emit("cqlsh_output", {"output": stderr.decode()})
    except Exception as e:
        socketio.emit("cqlsh_output", {"output": f"Error: {str(e)}"})

@socketio.on("ping_playbook")
def handle_ping_command():
    playbook_cmd = ["ansible-playbook", playbook_path + "/ping.yml"]

    process = subprocess.Popen(playbook_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=playbook_path)

    for line in process.stdout:
        #iter(process.stdout.readline, ""):
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.wait()

@socketio.on("scale_playbook")
def handle_run_command():
    env = os.environ.copy()
    playbook_cmd = ["ansible-playbook", playbook_path + "/add_8xl.yml"]
    # Run the playbook using subprocess and stream output
    process = subprocess.Popen(playbook_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=playbook_path, env=env)

    while True: 
        output = process.stdout.readline()

        if output:
            if output.strip():
                socketio.emit("playbook_output", {"output": output}, callback=True)
        else:
            if process.poll() is not None:
                print("BREAKING")
                break

        socketio.sleep(0)
    
    process.wait()
    for remaining_output in process.stdout:
        socketio.emit("playbook_output", {"output": remaining_output}, callback=True)

@socketio.on("downscale_playbook")
def handle_down_command():
    playbook_cmd = ["ansible-playbook", playbook_path + "/scale_in.yml"]
    
    socketio.start_background_task(run_playbook, playbook_cmd)
    socketio.emit("playbook_output", {"output": "Downscaling initiated\n"})

def run_playbook(playbook_cmd):
    process = subprocess.Popen(playbook_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=playbook_path)
    
@socketio.on("stop_loader")
def handle_stop_loader():
    stop_cmd = ["/bin/bash", "-c", "./stop_loader.sh" + ' "' + loaders + '"']
    process = subprocess.Popen(stop_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=scripts_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.stdout.close()
    process.wait()

@socketio.on("batch_loader")
def handle_batch_command():
    loader_cmd = ["/bin/bash", "-c", "./background_job.sh " + args.seed_node]
    process = subprocess.Popen(loader_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=scripts_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.stdout.close()
    process.wait()


@socketio.on("500k_loader")
def handle_500_loader():
    loader_cmd = ["/bin/bash", "-c", './start_loader.sh 167000 ' + '"' + loaders + '" "' + nodes + '"']
    print(loader_cmd)
    process = subprocess.Popen(loader_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=scripts_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.stdout.close()
    process.wait()

@socketio.on("1m_loader")
def handle_1m_loader():
    loader_cmd = ["/bin/bash", "-c", "./start_loader.sh 350000 " + '"' + loaders + '" "' + nodes + '"']
    process = subprocess.Popen(loader_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=scripts_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.stdout.close()
    process.wait()

@socketio.on("kill_node_playbook")
def handle_kill_node():
    playbook_cmd = ["ansible-playbook", f"{playbook_path}/kill_node.yml"]
    process = subprocess.Popen(playbook_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=playbook_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.wait()

@socketio.on("restart_node_playbook")
def handle_restart_node():
    playbook_cmd = ["ansible-playbook", f"{playbook_path}/restart_node.yml"]
    process = subprocess.Popen(playbook_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=playbook_path)

    for line in process.stdout:
        socketio.emit("playbook_output", {"output": line})
        socketio.sleep(0)

    process.wait()

def parse_ansible_inventory(inventory_file):
    config = configparser.ConfigParser(allow_no_value=True)
    config.optionxform = str  # Preserve case sensitivity
    
    # Read the inventory file
    config.read(inventory_file)

    inventory = {}
    for section in config.sections():
        hosts = {}
        for item in config.items(section):
            hostname, *variables = item[0].split()
            host_vars = dict(var.split('=') for var in variables)
            hosts[hostname] = host_vars
        inventory[section] = hosts

    return inventory

#
# Methods not called from front-end
#
def cqlsh_run(cqlfile):
    command = "cqlsh -u cassandra -p cassandra -f " + cqlfile + " " + args.seed_node
    try:
        # Run the command and capture output
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        # Emit output
        if stdout:
            print(stdout.decode())
        if stderr:
            print(stderr.decode())
    except Exception as e:
        print(f"Error on cqlsh_run({cmd}): {str(e)}")
#
# A local command. If you need SSH, best to call a shellscript.
# 
def cmd_run(cmd):
    try:
        process = subprocess.Popen(["/bin/bash", "-c", cmd], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if stdout:
            print(stdout.decode())
        if stderr:
            print(stderr.decode())
    except Exception as e:
        print(f"Error on cmd_run({cmd}): {str(e)}")

# 
# Any customizations during startup should go here.
#
def initial_setup():
    print("Creating schema, Roles and WLP SLs")
    cqlsh_run(cql_path + '/setup.cql')
    print("Ingesting data - see /tmp/ingest.log for progress")
    cmd_run(scripts_path + "/ingest.sh " + args.seed_node)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebApp Settings")

    parser.add_argument(
        "--seed-node", "-s",
        required=True,
        type=str,
        help="IP address of the seed node."
    )
    parser.add_argument(
        "--monitoring-ip", "-m",
        required=True,
        type=str,
        help="IP address for monitoring."
    )
    parser.add_argument(
        "--init", "-i",
        action="store_true",
        help="Optional flag to initialize (default: False)."
    )

    args = parser.parse_args()

    program_cwd = os.path.dirname(os.path.abspath(__file__))
    playbook_path = os.path.join(program_cwd, "ansible")
    scripts_path = os.path.join(program_cwd, "scripts")
    cql_path = os.path.join(program_cwd, "cql")

    inventory_dict = parse_ansible_inventory(os.path.join(playbook_path, "inventory.ini"))

    # This assumes 'base' is the initial list of nodes, 'loaders' is the initial list of loaders
    nodes = " ".join(list(inventory_dict['base'].keys()))
    loaders = " ".join(list(inventory_dict['loader'].keys()))

    if args.init:
        initial_setup()

    #socketio.run(app, host='0.0.0.0', debug=True)
    socketio.run(app, host='0.0.0.0', allow_unsafe_werkzeug=True)
