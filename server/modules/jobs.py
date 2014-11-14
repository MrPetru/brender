import os

from flask import (abort,
                   Blueprint,
                   jsonify,
                   render_template,
                   request)

# TODO(sergey): Generally not a good idea to import *
#from model import *
from utils import *
from workers import *
from mingmodel import session, Jobs, Shots, Shows

jobs_module = Blueprint('jobs_module', __name__)


def create_job(shot_id, chunk_start, chunk_end):
    job = Jobs()
    job.shot_id=shot_id
    job.worker_id=None
    job.chunk_start=chunk_start
    job.chunk_end=chunk_end
    job.current_frame=chunk_start
    job.status='ready'
    job.priority=50

    session.flush()
    session.clear()


def create_jobs(shot):
    shot_frames_count = shot.frame_end - shot.frame_start + 1
    shot_chunks_remainder = shot_frames_count % shot.chunk_size
    shot_chunks_division = shot_frames_count / shot.chunk_size

    if shot_chunks_remainder == 0:
        print('we have exact chunks')

        total_chunks = shot_chunks_division
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks):
            print('making chunk for shot', shot._id)

            create_job(shot._id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

    elif shot_chunks_remainder == shot.chunk_size:
        print('we have 1 chunk only')

        create_job(shot._id, shot.frame_start, shot.frame_end)

    #elif shot_chunks_remainder > 0 and \
    #     shot_chunks_remainder < shot.chunk_size:
    else:
        print('shot_chunks_remainder', shot_chunks_remainder)
        print('shot_frames_count', shot_frames_count)
        print('shot_chunks_division', shot_chunks_division)

        total_chunks = shot_chunks_division + 1
        chunk_start = shot.frame_start
        chunk_end = shot.frame_start + shot.chunk_size - 1

        for chunk in range(total_chunks - 1):
            print('making chunk for shot', shot._id)

            create_job(shot._id, chunk_start, chunk_end)

            chunk_start = chunk_end + 1
            chunk_end = chunk_start + shot.chunk_size - 1

        chunk_end = chunk_start + shot_chunks_remainder - 1
        create_job(shot._id, chunk_start, chunk_end)

    session.flush()


def start_job(worker, job):
    """Execute a single job
    We pass worker and job as objects (and at the moment we use a bad
    way to get the additional shot information - should be done with join)
    """

    shot = Shots.query.find({'_id' : job.shot_id}).first()
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

    """
    Additional params for future reference

    job_parameters = {'pre-run': 'svn up or other things',
                      'command': 'blender_path -b ' +
                                 '/filepath.blend -o /render_out -a',
                      'post-frame': 'post frame',
                      'post-run': 'clear variables, empty /tmp'}
    """

    params = {'job_id': job._id.__str__(),
              'file_path': filepath,
              'blender_path': blender_path,
              'render_settings': render_settings,
              'start': job.chunk_start,
              'end': job.chunk_end,
              'repo_path': repo_path,
              'server_repo_path': show.path_server,
              'rev': rev,
              'repo_type': repo_type}

    http_request(worker_ip_address, '/execute_job', params)
    #  get a reply from the worker (running, error, etc)

    job.status = 'running'
    #job.save()

    shot.current_frame = job.chunk_end
    #shot.save()
    session.flush()

    return 'Job started'

# def shutdown(worker):
#     worker_ip_address = worker.ip_address
#     http_request(worker_ip_address, '/poweroff')
#     return 'done'

# def render_frames(worker, shot, frames):

#     show = Shows.get(Shows.id == shot.show_id)
#     #snapshot = Snapshots.get(Snapshots.id == shot.snapshot_id)

#     filepath = shot.filepath

#     if 'Darwin' in worker.system:
#         setting_blender_path = Settings.get(
#             Settings.name == 'blender_path_osx')
#         setting_render_settings = Settings.get(
#             Settings.name == 'render_settings_path_osx')

#         repo_path = show.path_osx
#         rev = shot.snapshot_id
#         repo_type = show.repo_type

#         filepath = os.path.join(show.path_osx, shot.filepath)
#     else:
#         setting_blender_path = Settings.get(
#             Settings.name == 'blender_path_linux')
#         setting_render_settings = Settings.get(
#             Settings.name == 'render_settings_path_linux')

#         repo_path = show.path_linux
#         rev = shot.snapshot_id
#         repo_type = show.repo_type

#         filepath = os.path.join(show.path_linux, shot.filepath)

#     blender_path = setting_blender_path.value
#     render_settings = shot.render_settings

#     worker_ip_address = worker.ip_address

#     params = {'file_path': filepath,
#               'blender_path': blender_path,
#               'render_settings': render_settings,
#               'frames': ' '.join(frames),
#               'repo_path': repo_path,
#               'server_repo_path': show.path_server,
#               'rev': rev,
#               'repo_type': repo_type,
#               'shot_id': shot.id}

#     http_request(worker_ip_address, '/execute_job', params)
#     #  get a reply from the worker (running, error, etc)

#     return 'render started'

def dispatch_jobs(shot = None):
    if not shot:
        print("I don't know which of shot to run, please select one")
        return
    for worker in Workers.query.find({'status' : 'enabled', 'connection' : 'online'}).all():

        frames_to_render = Frames.query.find({'shot_id' : shot._id, 'status' : 'ready'}).limit(shot.chunk_size).all()
        #frames_to_render = q.execute()
        print(shot.chunk_size)
        #print(frames_to_render.count())
        frame_list = []
        for f in frames_to_render:
            print(f.frame)
            f.status = 'running'
            f.worker_id = worker._id
            frame_list.append(str(f.frame))

        # save modifications to database
        #for f in frames_to_render:
        #    f.save()

        print ('frame_list=', frame_list)

        if not frame_list:
            print('no more frames to render for shot=%s' % shot.shot_name)
            if worker.poweroff == 'poweroff':
                shutdown(worker)
            return
        else:
            render_frames(worker, shot, frame_list)

        #session.flush()

        # # pick the job with the highest priority (it means the lowest number)
        # job = None # will figure out another way
        # try:
        #     job = Jobs.select().where(
        #         Jobs.status == 'ready'
        #     ).order_by(Jobs.priority.desc()).limit(1).get()

        #     job.status = 'running'
        #     job.save()
        # except Jobs.DoesNotExist:
        #     # no more jobs, we can poweroff worker machine
        #         # check if worker should go down
        #         # send poweroff command
        #     if worker.poweroff == 'poweroff':
        #         shutdown(worker)
        #     print '[error] Job does not exist'
        # if job:
        #     start_job(worker, job)


def delete_job(job_id):
    # At the moment this function is not used anywhere
    try:
        job = Jobs.query.find({'_id' : job_id}).first()
    except Exception, e:
        print(e)
        return 'error'
    job.delete()
    print('Deleted job', job_id)
    #session.flush()


def delete_jobs(shot_id):
    delete_query = Jobs.query.remove({'shot_id' : shot_id})
    #delete_query.execute()
    print('All jobs deleted for shot', shot_id)


def start_jobs(shot_id):
    """
    [DEPRECATED] We start all the jobs for a specific shot
    """
    for job in Jobs.query.find({'shot_id' : shot_id, 'status' : 'ready'}).all():
        print(start_job(job._id))


def stop_job(job_id):
    """
    Stop a single job
    """
    job = Jobs.query.find({'_id' : job_id}).first()
    job.status = 'ready'
    #job.save()

    session.flush()
    return 'Job stopped'


def stop_jobs(shot_id):
    """
    We stop all the jobs for a specific shot
    """
    for job in Jobs.query.find({'shot_id' : shot_id, 'status' : 'running'}).all():
        print(stop_job(job._id))


@jobs_module.route('/jobs/')
def jobs():
    from decimal import Decimal
    jobs = {}
    percentage_done = 0
    for job in Jobs.query.find({}).all():

        shot = Shots.query.find({'_id' : job.shot_id}).first()
        show = Shows.query.find({'_id' : shot.show_id}).first()

        parent = "%s/%s" % (show.name, shot.shot_name)

        frame_count = job.chunk_end - job.chunk_start + 1
        current_frame = job.current_frame - job.chunk_start + 1
        percentage_done = Decimal(current_frame) / Decimal(frame_count) * Decimal(100)
        percentage_done = round(percentage_done, 1)
        jobs[job._id.__str__()] = {"shot_id": job.shot_id.__str__(),
                        "chunk_start": job.chunk_start,
                        "chunk_end": job.chunk_end,
                        "current_frame": job.current_frame,
                        "status": job.status,
                        "percentage_done": percentage_done,
                        "priority": job.priority,
                        "parent": parent}
    return jsonify(jobs)


@jobs_module.route('/jobs/update', methods=['POST'])
def jobs_update():
    job_id = request.form['id']
    status = request.form['status'].lower()

    job = Jobs.query.find({'_id' : ObjectId(job_id)}).first()
    shot = Shots.query.find({'_id' : job.shot_id}).first()

    full_output = request.form['full_output']
    retcode = request.form['retcode']
    source_worker = request.remote_addr
    with open('log_%s_%s.log' % (shot.shot_name, source_worker), 'a') as f:
        f.write("="*80+'\n')
        f.write("worker ip is %s\n" % source_worker)
        f.write("-"*80+'\n')
        f.write("return code is %s\n" % retcode)
        f.write("following complete log\n")
        f.write(full_output)
        f.close()

    if status in ['finished']:
        job.status = 'finished'
        #job.save()
        if job.chunk_end == shot.frame_end:
            shot.status = 'completed'
            # this can be added when we update the shot for every
            # frame rendered
            # if job.current_frame == shot.frame_end:
            #     shot.status = 'finished'
            #shot.save()
    elif status in ['error']:
        shot.status = 'error'
        #shot.save()
        job.status = 'error'
        #job.save()
    else:
        print('receiveed status is %s' % status)

    session.flush()
    dispatch_jobs()

    return "job updated"
