"""
Same as the previous, but real demoscene fire basically used a weighted average of the neighboring pixels 
to roll up the fire effect to get that nice plasma and smooth fade.
Using a box convolve effect to do that walking box sampling. Sampling the pixel I'm at stretches the fire
upward further while not unduly preserving the brightness or making it into a soup.
"""
import numpy as np
import pygame

from tomdemos.common.harness import Harness
from numpy.lib.stride_tricks import sliding_window_view

from numpy.typing import NDArray


# virtual screen - we want chonky pixels
HEIGHT = 80
WIDTH = 320


# center of the kernel is basically the current pixel, and how much it value counts for the final value of this pixel
# with that in mind, see that above doesn't matter at all, where we're at kinda matters, left and right barely matter
# but immediately below and to the sides matter a lot
CONVOLUTION_KERNEL = np.array([
    [0.00, 0.00, 0.00],
    [0.05, 0.10, 0.05],
    [0.20, 0.35, 0.20]
])


def kernel_convolve(intensity_map: NDArray) -> NDArray:
    windows = sliding_window_view(np.pad(intensity_map, 1), (3,3))
    return np.sum(windows * CONVOLUTION_KERNEL, axis=(-2, -1))
    

def main(harness: Harness):
    # random number generator from numpy because reasons
    rng = np.random.default_rng()

    # it's an oldschool 256-color palette, but weighted
    color_weights = [
        [[  0,   0,   0], 0.07], # black
        [[ 25,  25,  25], 0.05], # smokey
        [[ 50,  25,  25], 0.03], # smokey darkred
        [[180,   0,   0], 0.12], # red
        [[255,  90,   0], 0.25], # orange
        [[255, 220,   0], 0.20], # yellow
        [[255, 255, 255], 0.28], # white
    ]

    # separate out the crap here
    colors = np.array([color for color, weight in color_weights])
    weights = np.array([weight for color, weight in color_weights])

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
    intensity_map = np.zeros((HEIGHT+1, WIDTH))

    # render target with chonky pixel size
    intermediate_surface = pygame.Surface((WIDTH, HEIGHT))

    # Do fire
    # we're waiting until we hit the next frame timing to hit a 30fps target framerate
    while harness.tick(30):
        # use the box convolver to smear up
        intensity_map = kernel_convolve(intensity_map)

        # bottom fire line is replaced with a random line that's like 65% new hot pixels - bottom is HEIGHT because we padded
        intensity_map[HEIGHT] = rng.random(WIDTH) > 0.65

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
