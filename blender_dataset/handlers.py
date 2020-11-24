# Copyright 2018-2020 Ivan Alles. See also the LICENSE file.

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

        :param obj: the obj to place, e.g. a mesh, camera, empty, etc.
        :param location_range: a tuple ((x_min, y_min, z_min), (x_max, y_max, z_max)).
        :param rotation_euler_range: a tuple ((a1_min, a2_min, a3_min), (a1_max, a2_max, a3_max)).
        """
        super().__init__()
        self._object = obj
        self._location_range = location_range
        self._rotation_euler_range = rotation_euler_range

    def on_image_begin(self):
        if self._location_range is not None:
            self._object.location = self._generator.rng.uniform(*self._location_range)

        if self._rotation_euler_range is not None:
            self._object.rotation_euler = self._generator.rng.uniform(*self._rotation_euler_range)


class PlaceMultipleObjectsHandler(Handler):
    """
    Places multiple objects at a range of positions.

    Can check intersection and visibility.

    Developer notes: consider that derived classes may change the list of objects in run-time.
    """
    def __init__(self,
                 objects,
                 location_range=None,
                 rotation_euler_range=None,
                 bounds=None,
                 prevent_intersection_2d=False,
                 prevent_intersection_3d=False,
                 max_corners_outside_image=None,
                 far_away=None,
                 make_map2d=False,
                 random_attempt_count=100):
        super().__init__()
        self._location_range = np.array(location_range)
        self._rotation_euler_range = rotation_euler_range
        self._objects = objects
        self._bounds = bounds
        self._prevent_intersection_2d = prevent_intersection_2d
        self._prevent_intersection_3d = prevent_intersection_3d
        self._max_corners_outside_image = max_corners_outside_image
        self._far_away = far_away
        self._make_map2d = make_map2d
        self._map2d = None
        self._random_attempt_count = random_attempt_count

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

        check_bounds = check_bounds_bounding_box

        return check_bounds(obj)

    def on_image_begin(self):
        if self._make_map2d or self._max_corners_outside_image is not None:
            self._map2d = np.zeros(self._image_size[::-1], dtype=np.int32)

        if self._far_away is not None:
            for o in self._objects:
                o.location = self._far_away
            bpy.context.scene.update()

        successfully_placed = []

        for obj_i, obj in enumerate(self._objects):
            is_position_valid = False

            for attempt_i in range(self._random_attempt_count):
                if self._location_range is not None:
                    location = self._generator.rng.uniform(*self._location_range)

                if self._rotation_euler_range is not None:
                    rotation_euler = self._generator.rng.uniform(*self._rotation_euler_range)

                obj.location = location
                obj.rotation_euler = rotation_euler
                bpy.context.scene.update()

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

                if self._prevent_intersection_3d:
                    if utils.is_mesh_intersecting([obj], successfully_placed):
                        continue

                convex_hull_intesecting = False
                if self._prevent_intersection_2d:
                    if obj_i > 0:
                        convex_hull_image = np.zeros(self._image_size[::-1], dtype=np.int32)
                        cv2.fillPoly(convex_hull_image, convex_hull.reshape(1, -1, 2), color=obj_i + 1)
                        convex_hull_intesecting = np.logical_and(convex_hull_image, self._map2d).any()

                    if convex_hull_intesecting:
                        continue

                is_position_valid = True
                successfully_placed.append(obj)
                if self._make_map2d or self._prevent_intersection_2d:
                    cv2.fillPoly(self._map2d, convex_hull.reshape(1, -1, 2), color=obj_i + 1)
                    # cv2.imshow("map2d", self._map2d)
                    # cv2.waitKey(1000)
                    break

            if not is_position_valid and self._far_away is not None:
                obj.location = self._far_away
                bpy.context.scene.update()
                continue


class SetMaterialHandler(Handler):
    """
    This handler sets surface for an obj.

    TODO(ia): port random material weights from number plates.
    """

    def __init__(self, obj, materials=[],
                 texture_location_range=None,
                 texture_scale_range=None):
        """
        Constructs a new SetTexturedSurfaceHandler.

        :param materials a list of material names.
        """
        super().__init__()
        self._materials = [bpy.data.materials.get(mn) for mn in materials]
        self._object = obj
        self._texture_location_range = texture_location_range
        self._texture_scale_range = texture_scale_range

    def on_image_begin(self):
        material = self._materials[self._generator.rng.randint(0, len(self._materials))]
        self._object.data.materials.clear()
        self._object.data.materials.append(material)
        # mapping_key = "Mapping"
        # if mapping_key in material.node_tree.nodes:
        #     texture_mapping_node = material.node_tree.nodes[mapping_key]
        #     if self._texture_location_range is not None:
        #         value = self._generator.rng.uniform(self._texture_location_range[0], self._texture_location_range[1])
        #         # TODO(ia): restore this
        #         # texture_mapping_node.translation = value
        #     if self._texture_scale_range is not None:
        #         value = self._generator.rng.uniform(self._texture_scale_range[0], self._texture_scale_range[1])
        #         # TODO(ia): restore this
        #         # texture_mapping_node.scale = value


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

        :param light: light obj.
        :param power_range: a tuple (strength_min, strength_max).
        :param color_range: a tuple ((r_min, g_min, b_min), (r_max, g_max, b_max)).
        """
        super().__init__()
        self._light = light
        self._power_range = power_range
        self._color_range = color_range

    def on_image_begin(self):
        if self._power_range is not None:
            self._light.data.energy = self._generator.rng.uniform(*self._power_range)
        if self._color_range is not None:
            self._light.data.color = self._generator.rng.uniform(*self._color_range)
