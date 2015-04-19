from flask import Flask, redirect, url_for, request, jsonify
from flask import current_app
from threading import Thread
from uuid import getnode as get_mac_address
import flask
import gocept.cache.method
import os
import platform
import psutil
import requests
import select
import socket
import subprocess
import sys
import tempfile
import time


# instance_relative_config is used later to load configuration from path relative to this file
app = Flask(__name__, instance_relative_config=True)

# loading external configuration
app.config.from_object('config.WorkerConfig')

logger = app.logger

# maintaining this to not break existing code
BRENDER_SERVER = app.config['BRENDER_SERVER']

MAC_ADDRESS = get_mac_address()  # the MAC address of the worker
HOSTNAME = socket.gethostname()  # the hostname of the worker
SYSTEM = platform.system() + ' ' + platform.release()

if (len(sys.argv) > 1):
    PORT = sys.argv[1]
else:
    PORT = 5000

def serverPost(command, values, message=''):
    """Make a POST request to the server.

    Values should be a dictionary to be used as payload to de post request.
    """

    if not values:
        values = {}

    try:
        requests.post("%s/%s" % (BRENDER_SERVER, command), values)
        return True
    except e:
        logger.error("ServerPost with data: \nSERVER=%s\ncommand=%s\nvalues=%s" % (BRENDER_SERVER, command, values.__str__()))
        return False

def serverGet(command):
    try:
        response = requests.get("%s/%s" % (BRENDER_SERVER, command))
        data = response.json()
        return data
    except:
        logger.error("ServerGet with data: \nSERVER=%s\ncommand=%s" % (BRENDER_SERVER, command))
        return {}


# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def start_worker():

    registered = serverPost('connect', {'mac_address': MAC_ADDRESS,
                                   'port': PORT,
                                   'hostname': HOSTNAME,
                                   'system': SYSTEM})

    if registered:
        """ if application is loaded in debug mode it will execute this function
        twice when application will start. And as consequence, it will register
        twice to the server and some times will bring to having worker working
        with two chunks of frames.
        So we set reloader to false.
        """
        app.run(host='0.0.0.0', use_reloader=False)
    else:
        logger.error("Unable to register this worker")

    logger.info("Exit.")


def _checkProcessOutput(process):
    ready = select.select([process.stdout.fileno(),
                           process.stderr.fileno()],
                          [], [])
    full_buffer = ''
    for fd in ready[0]:
        while True:
            buffer = os.read(fd, 1024)
            if not buffer:
                break
            full_buffer += buffer
    return full_buffer


def _interactiveReadProcess(process, job_id):
    full_buffer = ''
    tmp_buffer = ''
    while True:
        tmp_buffer += _checkProcessOutput(process)
        if tmp_buffer:
            # http_request("update_blender_output_from_i_dont_know", tmp_buffer)
            pass
        full_buffer += tmp_buffer
        if process.poll() is not None:
            break
    # It might be some data hanging around in the buffers after
    # the process finished
    full_buffer += _checkProcessOutput(process)
    return (process.returncode, full_buffer)


@app.route('/')
def index():
    return redirect(url_for('info'))


@app.route('/info')
def info():
    return jsonify(mac_address=MAC_ADDRESS,
                   hostname=HOSTNAME,
                   system=SYSTEM)

def handleMercurialRepo(options):
    from mercurial import hg, ui, commands
    from mercurial.error import RepoError

    ssh_key_file = options['ssh_key_file'].encode()
    source = (options['repo_source'] + options['server_repo_path']).encode()
    try:
        repo = hg.repository(ui.ui(), options['repo_path'].encode())
    except RepoError:
        if ssh_key_file:
            commands.clone(ui.ui(), source, dest=options['repo_path'].encode(), ssh="ssh -i %s" % ssh_key_file)
        else:
            commands.clone(ui.ui(), source, dest=options['repo_path'].encode())
        repo = hg.repository(ui.ui(), options['repo_path'].encode())

    retcode = 0
    if ssh_key_file:
        try:
            commands.pull(ui.ui(), repo, source=source, ssh="ssh -i %s" % ssh_key_file)
        except RepoError:
            shotLog_file.write("cannot get interface to repo")
            retcode = 1001
    else:
        try:
            commands.pull(ui.ui(), repo, source=source)
        except RepoError:
            shotLog_file.write("cannot get interface to repo")
            retcode = 1001

    if retcode == 0:
        commands.update(ui.ui(), repo, rev=options['rev'])

    return retcode

def handleShared(options):
    # we will do some check or configuration here for normal shared projects
    return 0

def generateRenderCommand(options):
    print(options)
    print('has job type ', options.has_key('job_type'))

    if options.has_key('job_type') and options['job_type'] == 'render':
        render_command = [
            options['blender_path'],
            '--background',
            options['file_path'],
            '--python',
            options['render_settings'],
            '--enable-autoexec',
            '--',
            '--frames',
            options['frames'],
            '--server',
            BRENDER_SERVER,
            '--shot',
            options['shot_id']
            ]
        return render_command

    if options.has_key('job_type') and options['job_type'] == 'bake':
        render_command = [
            options['blender_path'],
            '--background',
            options['file_path'],
            '--python',
            options['render_settings'],
            '--enable-autoexec'
            ]
        return render_command

    return None

def run_blender_in_thread(options):
    """We build the command to run blender in a thread

    There are many job types:
        render cpu
        render gpu
        bake smoke
        bake fluid
        run script
    """

    # save log content to disk
    shotLog_file = open("shot_%s.log" % options['shot_id'], 'a')

    retcode = 0
    full_output = ''

    # get content of render config file from server and save it to the worker tmp  position
    # this situation is useful when a worker can't have a shared resource with server
    logger.info("Get render confing file content from server.")
    result = serverGet('render-settings/%s' % options['render_settings'])

    if result and result.has_key('text'):
        content = result['text']
        tmpConfigFile = tempfile.NamedTemporaryFile(mode='w', delete=True, suffix='.py')
        options['render_settings'] = tmpConfigFile.name
        f = tmpConfigFile.file
        f.write(content)
        f.close()
    else:
        shotLog_file.write("can't get render config file")
        retcode = 1002

    # do some stuff when repo type is mercurial
    if options['repo_type'] == 'mercurial':
        retcode = handleMercurialRepo(options)

    else:
        retcode = handleShared(options)
        logger.debug("Handle project with non version control, a shared folder.")

    if retcode == 0:

        if os.path.isfile(options['file_path']):

            render_command = generateRenderCommand(options)
            if render_command == None:
                status = 'error'
                retcode = 1003
                logger.debug("No render command was generated")
            else:

                logger.info("Running %s" % render_command)

                process = subprocess.Popen(render_command,
                                           stdout=shotLog_file,
                                           stderr=shotLog_file)
                #flask.g.blender_process = process
                #process.wait()
                (stdout_msg, error_msg) = process.communicate()
                retcode = process.returncode
                #shotLog_file.write(stdout_msg + '\n*********** encountered errors ***********\n' + error_msg)
                #(retcode, full_output) = _interactiveReadProcess(process, options["job_id"])
                #flask.g.blender_process = None

                logger.info("return code is %s" % retcode)

                if retcode == 0:
                    status = 'finished'
                else:
                    status = 'error'
        else:
            status = 'error'
            shotLog_file.write("supplied file %s doesn't exist\n" % options['file_path'])
            retcode = 0

    if retcode != 0:
        status = 'error'

    # close log file
    shotLog_file.close()

    # cleaning, close tmp file and it will be deleted
    if result:
        tmpConfigFile.close()

    # report chunk outcome to server
    serverPost('frames/update/%s' % options['shot_id'], {'frames': options['frames'],
                                    'status': status,
                                    'full_output': full_output,
                                    'retcode': retcode})

@app.route('/execute_job', methods=['POST'])
def execute_job():
    options = {
        'file_path': request.form['file_path'],
        'blender_path': request.form['blender_path'],
        'frames': request.form['frames'].encode(),
        'render_settings': request.form['render_settings'],
        'repo_path': request.form['repo_path'],
        'repo_type': request.form['repo_type'],
        'rev': request.form['rev'],
        'ssh_key_file': current_app.config['SSH_KEY_FILE'],
        'repo_source': current_app.config['REPO_SOURCE'],
        'server_repo_path': request.form['server_repo_path'],
        'shot_id': request.form['shot_id'],
        'job_type' : request.form['job_type']
    }

    render_thread = Thread(target=run_blender_in_thread, args=(options,))
    render_thread.start()

    return jsonify(status='worker is running the command')


@app.route('/update', methods=['POST'])
def update():
    logger.debug('updating')
    blender_process = flask.g.get("blender_process")
    if blender_process:
        blender_process.kill()
    return('done')


def online_stats(system_stat):
    if 'blender_cpu' in [system_stat]:
        try:
            find_blender_process = [x for x in psutil.process_iter() if x.name == 'blender']
            cpu = []
            if find_blender_process:
                for process in find_blender_process:
                    cpu.append(process.get_cpu_percent())
                    logger.debug(sum(cpu))
                    return round(sum(cpu), 2)
            else:
                return int(0)
        except psutil._error.NoSuchProcess:
            return int(0)
    if 'blender_mem' in [system_stat]:
        try:
            find_blender_process = [x for x in psutil.get_process_list() if x.name == 'blender']
            mem = []
            if find_blender_process:
                for process in find_blender_process:
                    mem.append(process.get_memory_percent())
                    return round(sum(mem), 2)
            else:
                return int(0)
        except psutil._error.NoSuchProcess:
            return int(0)
    if 'system_cpu' in [system_stat]:
        cputimes_idle = psutil.cpu_times_percent(interval=0.5).idle
        cputimes = round(100 - cputimes_idle, 2)
        return cputimes
    if 'system_mem' in [system_stat]:
        mem_percent = psutil.phymem_usage().percent
        return mem_percent
    if 'system_disk' in [system_stat]:
        disk_percent = psutil.disk_usage('/').percent
        return disk_percent


def offline_stats(offline_stat):
    if 'number_cpu' in [offline_stat]:
        return psutil.NUM_CPUS

    if 'arch' in [offline_stat]:
        return platform.machine()

    '''
        TODO
        1. [Coming Soon] Add save to database for offline stats
        2. [Fixed] find more cpu savy way with or without psutil
        3. [Fixed] seems like psutil uses a little cpu when its checks cpu_percent
        it goes to 50+ percent even though the system shows 5 percent
    '''


def get_system_load_frequent():
    load = os.getloadavg()
    time.sleep(0.5)
    return ({
        "load_average": ({
            "1min": round(load[0], 2),
            "5min": round(load[1], 2),
            "15min": round(load[2], 2)
            }),
        "worker_cpu_percent": online_stats('system_cpu'),
        'worker_blender_cpu_usage': online_stats('blender_cpu')
        })


@gocept.cache.method.Memoize(120)
def get_system_load_less_frequent():
    time.sleep(0.5)
    return ({
        "worker_num_cpus": offline_stats('number_cpu'),
        "worker_architecture": offline_stats('arch'),
        "worker_mem_percent": online_stats('system_mem'),
        "worker_disk_percent": online_stats('system_disk'),
        "worker_blender_mem_usage": online_stats('blender_mem')
        })


@app.route('/run_info')
def run_info():
    logger.debug("get_system_load for %s" % HOSTNAME)

    return jsonify(mac_address=MAC_ADDRESS,
                   hostname=HOSTNAME,
                   system=SYSTEM,
                   update_frequent=get_system_load_frequent(),
                   update_less_frequent=get_system_load_less_frequent()
                   )
@app.route('/poweroff')
def poweroff():
    os.system("sudo /sbin/poweroff")
    return 'poweroff now'

if __name__ == "__main__":
    start_worker()
