import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

from model import *
from utils import *

shows_module = Blueprint('shows_module', __name__)


@shows_module.route('/shows/')
def shows():
    # Here we will add a check to see if we shoud get shows from the
    # local database or if we should query attract for them
    shows = {}
    for show in Shows.select():
        try:
            snapshot = Snapshots.select().where(Snapshots.show_id == show.id).order_by(Snapshots.name.desc()).limit(1).get()
        except Snapshots.DoesNotExist:
            snapshot = Snapshots()
            snapshot.name = 'None'
            snapshot.comment = 'None'

        shows[show.id] = dict(
            id=show.id,
            name=show.name,
            path_server=show.path_server,
            path_linux=show.path_linux,
            path_osx=show.path_osx,
            repo_type=show.repo_type,
            repo_update_cmd=show.repo_update_cmd,
            repo_checkout_cmd=show.repo_checkout_cmd,
            snapshot=dict(name=snapshot.name, comment=snapshot.comment))
    
    return jsonify(shows)


@shows_module.route('/shows/<int:show_id>')
def get_show(show_id):
    try:
        show = Shows.get(Shows.id == show_id)
        print('[Debug] Get show %d') % (show.id)
    except Shows.DoesNotExist:
        print '[Error] Show not found'
        return 'Show %d not found' % show_id

    return jsonify(
        name=show.name,
        path_server=show.path_server,
        path_linux=show.path_linux,
        path_osx=show.path_osx,
        repo_type=show.repo_type,
        repo_update_cmd=show.repo_update_cmd,
        repo_checkout_cmd=show.repo_checkout_cmd)


@shows_module.route('/shows/add', methods=['POST'])
def show_add():
    path_linux = request.form['path_linux']
    path_osx = request.form['path_osx']
    path_server = request.form['path_server']

    repo_type = request.form['repo_type']
    repo_update_cmd = request.form['repo_update_cmd']
    repo_checkout_cmd = request.form['repo_checkout_cmd']

    show = Shows.create(
        name=request.form['name'],
        path_server=path_server,
        path_linux=path_linux,
        path_osx=path_osx,
        repo_type=repo_type,
        repo_update_cmd=repo_update_cmd,
        repo_checkout_cmd=repo_checkout_cmd)

    return 'done'


@shows_module.route('/shows/delete/<int:show_id>', methods=['GET', 'POST'])
def shows_delete(show_id):
    shots_show = Shots.select().where(Shots.show_id == show_id)
    for shot_show in shots_show:
        print '[Debug] Deleting shot (%s) for show %s ' % (shot_show.shot_name, shot_show.show_id)
        jobs = Jobs.select().where(Jobs.shot_id == shot_show.id)
        for j in jobs:
            j.delete_instance()
        shot_show.delete_instance()

    show = Shows.get(Shows.id == show_id)
    if show:
      show.delete_instance()
    return 'done'


@shows_module.route('/shows/update', methods=['POST'])
def shows_update():

    try:
        show = Shows.get(Shows.id == request.form['show_id'])
    except Shows.DoesNotExist:
        print '[Error] Show not found'
        return 'Show %d not found' % show_id

    show.path_server=request.form['path_server']
    show.path_linux=request.form['path_linux']
    show.path_osx=request.form['path_osx']

    #repo_type = request.form['repo_type']
    show.repo_update_cmd=request.form['repo_update_cmd']
    show.repo_checkout_cmd=request.form['repo_checkout_cmd']

    show.save()
    return 'done'


@shows_module.route('/render-shows/')
def render_shows():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_shows_path = os.path.join(path, 'render_shows/')
    onlyfiles = [f for f in listdir(render_shows_path) if isfile(join(render_shows_path, f))]
    #return str(onlyfiles)
    shows_files = dict(
        shows_files=onlyfiles)

    return jsonify(shows_files)
