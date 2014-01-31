import os

from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

# TODO(sergey): Generally not a good idea to import *
from model import *
from utils import *
from modules.workers import *

frames_module = Blueprint('frames_module', __name__)

def render_frames(worker, shot, frames):

    show = Shows.get(Shows.id == shot.show_id)
    #snapshot = Snapshots.get(Snapshots.id == shot.snapshot_id)

    filepath = shot.filepath

    if 'Darwin' in worker.system:
        setting_blender_path = Settings.get(
            Settings.name == 'blender_path_osx')
        setting_render_settings = Settings.get(
            Settings.name == 'render_settings_path_osx')

        repo_path = show.path_osx
        rev = shot.snapshot_id
        repo_type = show.repo_type

        filepath = os.path.join(show.path_osx, shot.filepath)
    else:
        setting_blender_path = Settings.get(
            Settings.name == 'blender_path_linux')
        setting_render_settings = Settings.get(
            Settings.name == 'render_settings_path_linux')

        repo_path = show.path_linux
        rev = shot.snapshot_id
        repo_type = show.repo_type

        filepath = os.path.join(show.path_linux, shot.filepath)

    blender_path = setting_blender_path.value
    render_settings = shot.render_settings

    worker_ip_address = worker.ip_address

    params = {'file_path': filepath,
              'blender_path': blender_path,
              'render_settings': render_settings,
              'frames': ' '.join(frames),
              'repo_path': repo_path,
              'server_repo_path': show.path_server, 
              'rev': rev,
              'repo_type': repo_type,
              'shot_id': shot.id}

    http_request(worker_ip_address, '/execute_job', params)
    #  get a reply from the worker (running, error, etc)

    return 'render started'

def shutdown(worker):
    worker_ip_address = worker.ip_address
    http_request(worker_ip_address, '/poweroff')
    return 'done'

def dispatch_frames():

    shots = Shots.select().where(Shots.status == 'running').order_by(Shots.priority)
    shot = None

    for s in shots:
        frames_count = Frames.select().where(Frames.status == 'ready').count()
        print("still frames to render = ", frames_count)
        if frames_count > 0:
            shot = s
            break
            
    if not shot:
        print("I don't know which of shot to run, please select one")
        return

    for worker in Workers.select().where((Workers.status == 'enabled') & (Workers.connection == 'online')):

        frames_to_render = Frames.select().where((Frames.shot_id == shot.id) & (Frames.status == 'ready')).limit(shot.chunk_size)
        #frames_to_render = q.execute()
        print(shot.chunk_size)
        #print(frames_to_render.count())
        frame_list = []
        for f in frames_to_render:
            print(f.frame)
            f.status = 'running'
            f.worker_id = worker.id
            f.worker_hostname = worker.hostname
            frame_list.append(str(f.frame))
        
        # save modifications to database
        for f in frames_to_render:
            f.save()

        print ('frame_list=', frame_list)

        if not frame_list:
            print('no more frames to render for shot=%s' % shot.shot_name)
            shot.status = 'complete'
            shot.save()
            if worker.poweroff == 'poweroff':
                shutdown(worker)
            return
        else:
            worker.status = 'busy'
            worker.save()
            render_frames(worker, shot, frame_list)

@frames_module.route('/frames/update/<shot_id>/<frame>', methods=['GET'])
@frames_module.route('/frames/update/<shot_id>', methods=['POST'])
def frames_update(shot_id, frame=None):
    if request.method == 'GET':
        shot = Shots.get(Shots.id == shot_id)
        frame = Frames.get((Frames.shot_id == shot_id) & (Frames.frame == frame))
        frame.duration = request.args.get('time')
        paths = request.args.get('paths').encode()
        paths = paths[2:-2].split("', '")
        result_path = []
        for p in paths:
            index = p.find('Render')
            file_path = p[index:]
            result_path.append(file_path)

        frame.result_path = ','.join(result_path)
        frame.status = 'done'
        frame.save()
        return 'updated'
    elif request.method == 'POST':
        frames = request.form['frames']
        flist = frames.split(' ')
        frames = []
        for f in flist:
            frames.append(int(f))

        status = request.form['status']
        full_output = request.form['full_output']
        retcode = request.form['retcode']
        print(frames, shot_id)
        print('retcode = ', retcode, 'type of retcode=', type(retcode))

        frames_list = Frames.select().where((Frames.shot_id == shot_id) & (Frames.frame in frames))
        worker_id = frames_list[0].worker_id
        worker = Workers.get(Workers.id == worker_id)
        worker.status = 'enabled'
        worker.save()

        if int(retcode) != 0:
            print('there is some error returnet from worker')
            for f in frames_list:
                if f.status == 'running':
                    f.status = 'error'
            for f in frames_list:
                f.save()
        else:
            print('no error were found, continuig with next frames')
            #shot = Shots.get(Shots.id == shot_id)
        
        dispatch_frames()
    return 'done'

@frames_module.route('/frames/<shot_id>')
def frames_index(shot_id):
    shot = Shots.get(Shots.id == shot_id)

    frames = {}
    for frame in Frames.select().where(Frames.shot_id == shot_id):
        paths = [p for p in frame.result_path.split(',')]
        frames[frame.id] = {
            "frame": frame.frame,
            "status": frame.status,
            "duration": "%.3fs" % (frame.duration or 0),
            "worker": frame.worker_hostname,
            "paths": paths,
            "show_id": shot.show_id
        }

    return jsonify(frames)

@frames_module.route('/frames/reset/<shot_id>', methods=['POST'])
def frames_reset(shot_id):
    frames_id = request.form['id']
    command = request.form['command']
    if command == 'reset':
        frames_id = frames_id.split(',')
        for fid in frames_id:
            print(fid)
            frame = Frames.get(Frames.id == fid)
            frame.status = 'ready'
            frame.save()
    elif command == 'reset_failed':
        frames = Frames.select().where((Frames.shot_id == shot_id) & (Frames.status == 'error'))
        for f in frames:
            f.status = 'ready'
            f.save()

    return 'done'