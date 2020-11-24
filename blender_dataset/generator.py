# Copyright 2018-2020 Ivan Alles. See also the LICENSE file.

import glob
import os

# noinspection PyUnresolvedReferences
import bpy
import numpy as np

from blender_dataset import utils

class Generator:
    """
    Generates images by transforming and rendering a blender scene.
    """

    def __init__(self, incremental=False,
                 output_dir='output',
                 image_dir='images', image_size=(640, 480), image_extension='png',
                 rng_seed=None):
        """
        Creates new object.

        :param incremental if false, will clear the output directory and recreate all outputs.
               If true, will add images to existing ones.
               If incremental is true, but the output directory does not exist,
               the setting is ignored. self.incremental will return false. This can be used to start generation from scratch by deleting the output
               directory without changing the parameters.
        :param output_dir: root directory for all output files. Will be cleared before image generation.
        :param image_dir: root directory for images (relative to output).
        :param image_size: size of the image. A tuple of (width, height, percentage).
        If the percentage is omitted it will default to 100 (recommended).
        :param rng_seed: rng seed to initialize self.rng. If None, numpy will use a random seed.
        """
        self._output_dir = output_dir
        self._incremental = incremental
        if self._incremental and not os.path.isdir(self._output_dir):
            self._incremental = False
        self._image_size = image_size
        self._image_dir = image_dir
        self._image_extension = image_extension
        self._handlers = []
        self._rng = np.random.RandomState(rng_seed)
        self._current_image_path = None

    @property
    def incremental(self):
        return self._incremental

    @property
    def output_dir(self):
        return self._output_dir

    @property
    def image_dir(self):
        return self._image_dir

    @property
    def current_image_path(self):
        """
        Relative (to output_dir/image_dir) path to the current image (including directories, filename and extension).
        :return:
        """
        return self._current_image_path

    @property
    def rng(self):
        """
        Random number generator. The handlers should use it to generate random numbers.

        :return: an instance of np.random.RandomState.
        """
        return self._rng

    def add_handlers(self, handlers):
        """
        Adds a list of handlers.
        """
        self._handlers += handlers

    def remove_handler(self, handler):
        """
        Removes a specified handler.
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    def generate_images(self, count):
        """
        Generate and renders images.

        :param count: number of images to generate.
        """
        for handler in self._handlers:
            handler.generator = self

        image_dir = os.path.join(self._output_dir, self._image_dir)

        if self._incremental:
            path = self._output_dir + "/" + self._image_dir + '/**/*.' + self._image_extension
            images = glob.glob(path, recursive=True)
            indexes = [int(os.path.splitext(os.path.basename(x))[0]) for x in images] + [-1]
            start_index = max(indexes) + 1
        else:
            start_index = 0
            utils.make_clean_directory(self._output_dir)

        self._run_handlers("on_scene_begin")

        if self._image_size is not None:
            utils.set_render_image_size(*self._image_size)

        for i in range(start_index, start_index + count):
            self._current_image_path = '{:04d}/{:07d}.{}'.format(i // 1000, i, self._image_extension)
            self._run_handlers("on_image_begin")
            full_image_path = os.path.join(image_dir, self._current_image_path)
            utils.set_render_filepath(full_image_path)
            bpy.ops.render.render(write_still=True)
            self._run_handlers("on_image_end", reverse=True)

        self._run_handlers("on_scene_end", reverse=True)

    def _run_handlers(self, method_name, reverse=False):
        handlers = reversed(self._handlers) if reverse else self._handlers
        for handler in handlers:
            method = getattr(handler, method_name)
            method()

