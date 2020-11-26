# Copyright 2018-2020 Ivan Alles. See also the LICENSE file.

import os
import shutil

# noinspection PyUnresolvedReferences
import bmesh
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
import bpy_extras
import cv2
# noinspection PyUnresolvedReferences
from mathutils import bvhtree
# noinspection PyUnresolvedReferences
from mathutils import Vector

import numpy as np


def get_object(obj):
    if type(obj) == str:
        return bpy.data.objects[obj]
    return obj


def set_render_filepath(filepath):
    root, ext = os.path.splitext(filepath)
    bpy.context.scene.render.image_settings.file_format = ext[1:].upper()
    bpy.context.scene.render.filepath = root


def set_render_image_size(width, height, percentage=100):
    bpy.context.scene.render.resolution_percentage = percentage
    bpy.context.scene.render.resolution_x = width
    bpy.context.scene.render.resolution_y = height


def get_camera_intrinsics(camera=None, scene=None, image_size=None):
    """
    Compute camera intrinsics.

    :return: 3x3 intrinsics array, (image_w, image_h)
    """
    scene = bpy.context.scene if scene is None else scene
    camera = scene.camera if camera is None else camera
    if scene is not None and scene.render.resolution_percentage != 100:
        raise ValueError("resolution_percentage != 100 is not supported")
    if image_size is None:
        image_size = (bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y)

    image_size = np.array(image_size, dtype=int)
    focal_length = camera.data.lens
    sensor_width = camera.data.sensor_width
    focal_length_pix = focal_length / sensor_width * image_size[0]

    c = (image_size - 1) / 2

    intrinsics = np.array([
        [focal_length_pix, 0, c[0]],
        [0, focal_length_pix, c[1]],
        [0, 0, 1]
    ], dtype=np.float64)

    return intrinsics, image_size


def world_to_image(world_location, scene=None, camera=None):
    """
    Convert world coordinates to image coordinates.

    :param world_location: (3,) or (n, 3) array-like of points in world coordinates.
    :param scene:
    :param camera:
    :return:
    """
    scene = bpy.context.scene if scene is None else scene
    camera = scene.camera if camera is None else camera

    world_location = np.array(world_location)
    dim = world_location.ndim
    if dim < 1 or dim > 2 or (dim == 2 and world_location.shape[1] != 3):
        raise ValueError('world_location must be a (3,) or (n, 3) array-like')
    world_location = np.atleast_2d(world_location)

    n = world_location.shape[0]
    image_location = np.empty((n, 2), dtype=np.float32)
    for i in range(n):
        im = bpy_extras.object_utils.world_to_camera_view(scene, camera, Vector(list(world_location[i])))
        image_location[i] = [im.x, im.y]

    render_scale = scene.render.resolution_percentage / 100
    render_size = np.array((scene.render.resolution_x, scene.render.resolution_y), dtype=np.float32) * render_scale

    # Flip vertically.
    image_location = (image_location * (1, -1) + (0, 1))

    # Convert normalized device coordinates from x, y, in [0, 1] to image coordinates in [-0.5, size-0.5].
    # 0.5 is subtracted to reflect the fact that the integer pixel coordinates are at the center of the pixel,
    # therefore the corners of the image have coordinates (-0.5, -0.5), (size_x-0.5, -0.5), etc.
    image_location = image_location * render_size - 0.5

    if dim == 1:
        image_location = image_location.reshape(-1)

    return image_location


def flatten_object_hierarchy(obj):
    """
    Flatten obj hierarchy.

    :param obj: a blender obj
    :return: a list containing the obj and all children.
    """

    def preorder(obj, objects):
        objects.append(obj)
        for c in obj.children:
            preorder(c, objects)

    objects = []
    preorder(obj, objects)

    return objects


def project_bounding_box_on_image(obj, scene=None, camera=None):
    """
    Computes a projection of the bounding boxes of the obj and its children onto image.

    :return: np.array of points (x, y).
    """

    objects = flatten_object_hierarchy(obj)
    points = []
    for o in objects:
        for p in o.bound_box:
            pl = list(o.matrix_world @ Vector(p))
            points.append(pl)

    image_points = world_to_image(points, scene, camera)
    return image_points


def compute_orinented_bounding_box_on_image(obj, scene=None, camera=None):
    """
    Computes an oriented rectangle representing a 2d bounding box of the obj with its children.

    :return: an cv2 RotatedRect: a tuple ((center.x, center.y), (size.x, size.y), angle). The angle is in degrees.
    """

    image_points = project_bounding_box_on_image(obj, scene, camera)
    image_points = np.round(image_points).astype(np.int32)
    rect = cv2.minAreaRect(image_points)
    return rect


def compute_convex_hull_on_image(obj, scene=None, camera=None):
    """
    Computes a 2d convex hull of the obj with its children.

    :return: a numpy array Nx2 of points x, y.
    """
    image_points = project_bounding_box_on_image(obj, scene, camera)
    image_points = np.round(image_points).astype(np.int32)
    h = np.array(cv2.convexHull(image_points), dtype=np.int32).reshape(-1, 2)
    return h


def is_mesh_intersecting(objects1, objects2):
    """
    Check mesh intersection.

    :param objects1: list of blender objects.
    :param objects2: list of blender objects.
    :return: True if any objects from objects1 intersects with any object from objects2.
    """
    def make_bvhtree(obj):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        return bvhtree.BVHTree.FromBMesh(bm)

    for obj1 in objects1:
        tree1 = make_bvhtree(obj1)
        for obj2 in objects2:
            if obj1 == obj2:
                continue
            tree2 = make_bvhtree(obj2)
            intersections = tree1.overlap(tree2)
            if intersections:
                return True

    return False


def make_clean_directory(path):
    """
    Creates an empty directory.

    If it exists, delete its content.
    If the directory is opened in Windows Explorer, may throw PermissionError,
    although the directory is usually cleaned. The caller may catch this exception to avoid program termination.
    :param path: path to the directory.
    """
    need_create = True
    if os.path.isdir(path):
        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        need_create = False
    elif os.path.isfile(path):
        os.remove(path)
    if need_create:
        os.makedirs(path)
