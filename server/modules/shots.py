from flask import Blueprint, render_template, abort, jsonify, request

import os
from os import listdir
from os.path import isfile, isdir, join, abspath, dirname

#from model import *
#from jobs import *
from jobs import create_jobs, create_job, delete_jobs, stop_jobs
from utils import *
from frames import dispatch_frames

import subprocess
import time
import shutil

from mingmodel import Shots, session, Shows, Frames
from bson import ObjectId

shots_module = Blueprint('shots_module', __name__)


def delete_shot(shot_id):

    Shots.query.remove({'_id' : ObjectId(shot_id)})
    #if not shot:
    #    #print('[error] Shot not found')
    #    return 'error'

    session.flush()
    print('[info] Deleted shot', shot_id)


@shots_module.route('/shots/')
def shots():
    shots = {}
    for shot in Shots.query.find({}).all():
        # percentage_done = 0
        # frame_count = shot.frame_end - shot.frame_start + 1
        # current_frame = shot.current_frame - shot.frame_start + 1
        # percentage_done = float(current_frame) / float(frame_count) * float(100)
        # percentage_done = round(percentage_done, 1)

        # get count of completed jobs and not
        total = shot.frame_end - shot.frame_start + 1
        finished = Frames.query.find({'shot_id' : shot._id, 'status' : 'done'}).count()

        if finished > 0:
            percentage_done = round((float(finished)  / float(total)) * 100.0, 1)
        else:
            percentage_done = 0

        if percentage_done == 100:
            shot.status = 'completed'

        show = Shows.query.find({'_id' : shot.show_id}).first()
        project_name = show.name

        shots[shot._id.__str__()] = {"frame_start": shot.frame_start,
                          "frame_end": shot.frame_end,
                          "current_frame": shot.current_frame,
                          "status": shot.status,
                          "shot_name": shot.shot_name,
                          "percentage_done": percentage_done,
                          "render_settings": shot.render_settings,
                          "project_name": project_name,
                          "frame_total": total,
                          "frame_done": finished}
    return jsonify(shots)


@shots_module.route('/shots/browse/', defaults={'path': ''}, methods=['GET', 'POST'])
@shots_module.route('/shots/browse/<path:path>', methods=['GET', 'POST'])
def shots_browse(path):
    """We browse the production folder on the server.
    The path value gets appended to the active_show path value. The result is returned
    in JSON format.
    """

    show_id = request.form['show_id']
    #snapshot_id = request.form['snapshot_id']

    #snapshot = Snapshots.select().where(Snapshots.id == snapshot_id).get()

    #active_show = Settings.get(Settings.name == 'active_show')
    active_show = Shows.query.find({'_id' : ObjectId(show_id)}).first()

    # path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # render_settings_path = os.path.join(path, 'render_settings/')

    absolute_path_root = active_show.path_server
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
    shots_list = stringToList(shot_ids)
    for shot_id in shots_list:
        print("updating shot %s = %s " % (shot_id, status))
    return "TEMP done updating shots "


@shots_module.route('/shots/start', methods=['POST'])
def shots_start():
    shot_ids = request.form['id']
    shots_list = stringToList(shot_ids)
    for shot_id in shots_list:

        shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()
        if not shot:
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id

        if not shot:
            return 'Shot not found'

        if shot.status == 'running':
            pass
        elif shot.status in ['stopped', 'ready', 'completed']:
            update_query = Shots.query.update({'_id' : shot._id}, {'$set' : {'status' : 'running'}})
            #update_query.execute()
            session.flush()

        dispatch_frames()
        #if shot.job_type == 'render':
        #    dispatch_frames()
        #elif shot.job_type == 'bake':
        #    dispatch_bake_job()

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
    shots_list = stringToList(shot_ids)
    for shot_id in shots_list:
        print '[info] Working on shot', shot_id
        # first we delete the associated jobs (no foreign keys)
        try:
            shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()
        except Shots.DoesNotExist:
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id
        if not shot:
            return 'Shot not found'

        if not shot.status in ['stopped', 'error']:
            stop_jobs(shot._id)
            shot.status = 'stopped'
            session.flush()

    session.clear()
    return jsonify(
        shot_ids=shot_ids,
        status='stopped')


@shots_module.route('/shots/reset', methods=['POST'])
def shots_reset():
    shot_ids = request.form['id']
    shots_list = stringToList(shot_ids)

    shots_to_delete_frames = []
    for shot_id in shots_list:
        try:
            shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()
        except Shots.DoesNotExist:
            shot = None
            print('[error] Shot not found')
            return 'Shot %d not found' % shot_id

        if not shot:
            return 'Shot not found'

        if shot.status == 'running':
            return 'Shot %d is running' % shot_id
        else:
            shots_to_delete_frames.append(shot._id)


            """
            For some reason updateting frames here will not work. So we delete all frames for
            respective shot and then we will recreate them.
            """
            #Frames.query.update({'shot_id' : shot._id}, {'$set' : {'status' : 'ready'}})
            Frames.query.remove({'shot_id' : shot._id})

            # create frames entries
            for f in range(shot.frame_start, shot.frame_end + 1):
                fr = Frames()
                fr.frame=f
                fr.shot_id=shot._id
                fr.status='ready'

            #print(Frames.query.find({'shot_id' : shot._id}).count())

            shot.current_frame = shot.frame_start
            shot.status = 'ready'
            #shot.save()

            delete_jobs(shot._id)
            create_jobs(shot)

        session.flush()

    session.flush()
    session.clear()
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

    shot = Shots()
    shot.attract_shot_id=None
    shot.show_id=ObjectId(request.form['show_id'])
    shot.frame_start=int(request.form['frame_start'])
    shot.frame_end=int(request.form['frame_end'])
    shot.chunk_size=int(request.form['chunk_size'])
    shot.current_frame=int(request.form['frame_start'])
    shot.filepath=request.form['filepath']
    shot.shot_name=request.form['shot_name']
    shot.render_settings=request.form['render_settings']
    shot.status='ready'
    shot.priority=10
    shot.owner='fsiddi'
    shot.snapshot_id=snapshot_id
    shot.job_type=request.form['job_type']

    if shot.job_type == 'bake':
        shot.frame_start = 1
        shot.frame_end = 1

    #if shot.job_type ==  'render':
    # create frames entries
    for f in range(shot.frame_start, shot.frame_end + 1):
        fr = Frames()
        fr.frame=f
        fr.shot_id=shot._id
        fr.status='ready'

    print('parsing shot to create jobs')

    create_jobs(shot)

    print('refresh list of available workers')

    #dispatch_jobs(shot.id)

    #elif shot.job_type == 'bake':
    #    # don't create frames
    #    # don't create more than one job
    #    create_job(shot._id, 1, 1)

    #else:
    #    print('unknown job type %s' % shot.job_type)

    session.flush()
    session.clear()
    return 'done'


@shots_module.route('/shots/delete', methods=['POST'])
def shots_delete():
    shot_ids = request.form['id']
    shots_list = stringToList(shot_ids)
    for shot_id in shots_list:
        delete_query = Frames.query.remove({'shot_id' : ObjectId(shot_id)})
        #delete_query.execute()

        shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()

        print('working on', shot_id, '-', str(type(shot_id)))
        # first we delete the associated jobs (no foreign keys)
        delete_jobs(shot._id)
        # then we delete the shot
        delete_shot(shot._id)
    return 'done'
