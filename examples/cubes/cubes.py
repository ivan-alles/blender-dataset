# Copyright 2018-2020 Ivan Alles. See also the LICENSE file.

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

from blender_dataset import generator  # noqa: E402
from blender_dataset import handlers   # noqa: E402


generator = generator.Generator(
    incremental=False,
    output_dir=os.path.join(MYDIR, 'output'),
    image_size=[640, 480],
    rng_seed=1)

handlers = [
    handlers.SetLightHandler(
        'light',
        power_range=(5, 15),
        color_range=((0.8, 0.8, 0.8), (1, 1, 1))
    ),
    handlers.PlaceObject(
        'light',
        location_range=((-1, -1, 0.5), (1, 1, 1.5))),
    handlers.SetMaterialHandler(
        'cube1',
        ('RedMaterial', 'GreenMaterial', 'Concrete'),
    ),
    handlers.SetMaterialHandler(
        'cube2',
        ('RedMaterial', 'GreenMaterial', 'Concrete'),
    ),
    handlers.PlaceObject(
        'cube1',
        location_range=((-0.10, -0.10, 0.05), (0.10, 0.10, 0.15)),
        rotation_euler_range=((-0.05, -0.05, -3.15), (0.05, 0.05, 3.15))),
    handlers.PlaceObject(
        'cube2',
        location_range=((-0.10, -0.10, 0.05), (0.10, 0.10, 0.15)),
        rotation_euler_range=((-0.05, -0.05, -3.15), (0.05, 0.05, 3.15))),
    # PlaceMultipleObjectsHandler(
    #     [cube],
    #     location_range=((-0.50, -0.50, 0.05), (0.50, 0.50, 0.15)),
    #     rotation_euler_range=((-0.05, -0.05, -3.15), (0.05, 0.05, 3.15))
    # ),
    handlers.SetMaterialHandler(
        'plane',
        ('RedMaterial', 'GreenMaterial', 'Concrete'),
    ),
]

generator.add_handlers(handlers)
generator.generate_images(20)
