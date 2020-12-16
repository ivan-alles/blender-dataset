# Copyright 2018-2020 Ivan Alles. See also the LICENSE file.

import json
import os
import shutil

# noinspection PyUnresolvedReferences
import bpy
import cv2
# noinspection PyUnresolvedReferences
from mathutils import Vector
import numpy as np
from robogym import transform3 as t3

from blender_dataset import utils


class Handler:
    """
    A handler is a kind of subroutine that is used in preparing a scene for rendering.

    It can move objects, switch on lights, write to file, etc. Handlers can be chained together to make
    a complex algorithm.
    """

    def __init__(self,):
        self._generator = None

    @property
    def generator(self):
        return self._generator

    @generator.setter
    def generator(self, value):
        self._generator = value

    def on_scene_begin(self):
        """
        Is called when the image scene processing is started.
        """
        pass

    def on_scene_end(self):
        """
        Is called when the image scene processing is finished.
        """
        pass

    def on_image_begin(self):
        """
        Is called for each rendered scene before rendering.

        The handler can apply its transforms, etc.
        """
        pass

    def on_image_end(self):
        """
        Is called for each rendered scene after rendering.

        The handler can undo its transforms if necessary, etc.
        """
        pass


class PlaceObject(Handler):
    """
    Places an obj into desired location and orientation.
    """

    def __init__(self, obj, location_range=None, rotation_euler_range=None):
        """
        Creates a new handler.

        :param obj: the object or its name.
        :param location_range: a tuple ((x_min, y_min, z_min), (x_max, y_max, z_max)).
        :param rotation_euler_range: a tuple ((a1_min, a2_min, a3_min), (a1_max, a2_max, a3_max)).
        """
        super().__init__()
        self._object = utils.get_object(obj)
        self._location_range = location_range
        self._rotation_euler_range = rotation_euler_range

    def on_image_begin(self):
        if self._location_range is not None:
            self._object.location = self._generator.rng.uniform(*self._location_range)

        if self._rotation_euler_range is not None:
            self._object.rotation_euler = self._generator.rng.uniform(*self._rotation_euler_range)


class PlaceMultipleObjectsHandler(Handler):
    """
    Tries to places multiple objects at a range of positions.
    Can check intersection and visibility.
    """
    def __init__(self,
                 objects,
                 location_range=None,
                 rotation_euler_range=None,
                 bounds=None,
                 intersection_3d=True,
                 intersection_2d=True,
                 max_corners_outside_image=None,
                 make_map2d=False,
                 random_attempt_count=100,
                 break_on_first_failed=False):
        """
        :param objects: an iterable of objects.
        :param location_range: a tuple ((x_min, y_min, z_min), (x_max, y_max, z_max)).
        :param rotation_euler_range: a tuple ((a1_min, a2_min, a3_min), (a1_max, a2_max, a3_max)).
        :param bounds: a bounding box the objects must fit into: ((minx, miny, minz), (maxx, maxy, maxz)).
        :param intersection_3d: if False, the 3d objects will not intersect.
        :param intersection_2d: if False, the rendered objects will not intersect.
        :param max_corners_outside_image: maximal number of object corners outside the image.
        :param make_map2d: make a 2d array with pixels filled with object indexes.
        :param random_attempt_count: a number of attempts to place the objects.
        :param break_on_first_failed: if True, stops on the first objects that cannot be placed.
        """
        super().__init__()
        self._location_range = np.array(location_range)
        self._rotation_euler_range = rotation_euler_range
        self._objects = [utils.get_object(o) for o in objects]
        self._bounds = bounds
        self._intersection_2d = intersection_2d
        self._intersection_3d = intersection_3d
        self._max_corners_outside_image = max_corners_outside_image
        self._make_map2d = make_map2d
        self._map2d = None
        self._random_attempt_count = random_attempt_count
        self._break_on_first_failed = break_on_first_failed

        image_pose_camera, self._image_size = utils.get_camera_intrinsics()
        image_pose_camera = t3.Transform3(image_pose_camera)
        self._camera_pose_image = image_pose_camera.inv()
        self._image_corners = np.array([
            [0, 0],
            [self._image_size[0], 0],
            [0, self._image_size[1]],
            [self._image_size[0], self._image_size[1]]]
        ) - 0.5

    @property
    def map2d(self):
        """
        An int32 image with the same size as rendered image.

        Each pixel contains an index + 1 of the convex hull
        of the obj projected to this pixel. Zero pixels indicate the absence of an obj.
        :return:
        """
        return self._map2d

    def _is_in_bounds(self, obj):
        """
        Check if the object is in bounds.

        :return: True if the object is in bounds.
        """
        if self._bounds is None:
            return True

        def check_bounds_bounding_box(obj):
            lb = np.array(self._bounds[0])
            ub = np.array(self._bounds[1])

            objects = utils.flatten_object_hierarchy(obj)
            points = []
            for o in objects:
                for p in o.bound_box:
                    pl = list(obj.matrix_world * Vector(p))
                    points.append(pl)

            points = np.array(points)
            is_outside = np.any(np.logical_or(points < lb, ub < points))

            return not is_outside

        return check_bounds_bounding_box(obj)

    def on_image_begin(self):
        is_map2d_required = self._make_map2d or not self._intersection_2d

        if is_map2d_required:
            self._map2d = np.zeros(self._image_size[::-1], dtype=np.int32)
        successfully_placed = []

        for obj in self._objects:
            obj.hide_viewport = True
            obj.hide_render = True

        object_indices = list(range(len(self._objects)))
        self._generator.rng.shuffle(object_indices)

        for obj_i in object_indices:
            obj = self._objects[obj_i]
            is_placed = False
            obj.hide_viewport = False
            obj.hide_render = False

            for attempt_i in range(self._random_attempt_count):
                if self._location_range is not None:
                    obj.location = self._generator.rng.uniform(*self._location_range)

                if self._rotation_euler_range is not None:
                    obj.rotation_euler = self._generator.rng.uniform(*self._rotation_euler_range)

                bpy.context.view_layer.update()

                if not self._is_in_bounds(obj):
                    continue

                convex_hull = utils.compute_convex_hull_on_image(obj)

                if self._max_corners_outside_image is not None:
                    corners_outside_image = 0

                    for p in convex_hull:
                        if p[0] < 0 or p[1] < 0 or p[0] >= self._image_size[0] or p[1] >= self._image_size[1]:
                            corners_outside_image += 1

                    if corners_outside_image > self._max_corners_outside_image:
                        continue

                if not self._intersection_3d and utils.is_mesh_intersecting([obj], successfully_placed):
                    continue

                if not self._intersection_2d:
                    convex_hull_image = np.zeros_like(self._map2d)
                    cv2.fillPoly(convex_hull_image, convex_hull.reshape(1, -1, 2), color=obj_i + 1)
                    if np.logical_and(convex_hull_image, self._map2d).any():
                        continue

                bpy.context.view_layer.update()
                successfully_placed.append(obj)
                is_placed = True
                if is_map2d_required:
                    cv2.fillPoly(self._map2d, convex_hull.reshape(1, -1, 2), color=obj_i + 1)
                    # cv2.imshow('map2d', self._map2d.astype(np.float32) / len(self._objects))
                    # cv2.waitKey(1000)
                break

            if not is_placed:
                obj.hide_viewport = True
                obj.hide_render = True
                if self._break_on_first_failed:
                    break


class SetMaterialHandler(Handler):
    """
    Set material for an object.
    How to create materials with textures: https://www.youtube.com/watch?v=NpJKZPTXlTU
    """

    def __init__(self, obj, materials=[],
                 texture_location_range=None,
                 texture_rotation_range=None,
                 texture_scale_range=None,
                 color_range=None):
        """
        Constructs a new SetTexturedSurfaceHandler.

        :param materials a list of material names.
        """
        super().__init__()
        self._materials = [bpy.data.materials.get(mn) for mn in materials]
        self._object = utils.get_object(obj)
        self._texture_location_range = texture_location_range
        self._texture_rotation_range = texture_rotation_range
        self._texture_scale_range = texture_scale_range
        self._color_range = color_range

    def on_image_begin(self):
        material = self._materials[self._generator.rng.randint(0, len(self._materials))]
        self._object.data.materials.clear()
        self._object.data.materials.append(material)

        mapping_key = 'Principled BSDF'  # This is a node in a simple material created by default
        if mapping_key in material.node_tree.nodes:
            node = material.node_tree.nodes[mapping_key]
            if self._color_range is not None:
                value = self._generator.rng.uniform(*self._color_range)
                node.inputs[0].default_value = value

        mapping_key = 'Mapping'  # This is the mapping node from texture coordinates to color, normals, and roughness.
        if mapping_key in material.node_tree.nodes:
            texture_mapping_node = material.node_tree.nodes[mapping_key]
            if self._texture_location_range is not None:
                value = self._generator.rng.uniform(*self._texture_location_range)
                texture_mapping_node.inputs[1].default_value = value
            if self._texture_rotation_range is not None:
                value = self._generator.rng.uniform(*self._texture_rotation_range)
                texture_mapping_node.inputs[2].default_value = value
            if self._texture_scale_range is not None:
                value = self._generator.rng.uniform(*self._texture_scale_range)
                texture_mapping_node.inputs[3].default_value = value


class SetLightHandler(Handler):
    """
    Set light parameters.
    """
    def __init__(self, light,
                 power_range=None,
                 color_range=None
                 ):
        """
        Creates a new handler.

        :param light: light obj or its name.
        :param power_range: a tuple (strength_min, strength_max).
        :param color_range: a tuple ((r_min, g_min, b_min), (r_max, g_max, b_max)).
        """
        super().__init__()
        self._light = utils.get_object(light)
        self._power_range = power_range
        self._color_range = color_range

    def on_image_begin(self):
        if self._power_range is not None:
            self._light.data.energy = self._generator.rng.uniform(*self._power_range)
        if self._color_range is not None:
            self._light.data.color = self._generator.rng.uniform(*self._color_range)


class CreateDatasetFileHandler(Handler):
    """
    Creates a JSON file containing a list of objects for each rendered image.
    """
    def __init__(self, objects, output_file='dataset.json'):
        """
        Constructor.
        :param objects: an iterable of objects. Of those, only objects having hide_render set to False
        will be included to include in the dataset.
        :param output_file: the name of the output file (relative to the output directory).
        """
        super().__init__()
        self._objects = [utils.get_object(o) for o in objects]
        self._output_file = output_file
        self._data = []
        self._output_path = None

    def on_scene_begin(self):
        if self._output_path is None:
            self._output_path = os.path.join(self._generator.output_dir, self._output_file)

    def on_image_end(self):
        """
        Add an entry to the output file and save it.

        Do it after image rendering and saving to make sure the file references an existing image.
        """
        bpy.context.view_layer.update()

        objects = []
        for obj in self._objects:
            obj_labels = self._create_object_labels(obj)
            if obj_labels is not None:
                objects.append(obj_labels)
        self._data.append(
            {
                'image': self._generator.current_image_path,
                'objects': objects
            }
        )

        self._save()

    def _create_object_labels(self, obj):
        """
        Create labels for current object.
        :return: a dictionary of object labels or None to skip the object.
        """
        if obj.hide_render:
            return None
        world_origin = obj.matrix_world @ Vector((0, 0, 0))
        world_ax = obj.matrix_world @ Vector((1, 0, 0))
        image_origin = utils.world_to_image(world_origin)
        image_ax = utils.world_to_image(world_ax)
        image_ax_vector = image_ax - image_origin
        angle = np.arctan2(image_ax_vector[1], image_ax_vector[0])
        origin_label = {
            'x': image_origin[0],
            'y': image_origin[1],
            'angle': angle,
        }
        return {
            'category': self._objects.index(obj),
            'origin': origin_label
        }

    def on_scene_end(self):
        self._save()

    def _save(self):
        if os.path.isfile(self._output_path):
            shutil.copyfile(self._output_path, self._output_path + ".bak")

        with open(self._output_path, 'w') as f:
            json.dump(self._data, f, indent=1)
