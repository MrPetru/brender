import os

from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

# TODO(sergey): Generally not a good idea to import *
#from model import *
from utils import *
from modules.workers import *
from flask import current_app

from mingmodel import session, Frames, Settings, Shots, Workers, Shows
from bson import ObjectId

frames_module = Blueprint('frames_module', __name__)

def render_frames(worker, shot, frames):

    show = Shows.query.find({'_id' : shot.show_id}).first()
    #snapshot = Snapshots.get(Snapshots.id == shot.snapshot_id)

    filepath = shot.filepath

    if 'Darwin' in worker.system:
        setting_blender_path = Settings.query.find({'name' : 'blender_path_osx'}).first()
        setting_render_settings = Settings.query.find({'name' : 'render_settings_path_osx'}).first()

        repo_path = show.path_osx
        rev = shot.snapshot_id
        repo_type = show.repo_type

        filepath = os.path.join(show.path_osx, shot.filepath)
    else:
        setting_blender_path = Settings.query.find({'name' : 'blender_path_linux'}).first()
        setting_render_settings = Settings.query.find({'name' : 'render_settings_path_linux'}).first()

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
              'shot_id': shot._id.__str__(),
              'job_type' : shot.job_type}

    http_request(worker_ip_address, '/execute_job', params)
    #  get a reply from the worker (running, error, etc)

    return 'render started'

def shutdown(worker):
    worker_ip_address = worker.ip_address
    http_request(worker_ip_address, '/poweroff')
    return 'done'

def dispatch_frames():

    shots = Shots.query.find({'status' : 'running'}).sort('priority', 1).all()
    shot = None

    for s in shots:
        frames_count = Frames.query.find({'shot_id' : s._id, 'status' : 'ready'}).count()
        current_app.logger.debug("still frames to render = %d" % frames_count)
        if frames_count > 0:
            current_app.logger.debug("shot to render is %s" % s.shot_name)
            shot = s
            break
        else:
            current_app.logger.debug('save shot as completed')
            s.status = 'completed'

    for worker in Workers.query.find({'status' : 'enabled', 'connection' : 'online'}).all():
        if not shot:
            current_app.logger.debug("there is no more shots to render")

            if worker.poweroff == 'poweroff':
                shutdown(worker)
            return

        if worker.baking == True and shot.job_type != 'bake':
            continue

        print(shot.chunk_size)
        frame_list = Frames.query.find({'shot_id' : shot._id, 'status' : 'ready'}).sort('frame', 1).limit(shot.chunk_size).all()
        frames = []
        for f in frame_list:
            print(f.frame)
            f.status = 'running'
            f.worker_id = worker._id
            f.worker_hostname = worker.hostname
            frames.append(str(f.frame))

        # save modifications to database
        #for f in frame_list:
        #    f.save()


        print ('frame_list=', frame_list)

        if not frames:
            # print('no more frames to render for shot=%s' % shot.shot_name)
            # shot.status = 'completed'
            # shot.save()
            worker.status = 'enabled'
            #worker.save()
            current_app.logger.debug("no frames found to render, exit fron dispatch_frames")
            return
        else:
            worker.status = 'busy'
            #worker.save()
            current_app.logger.debug("send render job to worker")
            render_frames(worker, shot, frames)

        session.flush()

@frames_module.route('/frames/update/<shot_id>/<frame>', methods=['GET'])
@frames_module.route('/frames/update/<shot_id>', methods=['POST'])
def frames_update(shot_id, frame=None):
    if request.method == 'GET':
        current_app.logger.debug("report done single frame")
        shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()
        frame = int(frame)
        print(shot, shot._id, frame)
        frame = Frames.query.find({'shot_id' : shot._id, 'frame' : frame}).first()
        frame.duration = float(request.args.get('time'))
        paths = request.args.get('paths').encode()
        paths = paths[2:-2].split("', '")
        result_path = paths
        #result_path = []
        #for p in paths:
        #    index = p.find('Render')
        #    file_path = p[index:]
        #    result_path.append(file_path)

        frame.result_path = ','.join(result_path)
        frame.status = 'done'
        #frame.save()
        session.flush()
        return 'updated'
    elif request.method == 'POST':
        current_app.logger.debug("report done all frames")
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

        frames_list_query = Frames.query.find({'shot_id' : ObjectId(shot_id)}).all()
        frames_list = []
        for f in frames_list_query:
            if f.frame in frames:
                frames_list.append(f)
                print("frame is =", f.frame)

        Frames.query.update({'shot_id' : ObjectId(shot_id)}, {'$set' : {'status' : 'done'}})

        worker_id = frames_list[0].worker_id
        worker = Workers.query.find({'_id' : worker_id}).first()
        current_app.logger.debug("set worker status to enabled")
        worker.status = 'enabled'
        #worker.save()

        if int(retcode) != 0:
            print('there is some error returnet from worker')
            for f in frames_list:
                if f.status == 'running':
                    f.status = 'error'
            #for f in frames_list:
            #    f.save()
        else:
            print('no error were found, continuig with next frames')
            #shot = Shots.get(Shots.id == shot_id)
        current_app.logger.debug("dispatch remaining frames")
        session.flush()
        session.clear()
        dispatch_frames()

    current_app.logger.debug("exit from frames/update")
    return 'done'

@frames_module.route('/frames/<shot_id>')
def frames_index(shot_id):
    shot = Shots.query.find({'_id' : ObjectId(shot_id)}).first()
    show = Shows.query.find({'_id' : shot.show_id}).first()
    frames = {}
    for frame in Frames.query.find({'shot_id' : shot._id}).all():
        paths = [p for p in frame.result_path.split(',')]
        frames[frame._id.__str__()] = {
            "frame": frame.frame,
            "status": frame.status,
            "duration": "%.3fs" % (frame.duration or 0),
            "worker": frame.worker_hostname,
            "paths": paths,
            "shot_name": shot.shot_name,
            "show_id": shot.show_id.__str__(),
            "project_name": show.name
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
            frame = Frames.query.find({'_id' : ObjectId(fid)}).first()
            frame.status = 'ready'
            #frame.save()
    elif command == 'reset_failed':
        update_query = Frames.query.update({'shot_id' : ObjectId(shot_id), 'status' : 'error'}, {'$set' : {'status' : 'ready'}})
        #update_query.execute()

    session.flush()

    return 'done'
