"""
# Simple demoscene fire effect using pygame, but with numpy doing what we couldn't do with old-assed non-floating-point-assed hardware

So basically the old demoscene fire effect is basically you have a palette LUT that is basically 256 color mode but like 32 colors.
with a gradient from white -> yellow -> orange -> red -> dark_red -> black
You kept basically a scalar value (from like 0 - 31 usually, because 32 values colors made the integer math fast) that was how "intense" the fire was.
Each frame you'd dim the previous line and copy it up one, either blanking the top row or just letting god sort it out.
You'd stop 1 from the bottom row.
Then the bottom row you'd fill with a random scattering of 0-31 intensity values across it.  This meant you'd have "embers" that would "rise" as they were 
copied up, and dim as they went, and the bottom row would generate new randomly positioned embers.

I'm doing this shit with pygame as dumb as possible, with real RGBA and a palette lookup that I'll be honest, I asked ChatGPT how it'd do it with numpy
because I wanted to use numpy, and when I suggested what I wanted to do it told me how to do it, then told me a much saner way of doing it.
I'm not good with numpy.

Here's my reimplementation of what it suggested, plus my idea of how to handle the fire fade, which is basically using numpy.roll to shift the array.
This puts the top at the bottom, and shifts everything else up. Then I multiply the whole matrix by the intensity decay factor, which makes it all dimmer.
Then I overwrite the bottom with new embers. Same shit, different magic, and insanely faster on modern hardware.
"""
import numpy as np
import pygame

from tomdemos.common.harness import Harness


def main(harness: Harness):
    # random number generator from numpy because reasons
    rng = np.random.default_rng()

    # pygame frame timer
    clock = pygame.Clock()

    # virtual screen - we want chonky pixels
    width = 160
    height = 120

    # it's an oldschool 256-color palette
    # interpolated by some fucking magic that AI explained but it's too late and my brain can't tonight
    # I think it's basically just lerping between each of those values, where 1.0 basically maps to bright white, 
    # and 0.0 maps to black, and it's the gradient I described at the top
    stops = np.array([
        [  0,   0,   0],   # black
        [75,   0,   0],   # darkred
        [180,   0,   0],   # red
        [255,  90,   0],   # orange
        [255, 220,   0],   # yellow
        [255, 255, 255],   # white
    ], dtype=np.float32)

    # this is some shit that gives you basically 256 steps that go from zero to the number of color stops
    # lerping between the stops (like 0.0 is black, 0.16667 is darkred, 0.08 is halfway between black and darkred)
    x = np.linspace(0, len(stops) - 1, 256)

    # then this bit here basically does the thing here where it builds a 256 color array out of looking up the color from that lerp of stops, more lerp. lerp.
    palette = np.column_stack([
        np.interp(x, np.arange(len(stops)), stops[:, channel])
        for channel in range(3)
    ]).astype(np.uint8)

    # the actual fire field to store a single float intensity value per position
    # everything happens on the y axis, so we're putting height in the first field
    intensity_map = np.zeros((height, width))

    # render target with chonky pixel size
    intermediate_surface = pygame.Surface((width, height))

    # Do fire
    # we're waiting until we hit the next frame timing to hit a 30fps target framerate
    while harness.tick(30):
        # fade the map
        intensity_map *= 0.95

        # roll the buffer up
        intensity_map = np.roll(intensity_map, -1, axis=0)

        # bottom fire line is replaced with a random line that's like 65% new hot pixels
        intensity_map[height-1] = rng.random(width) > 0.65

        pygame.surfarray.blit_array(
            intermediate_surface, 
            # do palettte lookup for whole array
            palette[(intensity_map*255).astype(np.uint8)]
            # then swap width/height because
            .transpose((1, 0, 2)))
        
        # and then this one I'm just integer rescaling (nearest-neighbor) the intermediate 320x240 surface we're working with and writing directly to the target screen
        pygame.transform.scale(intermediate_surface, harness.screen.get_size(), harness.screen)

        # then flipping the double buffer
        pygame.display.flip()
