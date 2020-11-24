import os
import sys

# noinspection PyUnresolvedReferences
import bpy

# Set to True to install dependencies once. Blender must be run with amdinistrator rights.
if False:
    import subprocess

    python_exe = os.path.join(sys.prefix, 'bin', 'python.exe')
    subprocess.call([python_exe, '-m', 'ensurepip'])
    subprocess.call([python_exe, '-m', 'pip', 'install', '--upgrade', 'pip'])

    subprocess.call([python_exe, '-m', 'pip', 'install', 'opencv-python'])
    subprocess.call([python_exe, '-m', 'pip', 'install', 'scipy'])
    subprocess.call([python_exe, '-m', 'pip', 'install', 'git+https://github.com/ivan-alles/robogym.git@master'])

MYDIR = os.path.dirname(bpy.data.filepath)
# Add project root to be able to import blender-dataset.
sys.path.append(os.path.abspath(os.path.join(MYDIR, '..', '..')))

from blender_dataset import generator
from blender_dataset import handlers

light = bpy.data.objects['light']

# Set-up generator and handlers
generator = generator.Generator(
    incremental=False,
    output_dir=os.path.join(MYDIR, 'output'),
    image_size=[640, 480],
    rng_seed=1)

cube = bpy.data.objects['cube']
camera = bpy.data.objects['camera']

handlers = [
    handlers.SetLightHandler(
        light,
        power_range=(5, 15),
        color_range=((0.8, 0.8, 0.8), (1, 1, 1)
        )
    ),
    handlers.PlaceObject(
        light,
        location_range=((-1, -1, 0.5), (1, 1, 1.5))),
    handlers.PlaceObject(
        cube,
        location_range=((-0.10, -0.10, 0.05), (0.10, 0.10, 0.15)),
        rotation_euler_range=((-0.05, -0.05, -3.15), (0.05, 0.05, 3.15)))
]

generator.add_handlers(handlers)
generator.generate_images(10)
