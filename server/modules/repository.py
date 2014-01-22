import os

from flask import abort, Blueprint, jsonify, render_template, request
from flask import current_app

# TODO(sergey): Generally not a good idea to import *
from model import *
from utils import *
from workers import *
import time
import subprocess

repo_module = Blueprint('repo_module', __name__)

@repo_module.route('/repo/')
def repo():
    return 'done'

@repo_module.route('/repo/checkout/<show_id>/<rev>')
def repo_checkout(show_id, rev):
    if not show_id or not rev:
        return 'version checkout with errors'

    show = Shows.get(Shows.id == show_id)
    path = show.path_server
    if show.repo_type == 'mercurial':
        from mercurial import ui, hg, commands
        from mercurial.error import RepoError, RepoLookupError
        try:
            repo = hg.repository(ui.ui(), path)
            commands.update(ui.ui(), repo, rev=rev)
        except (RepoError, RepoLookupError):
            print(RepoError)
            return 'cannot switch revision'
        return 'checkouted version %s' % rev

    else:
        return 'cannot handle repository of type %s' % show.repo_type

@repo_module.route('/repo/revisions/<show_id>')
def repo_revisions(show_id):
    print(show_id)
    if not show_id:
        return 'no show id were provided'
        
    if request.method == 'GET':
        show = Shows.get(Shows.id == show_id)
        path = show.path_server

        if show.repo_type == 'mercurial':
            from mercurial import ui, hg, commands
            from mercurial.error import RepoError
            try:
                repo = hg.repository(ui.ui(), path)
            except RepoError:
                print(RepoError)
                return jsonify({'revisions':[],'message': 'cannot open interface to repository (is the path correct)'})

            revisions = []
            for rev in repo:
                d = {'rev':rev, 'description':repo[rev].description()}
                revisions.append(d)
            revisions.reverse()
            return jsonify({'revisions':revisions, 'message':''})

        else:
            return 'cannot handle repository of type %s' % show.repo_type

    elif request.method == 'POST':
        return jsonify({'revisions':[]})
    else:
        return 'unknown request method %s' % request.method