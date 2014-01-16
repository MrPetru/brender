import os

from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

from flask import current_app

# TODO(sergey): Generally not a good idea to import *
from model import *
from utils import *
from workers import *
import time
import subprocess

snapshots_module = Blueprint('snapshot_module', __name__)

@snapshots_module.route('/snapshots/')
def snapshots():

    snapshots = {}
    for snapshot in Snapshots.select().order_by(Snapshots.name):
        snapshots[snapshot.id] = dict(
            id=snapshot.id,
            name=snapshot.name,
            show_id=snapshot.show_id,
            comment=snapshot.comment)

    return jsonify(snapshots)

@snapshots_module.route('/snapshots/add', methods=['POST'])
def snapshots_add():

    show_id = request.form['show_id']
    show = Shows.get(Shows.id == show_id)
    snapshot_comment = request.form['snapshot_comment']

    snapshot_id = "%s_%s" % (show.name,time.strftime('%Y.%m.%d_%H:%M.%S'))

    snapshots_path = show.path_server_snapshots

    message = "can't create snapshot"
    if snapshots_path:
        # shot.snapshot_id = snapshot_id
        # shot.save()

        prj_src_path = show.path_server
        prj_snapshot = os.path.join(snapshots_path, snapshot_id)

        if 'SYNC_COMMAND' in current_app.config:
            print('using external config')
            sync_command = current_app.config['SYNC_COMMAND'] % (prj_src_path, prj_snapshot)
        else:
            sync_command = 'rsync -au --exclude="*.blend?" --exclude="*_v[0-9][0-9].blend" --exclude="*.zip" %s/ %s/' % (prj_src_path, prj_snapshot)

        # register_thread = Thread(target=create_snapshot)
        # register_thread.setDaemon(True)
        # register_thread.start()
        process = subprocess.Popen(sync_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        process.wait()
        print(process.communicate())
        if process.returncode == 0:
            message = "snapshot created with success"
            # save snapshot to database
            snapshot = Snapshots.create(name=snapshot_id, show_id=show_id, comment=snapshot_comment)
            return jsonify(dict(message=message, name=snapshot.name))

        else:
            message = "snapshot creation errro, code %d" % process.returncode

    print(message)

    return jsonify(dict(message=message, name=''))

@snapshots_module.route('/snapshots/del', methods=['POST'])
def snapshots_del():
    snapshot_id = request.form['snapshot_id']
    snapshot = Snapshots.get(Snapshots.id == snapshot_id)

    show = Shows.get(Shows.id == snapshot.show_id)

    shots = Shots.select().where(Shots.snapshot_id == snapshot_id)
    message = 'somthing was gone wrong when deleting snapshot on server'

    if len(shots) == 0:

        prj_snapshot = os.path.join(show.path_server_snapshots, snapshot.name)
        if os.path.exists(prj_snapshot):
            shutil.rmtree(prj_snapshot)
            message = 'snapshot were deleted on server'

    return jsonify(dict(message=message))