
# ============== start dender configutation and render process ===========


import bpy
import sys
import argparse
import time
from urllib import request
from urllib.parse import urlencode
import os

bpy.context.user_preferences.system.compute_device_type = 'CUDA'
bpy.context.user_preferences.system.compute_device = 'CUDA_0'

# parse list of frames from command line arguments
argv = sys.argv
argv = argv[argv.index("--") + 1:]
parser = argparse.ArgumentParser(description="read arguments passed from brender")

parser.add_argument('-f', '--frames', type=str)
parser.add_argument('-sh', '--shot', type=int)
parser.add_argument('-s', '--server', type=str)
args = parser.parse_args(argv)


def expand_padding(formated):
    if formated[-1] == '.':
        formated = formated[:-1]
        
    last_index = formated.rfind('#')
    if last_index < 0:
        formated += "%04d"
        return formated
    
    pad = '#'
    while formated[last_index - 1] == '#':
        pad += '#'
        last_index -= 1
    
    formated = formated.replace(pad, "%%0%dd" % (len(pad)))
    return formated

def output_frame_path(frame=None):
    
    format_to_ext = {
        'JPEG': 'jpg',
        'BMP': 'bmp',
        'IRIS': 'rgb',
        'PNG': 'png',
        'TARGA': 'tga',
        'TARGA_RAW': 'tga',
        'CINEON': 'cin',
        'DPX': 'dpx',
        'OPEN_EXR_MULTILAYER': 'exr',
        'OPEN_EXR': 'exr',
        'HDR': 'hdr',
        'TIFF': 'tif'
    }
    
    if not frame:
        frame = bpy.context.scene.frame_current
        
    paths = []
    if hasattr(bpy.context.scene, 'node_tree') and bpy.context.scene.node_tree:
        for n in bpy.context.scene.node_tree.nodes:
            if n.type == 'OUTPUT_FILE':
                for s in n.file_slots:
                    fileNameExpanded = expand_padding(s.path)
                    ext = format_to_ext[s.format.file_format]
                    
                    fileName = "%s.%s" % (fileNameExpanded, ext)
                    paths.append(os.path.join(n.base_path, fileName % frame))
            
    return paths

def update_frame(server, shot, frame, timed):
    paths = output_frame_path(frame)
    paths.append(bpy.context.scene.render.frame_path(frame))
    print(paths)
    command = 'frames/update/%s/%s' % (shot, frame)
    params = urlencode({'time':timed, 'paths':paths})
    request.urlopen(server + '/' + command + '?' + params).read()

def main():

    frames = args.frames
    flist = frames.split(' ')
    frames = []
    for f in flist:
        frames.append(int(f))

    shot = args.shot
    server = args.server
    for f in frames:
        bpy.context.scene.frame_start = f
        bpy.context.scene.frame_end = f
        start_time = time.time()
        bpy.ops.render.render(animation=True)
        timed = time.time() - start_time
        update_frame(server, shot, f, timed)


    # send resutl tu the server
main()
# =============== end brender default configuration =====================