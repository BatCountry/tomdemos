"""
Guts of a new demo
"""
import ast
import re
from collections.abc import Callable

from typing import Callable

import numpy as np
import pygame

from tomdemos.common.harness import Harness
from tomdemos.common.parameters import Parameters
from tomdemos.common.uiwindow import Application, ParametersWindow


PARAMETERS = Parameters([
    {
        "name": "height",
        "default": 600,
        "description": "Height of the virtual buffer",
        "validator": lambda v: type(v) is int and v > 0
    },
    {
        "name": "width",
        "default": 800,
        "description": "Width of the virtual buffer",
        "validator": lambda v: type(v) is int and v > 0
    },
    {
        "name": "time_scale",
        "default": 0.001,
        "description": "A multiplier to scale down the tick counter from microseconds to something less jittery, adjusts motion speed",
        "validator": lambda v: (type(v) is float or type(v) is int)
    },
    {
        "name": "placeholder",
        "default": "V",
        "headers": {
            "columns": ["Vee",]
        },
        "description":
            "Vee. ",
        "pre_validator": lambda v: v,
        "column_validators": {
            # column 0, +/- sin/cos
            0: lambda v: v,
            # column 1, 2, parse_expression
            "default": lambda v: v
        },
        "row_factory": lambda: list(["v"])
    },
])


def build_palette() -> np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]:
    # separate out the crap here
    colors = np.array([[r,g,b] for r,g,b, _ in PARAMETERS.color_weights])
    weights = np.array([weight for _, __, ___, weight in PARAMETERS.color_weights])

    # this turns the collection of percentages into the start positions of those colors across the range from 0.0 to 1.0
    weights = weights / 100.0
    positions = np.cumsum(weights) - weights

    # this turns what is basically [[r,r,r,r,r],[g,g,g,g,g],[b,b,b,b,b]] into [[r,g,b], [r,g,b], ...]
    # then uses that smooth linear gradient thing in linspace across 256 values to make palette
    palette = np.column_stack([
        np.interp(
            np.linspace(0.0, 1.0, 256), 
            positions, 
            colors[:, channel])
        for channel in range(3)
    ]).astype(np.uint8)
    return palette


def main(harness: Harness):
    Application.create()
    window = ParametersWindow(PARAMETERS)
    harness.start_window(window)

    # palette = build_palette()

    intermediate_map = np.zeros((PARAMETERS.height, PARAMETERS.width))

    # render target with chonky pixel size
    intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))

    first_run = True

    # we're waiting until we hit the next frame timing to hit a 30fps target framerate
    while harness.tick(30):
        # if we've changed the dimensions in the parameters window, we have to regen the surface, the intermediate map, and the ogrid, and the scaling factors in the plasma function
        if first_run or PARAMETERS.height.is_dirty() or PARAMETERS.width.is_dirty():
            first_run = False
            intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))
            PARAMETERS.height.clean() 
            PARAMETERS.width.clean()

        # turn the intermediate map into a paletted image and blit it to our intermediate render surface
        # pygame.surfarray.blit_array(
        #     intermediate_surface, 
        #     # do palette lookup for whole array
        #     palette[(intermediate_map*255).astype(np.uint8)]
        #     # then swap width/height because, though it hardly matters here
        #     .transpose((1, 0, 2)))

        # then blit/scale the render surface to our actual window surface
        pygame.transform.scale(intermediate_surface, harness.screen.get_size(), harness.screen)

        # then flip the double buffer
        pygame.display.flip()
