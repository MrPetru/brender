
from flask import Flask, jsonify, request
from mingmodel import Workers
from mingmodel import session
from modules.frames import frames_module
from modules.jobs import jobs_module
from modules.repository import repo_module
from modules.settings import settings_module
from modules.shots import shots_module
from modules.shows import shows_module
from modules.stats import stats_module
from modules.workers import workers_module

# instance_relative_config is used later to load configuration from path relative to this file
app = Flask(__name__, instance_relative_config=True)

# loading external configuration
app.config.from_object('config.ServerConfig')

@app.route('/')
def index():
    """Do nothing for now
    """

    return jsonify(status='ok')


@app.route('/connect', methods=['POST', 'GET'])
def connect():
    """When a worker will start up it will connect to the server to updat his
    IP address or other vital informations.
    """

    error = ''
    if request.method == 'POST':

        # We assemble the remote_addr value with
        # the port value sent from the worker
        ip_address = request.remote_addr + ':' + str(request.form['port'])
        mac_address = request.form['mac_address']
        hostname = request.form['hostname']
        system = request.form['system']

        worker = Workers.query.find({'mac_address' : mac_address}).first()

        if worker:
            print('This worker connected before, updating IP address')
            worker.ip_address = ip_address

        else:
            print('This worker never connected before')
            # create new worker object with some defaults.
            # Later on most of these values will be passed as JSON object
            # during the first connection
            mac_address = mac_address

            worker = Workers(hostname, ip_address, mac_address, system)

            print('Worker has been added')

        session.flush()

    return jsonify(error=error)

if __name__ == "__main__":
    app.register_blueprint(workers_module)
    app.register_blueprint(jobs_module)
    app.register_blueprint(shots_module)
    app.register_blueprint(shows_module)
    app.register_blueprint(settings_module)
    app.register_blueprint(stats_module)
    app.register_blueprint(repo_module)
    app.register_blueprint(frames_module)
    app.run(host=app.config['HOST'])
