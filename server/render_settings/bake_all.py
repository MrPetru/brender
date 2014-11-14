import bpy

"""
    Use this script to start smoke bake process from terminal.

    Like this:
        blender -b scenefile.blend --python runBake.py
"""


# ?? Should we bake domain by domain or all together
# if we hit bake on one smoke domain then all other domains will start bake process too
# so we will go faster way and will use bake all operation

# should we free bake before we star new one?
bpy.ops.ptcache.free_bake_all()

try:
    bpy.ops.ptcache.bake_all(bake=True)

    # save file when done
    # WARNING: save file can create conflicts with version control systems
    try:
        bpy.ops.wm.save_mainfile(filepath=bpy.data.filepath, check_existing=False)
    except:
        print("error on saving file to HDD after bake process complete")
except:
    print("some strange thigs happened during bake process")



# using bake all from smoke namespace will not bake fluids too  ... so,
# after baking smoke we try to run fluid fluid bake

# bake fluid


try:
    bpy.ops.fluid.bake()
except:
    print("error when baking fluid")
