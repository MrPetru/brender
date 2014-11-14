
# get all needed imports
from ming import Session
from ming import create_datastore
from ming.odm import FieldProperty
from ming import schema as s
from ming.odm import Mapper
from ming.odm.declarative import MappedClass
from ming.odm import ThreadLocalODMSession
from datetime import datetime
import bson

# create database connection
bind = create_datastore('mongodb://brenderuser:brendertmppassword@localhost:27017/brender')
doc_session = Session(bind)
session = ThreadLocalODMSession(doc_session=doc_session)

def getJson(obj):
    r = dict()
    properties = mapper(obj).properties
    for p in properties:

        # format date and time
        if p.name == '_id':
            r[p.name] = self.__getattribute__(p.name).__str__()
            continue

        r[p.name] = obj.__getattribute__(p.name)

    return r


# define models

# models:
    # Worker
class Workers(MappedClass):

    class __mongometa__:
        session = session
        name = 'workers'

    def __init__(self, hostname, ip_address, mac_address, system):
        self.hostname = hostname
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.system = system

    _id = FieldProperty(s.ObjectId)
    mac_address = FieldProperty(s.String)
    hostname = FieldProperty(s.String)
    status = FieldProperty(s.String, if_missing='enabled')
    warning = FieldProperty(s.Bool, if_missing=False)
    config = FieldProperty(s.String, if_missing='{}')
    system = FieldProperty(s.String)
    ip_address = FieldProperty(s.String)
    connection = FieldProperty(s.String, if_missing='online')
    poweroff = FieldProperty(s.String, if_missing='')
    baking = FieldProperty(s.Bool, if_missing=False)

    @classmethod
    def getAll(cls):
        return cls.query.find({}).all()

    @classmethod
    def deleteAll(cls, ids):
        if not len(ids):
            return False

        id_list = []
        if isinstance(ids[0], str):
            for i in ids:
                id_list.append(bson.ObjectId(i))
        else:
            id_list = ids

        cls.query.remove({'_id' : {'$in' : ids}})
        return True

    @classmethod
    def updateById(cls, ids, newdata):
        if not isinstance(ids, list):
            ids = [ids]

        id_list = []
        if isinstance(ids[0], str) or isinstance(ids[0], unicode):
            for i in ids:
                id_list.append(bson.ObjectId(i))
        else:
            id_list = ids

        print(id_list)

        cls.query.update({'_id' : {'$in' : id_list}, 'status' : {'$ne': 'offline'}}, {'$set' : newdata})

    @classmethod
    def updateAll(cls, newdata):
        cls.query.find_and_modify({'status' : {'$not' : 'offline'}}, newdata)


    #def __json__(self):

    #    r = dict()
    #    properties = mapper(self).properties
    #    for p in properties:

    #        # format date and time
    #        if p.name == '_id':
    #            r[p.name] = self.__getattribute__(p.name).__str__()
    #            continue

    #        r[p.name] = self.__getattribute__(p.name)

    #    return r


class Frames(MappedClass):

    class __mongometa__:
        session = session
        name = 'frames'

    _id = FieldProperty(s.ObjectId)
    frame = FieldProperty(s.Int)
    shot_id =  FieldProperty(s.ObjectId)
    status = FieldProperty(s.String)
    worker_id = FieldProperty(s.ObjectId, if_missing=None)
    worker_hostname = FieldProperty(s.String, if_missing='')
    result_path = FieldProperty(s.String, if_missing='')
    duration = FieldProperty(s.Float, if_missing=None)

    #def __json__(self):

    #    return {'name': 'petru'}

    #    # ip -> where to find it
    #    # status -> waiting, working
    #    # config -> node specific configurations
    #    # hostname -> human redable name

class Shows(MappedClass):

    class __mongometa__:
        session = session
        name = 'Shows'

    _id = FieldProperty(s.ObjectId)
    name = FieldProperty(s.String)
    path_server = FieldProperty(s.String)
    path_linux = FieldProperty(s.String)
    path_osx = FieldProperty(s.String)
    repo_type = FieldProperty(s.String)
    repo_update_cmd = FieldProperty(s.String)
    repo_checkout_cmd = FieldProperty(s.String)


class Shots(MappedClass):

    class __mongometa__:
        session = session
        name = 'Shots'

    _id = FieldProperty(s.ObjectId)
    attract_shot_id = FieldProperty(s.ObjectId, if_missing=None)
    show_id = FieldProperty(s.ObjectId)
    frame_start = FieldProperty(s.Int)
    frame_end = FieldProperty(s.Int)
    chunk_size = FieldProperty(s.Int)
    current_frame = FieldProperty(s.Int)
    shot_name = FieldProperty(s.String)
    filepath = FieldProperty(s.String)
    render_settings = FieldProperty(s.String)
    status = FieldProperty(s.String)
    priority = FieldProperty(s.Int)
    owner = FieldProperty(s.String)
    snapshot_id = FieldProperty(s.String)

    job_type = FieldProperty(s.String, if_missing='render')


class Jobs(MappedClass):


    class __mongometa__:
        session = session
        name = 'Jobs'

    #shot = ForeignKeyField(Shots, related_name='fk_shot')
    #worker = ForeignKeyField(Workers, related_name='fk_worker')
    _id = FieldProperty(s.ObjectId)
    shot_id = FieldProperty(s.ObjectId)
    worker_id = FieldProperty(s.ObjectId)
    chunk_start = FieldProperty(s.Int)
    chunk_end = FieldProperty(s.Int)
    current_frame = FieldProperty(s.Int)
    status = FieldProperty(s.String)
    priority = FieldProperty(s.Int)


class Settings(MappedClass):

    class __mongometa__:
        session = session
        name = 'Settings'

    _id = FieldProperty(s.ObjectId)
    name = FieldProperty(s.String)
    value = FieldProperty(s.String)

    # Project
    # Shot
    # Job
    # Settings
    # Frame

# compile models
Mapper.compile_all()
