# noinspection PyUnresolvedReferences
import bpy
import numpy as np
import os
import sys
import json

MYDIR = os.path.dirname(bpy.data.filepath)
PROJECT_ROOT = os.path.abspath(os.path.join(MYDIR, '..', '..'))
print(PROJECT_ROOT)

# Allow imports form our project instead of blender installation.
module_paths = [
    PROJECT_ROOT,
#    os.path.join(PROJECT_ROOT, '.venv/Lib/site-packages')
]

for mp in module_paths:
    ap = os.path.abspath(mp)
    print(ap)
    if not ap in sys.path:
        sys.path.append(ap)

from blender_dataset import generator
from blender_dataset import handlers
from robogym import transform3 as t3


# Settings
out_dir = os.path.join(MYDIR, 'output')

# Set-up generator and handlers
generator = generator.Generator(
    incremental=False,
    output_dir=out_dir,
    image_size=[640, 480],
    rng_seed=1)

#working_plane = bpy.data.objects['working_plane']

camera = bpy.data.objects['Camera']


# Fix camera position at z = min_z. We will vary object position in range [min_z - max_z, 0]
#min_z = 100
#camera.location = (0, 0, min_z)


handlers = [
]

generator.add_handlers(handlers)
generator.generate_images(10)


