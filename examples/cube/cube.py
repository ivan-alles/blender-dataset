import os
import sys

# noinspection PyUnresolvedReferences
import bpy


# Set to True to install dependencies once. Blender must be run with amdinistrator rights.
if True:
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


