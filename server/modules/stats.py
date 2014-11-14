import json

from flask import Blueprint, render_template, abort, jsonify, request

#from model import *
from utils import *

from mingmodel import Jobs, Shots, Shows

stats_module = Blueprint('stats_module', __name__)


@stats_module.route('/stats/')
def stats():
    # Here we will aget some basic statistics and infos from the server.
    stats = {
            "total_jobs":Jobs.query.find({}).count(),
            "total_shots":Shots.query.find({}).count(),
            "total_shows":Shows.query.find({}).count(),
            }

    #b = Jobs.select().count()


    return jsonify(server_stats=stats)
