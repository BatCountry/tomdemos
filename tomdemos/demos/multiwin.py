"""
Pygame only lets you have one window, but that doesn't mean the program only gets to have one Window,
it just means Pygame won't be controlling more than one of them.  Using Pyside6 here (a wrapper for PyQt6)
to give an options window that lets you screw around with parameters.

Also why engineer something when you can overengineer it? I've added a parameter registration system to the 
tomdemos.common namespace which will make it easy to dynamically generate window controls to manage them
and also help document the settings of stuff.
"""
import numpy as np
import pygame

from tomdemos.common.harness import Harness
from tomdemos.common.parameters import Parameters
from tomdemos.common.uiwindow import Application, ParametersWindow

from numpy.lib.stride_tricks import sliding_window_view

from numpy.typing import NDArray


MAX_HEIGHT = 600
MAX_WIDTH = 1920


PARAMETERS = Parameters([
    {
        "name": "height",
        "default": 80,
        "description": "Height of the virtual fire map",
        "validator": lambda v: type(v) is int and v > 0 and v < MAX_HEIGHT
    },
    {
        "name": "width",
        "default": 320,
        "description": "Width of the virtual fire map",
        "validator": lambda v: type(v) is int and v > 0 and v < MAX_WIDTH
    },
    # center of the kernel is basically the current pixel, and how much it value counts for the final value of this pixel
    # with that in mind, see that above doesn't matter at all, where we're at kinda matters, left and right barely matter
    # but immediately below and to the sides matter a lot
    {
        "name": "kernel",
        "default": [
            [0.00, 0.00, 0.00],
            [0.05, 0.10, 0.05],
            [0.20, 0.35, 0.20]],
        "description": "Convolution kernel to propagate the fire effect. Must add up to less than 1.0.",
        "validator": lambda v: len(v) == 3 and all(len(i) == 3 for i in v) and sum(sum(i) for i in v) <= 1.0
    },
    {
        "name": "color_weights",
        "default": [
            [[  0,   0,   0], 0.07], # black
            [[ 25,  25,  25], 0.05], # smokey
            [[ 50,  25,  25], 0.03], # smokey darkred
            [[180,   0,   0], 0.12], # red
            [[255,  90,   0], 0.25], # orange
            [[255, 220,   0], 0.20], # yellow
            [[255, 255, 255], 0.28], # white
        ],
        "description": (
            "An array of pairs of RGB value vectors (0-255 per channel) and the decimal percentage"
            "that each color should occupy of the resulting linear 256 color palette."
            "The color palette percentages need to add up to 1.0"
        ),
        "validator": lambda v: np.isclose(sum(i[1] for i in v), 1.0)
    },
])


def main(harness: Harness):
    Application.create()
    window = ParametersWindow(PARAMETERS)
    harness.start_window(window)

    def kernel_convolve(intensity_map: NDArray) -> NDArray:
        windows = sliding_window_view(np.pad(intensity_map, 1), (3,3))
        return np.sum(windows * PARAMETERS.kernel, axis=(-2, -1))


    # random number generator from numpy because reasons
    rng = np.random.default_rng()

    # separate out the crap here
    colors = np.array([color for color, weight in PARAMETERS.color_weights])
    weights = np.array([weight for color, weight in PARAMETERS.color_weights])

    # this turns the collection of percentages into the start positions of those colors across the range from 0.0 to 1.0
    positions = np.cumsum(weights) - weights

    # this is just some janitorial shit from when I was tuning the color values
    check_the_sum = np.sum(weights)
    assert np.isclose(check_the_sum, 1.0), check_the_sum

    # this turns what is basically [[r,r,r,r,r],[g,g,g,g,g],[b,b,b,b,b]] into [[r,g,b], [r,g,b], ...]
    # then uses that smooth linear gradient thing in linspace across 256 values to make palette
    palette = np.column_stack([
        np.interp(
            np.linspace(0.0, 1.0, 256), 
            positions, 
            colors[:, channel])
        for channel in range(3)
    ]).astype(np.uint8)

    # the actual fire field to store a single float intensity value per position
    # everything happens on the y axis, so we're putting height in the first field
    intensity_map = np.zeros((PARAMETERS.height+1, PARAMETERS.width))
    intensity_map_hw = (PARAMETERS.height, PARAMETERS.width)

    # render target with chonky pixel size
    intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))

    # Do fire
    # we're waiting until we hit the next frame timing to hit a 30fps target framerate
    while harness.tick(30):
        # if we've changed the dimensions in the parameters window, we have to regen the surface and the intensity map
        if intensity_map_hw != (PARAMETERS.height, PARAMETERS.width):
            intensity_map = np.zeros((PARAMETERS.height+1, PARAMETERS.width))
            intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))
            intensity_map_hw = (PARAMETERS.height, PARAMETERS.width)

        # use the box convolver to smear up
        intensity_map = kernel_convolve(intensity_map)

        # bottom fire line is replaced with a random line that's like 65% new hot pixels - bottom is PARAMETERS.height because we padded
        intensity_map[PARAMETERS.height] = rng.random(PARAMETERS.width) > 0.65

        pygame.surfarray.blit_array(
            intermediate_surface, 
            # do palettte lookup for whole array
            palette[(intensity_map[:-1]*255).astype(np.uint8)]
            # then swap width/height because
            .transpose((1, 0, 2)))
        
        # and then this one I'm just integer rescaling (nearest-neighbor) the intermediate 320x240 surface we're working with and writing directly to the target screen
        pygame.transform.scale(intermediate_surface, harness.screen.get_size(), harness.screen)

        # then flipping the double buffer
        pygame.display.flip()
