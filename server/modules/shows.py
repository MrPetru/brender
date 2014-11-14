import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

#from model import *
from utils import *

from mingmodel import session, Shows, Shots, Frames
from bson import ObjectId

shows_module = Blueprint('shows_module', __name__)


@shows_module.route('/shows/')
def shows():
    # Here we will add a check to see if we shoud get shows from the
    # local database or if we should query attract for them
    shows = {}
    for show in Shows.query.find({}).all():
        shows[show._id.__str__()] = dict(
            id=show._id.__str__(),
            name=show.name,
            path_server=show.path_server,
            path_linux=show.path_linux,
            path_osx=show.path_osx,
            repo_type=show.repo_type,
            repo_update_cmd=show.repo_update_cmd,
            repo_checkout_cmd=show.repo_checkout_cmd)

    return jsonify(shows)


@shows_module.route('/shows/<show_id>')
def get_show(show_id):
    try:
        show = Shows.query.find({'_id' : ObjectId(show_id)}).first()
        print('[Debug] Get show %s') % (show._id.__str__())
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

    show = Shows()
    show.name=request.form['name']
    show.path_server=path_server
    show.path_linux=path_linux
    show.path_osx=path_osx
    show.repo_type=repo_type
    show.repo_update_cmd=repo_update_cmd
    show.repo_checkout_cmd=repo_checkout_cmd

    session.flush()

    return 'done'


@shows_module.route('/shows/delete/<show_id>', methods=['GET', 'POST'])
def shows_delete(show_id):
    shots_show = Shots.query.find({'_id' : ObjectId(show_id)}).first()
    for shot_show in shots_show:
        print '[Debug] Deleting shot (%s) for show %s ' % (shot_show.shot_name, shot_show.show_id.__str__())
        jobs = Jobs.query.find({'shot_id' : shot_show._id}).all()
        for j in jobs:
            j.delete()
        shot_show.delete()

    show = Shows.query.remove({'_id' : ObjectId(show_id)})

    session.flush()
    #if show:
    #  show.delete_instance()
    return 'done'


@shows_module.route('/shows/update', methods=['POST'])
def shows_update():

    try:
        show = Shows.query.find({'_id' : ObjectId(request.form['show_id'])})
    except Shows.DoesNotExist:
        print '[Error] Show not found'
        return 'Show %d not found' % show_id

    if not show:
        return "Show not found"

    show.path_server=request.form['path_server']
    show.path_linux=request.form['path_linux']
    show.path_osx=request.form['path_osx']

    #repo_type = request.form['repo_type']
    show.repo_update_cmd=request.form['repo_update_cmd']
    show.repo_checkout_cmd=request.form['repo_checkout_cmd']

    #show.save()
    session.flush()
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
