import json

import os
from os import listdir
from os.path import isfile, join, abspath, dirname
from flask import Blueprint, render_template, abort, jsonify, request

#from model import *
from utils import *

from mingmodel import session, Workers, Frames, Settings, getJson

settings_module = Blueprint('settings_module', __name__)


@settings_module.route('/settings/')
def settings():
    settings = {}
    for setting in Settings.query.find({}).all():
        settings[setting.name] = setting.value

    #return jsonify(getJson(settings))
    return jsonify(settings)


@settings_module.route('/settings/update', methods=['POST'])
def settings_update():
    for setting_name in request.form:

        setting = Settings.query.find({'name' :  setting_name}).first()
        if setting:
            setting.value = request.form[setting_name]
            #setting.save()
            print('[Debug] Updating %s %s') % \
            (setting_name, request.form[setting_name])
        else:
            setting = Settings()
            setting.name=setting_name
            setting.value=request.form[setting_name]
            #setting.save()
            print('[Debug] Creating %s %s') % \
            (setting_name, request.form[setting_name])

        session.flush()
    return 'done'



@settings_module.route('/settings/<setting_name>')
def get_setting(setting_name):
    try:
        setting = Settings.query.find({'name' : setting_name}).first()
        print('[Debug] Get Settings %s %s') % (setting.name, setting.value)
    except Exception, e:
        print(e, '--> Setting not found')
        return 'Setting %s not found' % setting_name

    # a = json.loads(setting['value'])
    # print(a)

    return setting.value


@settings_module.route('/render-settings/')
def render_settings():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/')
    onlyfiles = [f for f in listdir(render_settings_path) if isfile(join(render_settings_path, f))]
    #return str(onlyfiles)
    settings_files = dict(
        settings_files=onlyfiles)

    return jsonify(settings_files)

@settings_module.route('/render-settings/<sname>', methods=['GET', 'POST'])
def render_settings_edit(sname):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    render_settings_path = os.path.join(path, 'render_settings/', sname)
    if not os.path.exists(render_settings_path):
        return jsonify(dict(text="file were not fonud"))
    if not os.path.isfile(render_settings_path):
        return jsonify(dict(text="file were not fonud"))

    if request.method == 'GET':
        f = open(render_settings_path, 'r')
        text = f.read()
        f.close()
        return jsonify(dict(text=text))
    elif request.method == 'POST':
        content = request.form['content']
        f = open(render_settings_path, 'w')
        f.write(content)
        f.close()
        return 'done'
