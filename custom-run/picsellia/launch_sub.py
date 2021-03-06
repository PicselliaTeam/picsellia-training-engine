import subprocess
import shlex
from picsellia.client import Client
import os
import re 

os.environ["PYTHONUNBUFFERED"] = "1"
os.chdir('picsellia')
import sys
from picsellia.pxl_exceptions import AuthenticationError

# host = 'http://127.0.0.1:8000/sdk/v2/'
if 'api_token' not in os.environ:
    raise AuthenticationError("You must set an api_token to run this image")
api_token = os.environ["api_token"]

if "project_token" not in os.environ:
    raise AuthenticationError("You must set a valid project token to launch runs")
project_token = os.environ["project_token"]

if "run_id" not in os.environ:
    raise AuthenticationError("You must set a valid run id to launch run")
run_id = os.environ["run_id"]

# api_token = 'ac7a44b7be181774bd088c0099afd449b26bbeb7'
# project_token = 'a0b90c90-3a7e-4dda-b6d0-59d6c4c19804'
# sweep = 'test-sweep'
# run_id = ""
experiment = Client.Experiment(api_token=api_token, project_token=project_token)
experiment.get_run(run_id)

experiment.install_run_requirements()
experiment.download_run_data()
exp = experiment.checkout(experiment.run["experiment"]["id"])
os.environ["experiment_id"] = exp.id

filename = exp.download_script()


command = "python3 {}/{}".format(os.getcwd(), filename)
process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
part = "--#--Start Run"
replace_log = False
buffer = []
start_buffer = False
buffer_length = 0
exp.send_experiment_logging(part, part)

last_line = ""
f = open('{}-logs.txt'.format(experiment.run["experiment"]["id"]), 'w')
while True:
    output = process.stdout.readline()
    if output.decode("utf-8")  == '' and process.poll() is not None:
        f.write(last_line)
        f.close()
        exp.store('logs','{}-logs.txt'.format(exp.id))
        break
    print(output.decode("utf-8")) 
    if output:
        if output.decode("utf-8").startswith('--#--'):
            part = output.decode("utf-8")

        if output.decode("utf-8").startswith('-----'):
            progress_line_nb = exp.line_nb
            replace_log = True

        if output.decode("utf-8").startswith('--*--'):
            if replace_log:
                f.write(last_line + os.linesep)
            replace_log = False

        if re.match("--[0-9]--", output.decode("utf-8")[:6]):
            start_buffer = True
            buffer_length = int(output.decode("utf-8")[2])

        if re.match("---[0-9]---", output.decode("utf-8")[:8]):
            start_buffer = False
            exp.send_experiment_logging(buffer, part, special='buffer')
            exp.line_nb += (len(buffer)-1)
            buffer = []

        if start_buffer:
            buffer.append(output.decode("utf-8"))
            if len(buffer)==buffer_length:
                exp.send_experiment_logging(buffer, part, special='buffer')
                exp.line_nb += (buffer_length-1)
                buffer = []
        else:
            if not replace_log:
                exp.send_experiment_logging(output.decode("utf-8"), part)
            else:
                exp.line_nb = progress_line_nb
                exp.send_experiment_logging(output.decode("utf-8"), part)
        
        last_line = output.decode("utf-8")

        if not replace_log:
            a = f.write(output.decode("utf-8") + os.linesep)
        
if buffer != []:
    exp.send_experiment_logging(buffer, part, special='buffer')
exp.send_experiment_logging(str(process.returncode), part, special='exit_code')
if process.returncode == 0 or process.returncode == "0":
    exp.update(status='success')
    exp.update_run(status='success')
else:
    exp.update(status='failed')
    exp.update_run(status='failed')
exp.end_run()
rc = process.poll()
