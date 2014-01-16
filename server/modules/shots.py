from flask import Blueprint, render_template, abort, jsonify, request

import os
from os import listdir
from os.path import isfile, isdir, join, abspath, dirname

from model import *
from jobs import *
from utils import *

import subprocess
import time
import shutil

shots_module = Blueprint('shots_module', __name__)


def delete_shot(shot_id):
    try:
        shot = Shots.get(Shots.id == shot_id)
    except Shots.DoesNotExist:
        print('[error] Shot not found')
        return 'error'
    shot.delete_instance()
    print('[info] Deleted shot', shot_id)


@shots_module.route('/shots/')
def shots():
    shots = {}
    for shot in Shots.select():
        # percentage_done = 0
        # frame_count = shot.frame_end - shot.frame_start + 1
        # current_frame = shot.current_frame - shot.frame_start + 1
        # percentage_done = float(current_frame) / float(frame_count) * float(100)
        # percentage_done = round(percentage_done, 1)

        # get count of completed jobs and not
        finished = 0
        total = 0
        for j in Jobs.select().where(Jobs.shot_id == shot.id):
            total+=1
            if j.status == 'finished':
                finished+=1
        if finished > 0:
            percentage_done = round((float(finished)  / float(total)) * 100.0, 1)
        else:
            percentage_done = 0

        if percentage_done == 100:
            shot.status = 'completed'

        shots[shot.id] = {"frame_start": shot.frame_start,
                          "frame_end": shot.frame_end,
                          "current_frame": shot.current_frame,
                          "status": shot.status,
                          "shot_name": shot.shot_name,
                          "percentage_done": percentage_done,
                          "render_settings": shot.render_settings}
    return jsonify(shots)


@shots_module.route('/shots/browse/', defaults={'path': ''}, methods=['GET', 'POST'])
@shots_module.route('/shots/browse/<path:path>', methods=['GET', 'POST'])
def shots_browse(path):
    """We browse the production folder on the server.
    The path value gets appended to the active_show path value. The result is returned
    in JSON format.
    """

    show_id = request.form['show_id']
    snapshot_id = request.form['snapshot_id']

    snapshot = Snapshots.select().where(Snapshots.id == snapshot_id).get()

    #active_show = Settings.get(Settings.name == 'active_show')
    active_show = Shows.get(Shows.id == show_id)

    # path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # render_settings_path = os.path.join(path, 'render_settings/')

    absolute_path_root = os.path.join(active_show.path_server_snapshots, snapshot.name)
    parent_path = ''

    if path != '':
        absolute_path_root = os.path.join(absolute_path_root, path)
        parent_path = os.pardir

    # print(active_show.path_server)
    # print(listdir(active_show.path_server))

    # items = {}
    items_list = []

    for f in listdir(absolute_path_root):
        relative_path = os.path.join(path, f)
        absolute_path = os.path.join(absolute_path_root, f)

        # we are going to pick up only blend files and folders
        if absolute_path.endswith('blend'):
            # items[f] = relative_path
            items_list.append((f, relative_path, 'blendfile'))
        elif os.path.isdir(absolute_path):
            items_list.append((f, relative_path, 'folder'))

    #return str(onlyfiles)
    project_files = dict(
        project_path_server=active_show.path_server,
        parent_path=parent_path,
        # items=items,
        items_list=items_list)

    return jsonify(project_files)


@shots_module.route('/shots/update', methods=['POST'])
def shot_update():
    status = request.form['status']
    # TODO parse
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        print("updating shot %s = %s " % (shot_id, status))
    return "TEMP done updating shots "


@shots_module.route('/shots/start', methods=['POST'])
def shots_start():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        try:
            shot = Shots.get(Shots.id == shot_id)
        except Shots.DoesNotExist:
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id

        if shot.status == 'running':
            pass
        elif shot.status in ['error', 'completed']:
            delete_jobs(shot.id)
            create_jobs(shot)
            shot.status = 'running'
            shot.save()
            dispatch_jobs()
        elif shot.status in ['stopped', 'ready']:
            shot.status = 'running'
            shot.save()
            dispatch_jobs()

        # if shot.status != 'running':
        #     shot.status = 'running'
        #     shot.save()
        #     print ('[debug] Dispatching jobs')
        #     dispatch_jobs()

    return jsonify(
        shot_ids=shot_ids,
        status='running')


@shots_module.route('/shots/stop', methods=['POST'])
def shots_stop():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        print '[info] Working on shot', shot_id
        # first we delete the associated jobs (no foreign keys)
        try:
            shot = Shots.get(Shots.id == shot_id)
        except Shots.DoesNotExist:
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id

        if not shot.status in ['stopped', 'error']:
            stop_jobs(shot.id)
            shot.status = 'stopped'
            shot.save()

    return jsonify(
        shot_ids=shot_ids,
        status='stopped')


@shots_module.route('/shots/reset', methods=['POST'])
def shots_reset():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        try:
            shot = Shots.get(Shots.id == shot_id)
        except Shots.DoesNotExist:
            shot = None
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id

        if shot.status == 'running':
            return 'Shot %d is running' % shot_id
        else:
            shot.current_frame = shot.frame_start
            shot.status = 'ready'
            shot.save()

            delete_jobs(shot.id)
            create_jobs(shot)

    return jsonify(
        shot_ids=shots_list,
        status='ready')

def create_snapshot():
    pass

@shots_module.route('/shots/add', methods=['POST'])
def shot_add():
    print('adding shot')

    #snapshot_id = "%d" % round(time.time() * 1000000)
    snapshot_id = request.form['snapshot_id']
    print(snapshot_id)

    shot = Shots.create(
        attract_shot_id=1,
        show_id=int(request.form['show_id']),
        frame_start=int(request.form['frame_start']),
        frame_end=int(request.form['frame_end']),
        chunk_size=int(request.form['chunk_size']),
        current_frame=int(request.form['frame_start']),
        filepath=request.form['filepath'],
        shot_name=request.form['shot_name'],
        render_settings=request.form['render_settings'],
        status='ready',
        priority=10,
        owner='fsiddi',
        snapshot_id=snapshot_id)

    # create a snapshot of files for this shot
    # server_side_path
    #active_show_name = Settings.get(Settings.name == 'active_show').value
    #show = Shows.get(Shows.id == shot.show_id)
    #snapshots_path = show.path_server_snapshots

    # if snapshots_path:
    #     shot.snapshot_id = snapshot_id
    #     shot.save()

    #     prj_src_path = show.path_server
    #     prj_snapshot = os.path.join(snapshots_path, shot.snapshot_id)

    #     sync_command = "rsync -au %s/ %s/" % (prj_src_path, prj_snapshot)

    #     # register_thread = Thread(target=create_snapshot)
    #     # register_thread.setDaemon(True)
    #     # register_thread.start()
    #     process = subprocess.Popen(sync_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    #     process.wait()
    #     print('return code from sync is %d' % process.returncode)

    print('parsing shot to create jobs')

    create_jobs(shot)

    print('refresh list of available workers')

    #dispatch_jobs(shot.id)

    return 'done'


@shots_module.route('/shots/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    shots_list = list_integers_string(shot_ids)
    for shot_id in shots_list:
        shot = Shots.get(Shots.id == shot_id)

        print('working on', shot_id, '-', str(type(shot_id)))
        # first we delete the associated jobs (no foreign keys)
        delete_jobs(shot_id)
        # then we delete the shot
        delete_shot(shot_id)
    return 'done'
