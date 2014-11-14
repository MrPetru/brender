from flask import Blueprint, render_template, abort, jsonify, request

#from model import *
#from utils import *

from mingmodel import session, Workers, Frames
import requests
from utils import stringToList
from bson import ObjectId

workers_module = Blueprint('workers_module', __name__)


#def update_worker(worker, worker_data):
#    if worker.connection != 'offline':
#        worker.connection = 'online'
#        worker.poweroff = ''
#        worker.save()
#
#    http_request(worker.ip_address, '/update', worker_data)
#
#    for key, val in worker_data.iteritems():
#        print(key, val)
#        if val:
#            setattr(worker, key, val)
#    worker.save()
#    print('status ', worker.status)


@workers_module.route('/workers/')
def workers():
    workers = {}

    for worker in Workers.getAll():
        try:
            requests.get('http://%s' % worker.ip_address)
            worker.connection = 'online'
        except Exception, e:
            print('[Warning] Worker', worker.hostname, 'is not online')
            worker.connection = 'offline'
            worker.status = 'enabled'

            # if worker is offline we will reset frames if assigned to that worker
        if worker.connection == 'offline':
            frames = Frames.query.update({'worker_id' : worker._id, 'status' :'running'}, {'$set' : {'status':'ready', 'worker_id' : None}})

        poweroff = ''
        if worker.baking == True:
            poweroff = poweroff + "only bake, "
        if worker.poweroff == 'poweroff':
            poweroff = "will shutdown when no more jobs"


        workers[worker.hostname] = {"id": worker._id.__str__(),
                                    "hostname": worker.hostname,
                                    "status": worker.status,
                                    "connection": worker.connection,
                                    "system": worker.system,
                                    "ip_address": worker.ip_address,
                                    "poweroff": poweroff}

        session.flush()
        session.clear()

    return jsonify(workers)

@workers_module.route('/workers/update', methods=['POST'])
def workers_update():
    status = request.form['status']
    # TODO parse
    workers_ids = request.form['id']
    workers_list = stringToList(workers_ids)
    for worker_id in workers_list:
        print("updating worker %s = %s " % (worker_id, status))
    return "TEMP done updating workers "


@workers_module.route('/workers/edit', methods=['POST'])
def workers_edit():
    worker_ids = request.form['id']
    worker_status = request.form['status']

    if worker_status in ['disabled', 'enabled']:
        worker_data = {"status": request.form['status'],
                       "config": request.form['config'],
                       "connection" : "online",
                       "poweroff" : '',
                       "baking" : False}

        if worker_ids:
            worker_ids = stringToList(worker_ids)
            Workers.updateById(worker_ids, worker_data)

            session.flush()
            session.clear()
            return jsonify(result='success')
        else:
            print('we edit all the workers')
            Workers.updateAll(worker_data)

        return jsonify(result='success')

    elif worker_status in ['poweroff']:
        if worker_ids:
            worker_ids = stringToList(worker_ids)
            Workers.updateById(worker_ids, {'poweroff' : 'poweroff'})

        session.flush()
        session.clear()
        return jsonify(result='sccess')

    elif worker_status in ['baking']:
        if worker_ids:
            worker_ids = stringToList(worker_ids)
            Workers.updateById(worker_ids, {'baking' : True})

        session.flush()
        session.clear()
        return jsonify(result='sccess')


@workers_module.route('/workers/delete', methods=['POST'])
def workers_delete():
    """Delete selected workers from database"
    """

    worker_ids = request.form['id']
    if worker_ids:
        ids = stringToList(worker_ids)
        ids = [ObjectId(id) for id in ids]
        print(ids)
        Workers.query.remove({'_id' : {'$in' : ids}})

        # TODO: check if there are jobs asigned to this worker and delete them

        session.flush()
        session.clear()
        return jsonify(result='success')
