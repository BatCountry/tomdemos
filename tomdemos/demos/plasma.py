"""
The Demoscene loved its plasma effects. When you don't have to do floating point math because you can use a lookup table for sin/cos
you get smooth curvy curves instead of jaggy blocks for the cost of jaggy blocks.

In the spirit of multiwin.py, why engineer something when you can overengineer it, so this uses python's AST module to build an 
expression language so you can add arbitrary parameters to the plasma function
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


VALID_NAMES = "xytswhp"

VALID_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.UAdd,
    ast.USub,
)


def parse_expression(expr: str) -> ast.Expression | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if not isinstance(node, VALID_NODES):
            return None

        if isinstance(node, ast.Name) and node.id not in VALID_NAMES:
            return None

        if isinstance(node, ast.Constant) and type(node.value) not in (int, float):
            return None

    return tree


def compile_expression(tree: ast.Expression) -> Callable:
    tree = ast.Expression(
        ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(name) for name in VALID_NAMES[:-1]],
                kwonlyargs=[ast.arg('p')],
                kw_defaults=[ast.Constant(value=np.pi)],
                defaults=[],
            ),
            body=tree.body,
        )
    )

    ast.fix_missing_locations(tree)

    # this isn't safe, and builtins should get sterilized here, but the language is simple and I don't care to fight it anymore
    return eval(
        compile(tree, "<expression>", "eval"),
    )


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
        "name": "plasma_functions",
        "default": [
            ["sin", "s/2*x", "0.3"],
            ["cos", "y", "0.5"],
            ["sin", "x+(y/4)+t", "0.2"],
            ["cos", "y+(x/4)", "s/p"]
        ],
        "headers": {
            "columns": ["sin/cos", "function", "amplitude"]
        },
        "description":
            "The final plasma function will be the sum of these rows. Each row is either +/- cos or sin(your function here) / amplitude. "
            "This is all about interference patterns and wrapping around a clamped 0-255 color palette."
            "You can use /*+- for division, multiplication, etc. with any valid numbers, int or float, x for the current x position, y for the current y position, p for pi, t for a scaled time component, w for the buffer width, h for the buffer height. "
            "The first field is whether it's sin or cos, the second is your function, the third is roughly the periodicity of this function which itself can be a function.",
        "pre_validator": lambda v: re.sub(r'\s', '', v),
        "column_validators": {
            # column 0, +/- sin/cos
            0: lambda v: re.search(r'\s*-?(sin|cos)\s*', v, re.IGNORECASE),
            # column 1, 2, parse_expression
            "default": lambda v: parse_expression(v) is not None
        },
        "row_factory": lambda: list(["sin", "0", "1"])
    },
    {
        "name": "color_weights",
        "default": [
            [  0,   0,  50, 10],
            [  0,  25, 100, 10],
            [  0,  75, 200, 10],
            [ 75, 100, 200, 20],
            [255, 255, 255, 10],
            [  0,   0,  50, 40],
        ],
        "headers": {
            "columns": ["red", "green", "blue", "end at percentage"]
        },
        "description": (
            "An array of pairs of RGB value vectors (0-255 per channel) and the percentage that each color should start at in the resulting linear 256 color palette. "
            "If you want a smooth wrap, you should probably end with a gradient up to the last color that matches the first color. "
            "The color palette percentages need to add up to 100.0"
        ),
        "validator": lambda v: np.isclose(sum(i[3] for i in v), 100.0) and all(lambda i: i<=255 and i>=0 for i in v[0:3])
    },
])


def parse_sine_part(sine_part_string: str) -> Callable[[np.ndarray, np.ndarray, np.float32, np.float32, np.float32, np.float32], np.float32]:
    expression = parse_expression(sine_part_string)

    assert expression is not None

    compiled_function = compile_expression(expression)

    return lambda x, y, s, t, w, h: compiled_function(x, y, s, t, w, h)


def nodiv0(value: np.floating) -> np.floating:
    '''For guarding against divide by zero without breaking the numpy performance magic
    and bonus cast to float. np.sign returns 0 for 0, so that's going to break, hence the np.where
    '''
    return np.where(value < 0, -1.0, 1.0) * np.maximum(0.00001, np.abs(value))


def build_plasma_row_function(row) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    '''
    Using [sincos_expression, function_expression, amplitude_expression]
    Turns ["-sin", "x + 2.0 * -t / 3.14159", "4.0"]
    Into lambda x, y: -np.sin(x + 2.0 * -t / 3.14159) / nodiv0(4.0)
    '''
    sincos_val, user_function_val, amplitude_value = map(lambda i: re.sub(r'\s*', '', i).lower(), row)
    user_function = parse_sine_part(user_function_val)
    amplitude = parse_sine_part(amplitude_value)

    sincos_sign = np.float32(-1.0 if sincos_val[0] == '-' else 1.0)
    sincos = np.sin if sincos_val == 'sin' else np.cos
    
    s = lambda: np.sin(pygame.time.get_ticks() * float(PARAMETERS.time_scale) % (2.0 * np.pi))
    t = lambda: np.float32(pygame.time.get_ticks() * float(PARAMETERS.time_scale) % (2.0 * np.pi))
    w = np.float32(PARAMETERS.width.value)
    h = np.float32(PARAMETERS.height.value)

    return lambda x, y: (
        sincos_sign * sincos(user_function(x, y, t(), s(), w, h))
            * amplitude(x, y, t(), s(), w, h))


def build_plasma_function() -> Callable[[np.ndarray, np.ndarray], np.ndarray | np.floating]:
    fn = []

    for row in PARAMETERS.plasma_functions.value:
        fn.append(build_plasma_row_function(row))

    return lambda x, y: sum((v(x, y) for v in fn), start=np.float32(0.0))


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

    palette = build_palette()

    intermediate_map = np.zeros((PARAMETERS.height, PARAMETERS.width))

    # render target with chonky pixel size
    intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))

    first_run = True
    plasma_function: Callable[[np.ndarray, np.ndarray], np.ndarray | np.floating]|None = None

    # we're waiting until we hit the next frame timing to hit a 30fps target framerate
    while harness.tick(30):
        if PARAMETERS.color_weights.is_dirty():
            palette = build_palette()
            PARAMETERS.color_weights.clean()

        # if we've changed the dimensions in the parameters window, we have to regen the surface, the intermediate map, and the ogrid, and the scaling factors in the plasma function
        if first_run or PARAMETERS.height.is_dirty() or PARAMETERS.width.is_dirty() or PARAMETERS.plasma_functions.is_dirty():
            first_run = False
            intermediate_surface = pygame.Surface((PARAMETERS.width, PARAMETERS.height))
            PARAMETERS.height.clean() 
            PARAMETERS.width.clean()

            plasma_function = build_plasma_function()
            PARAMETERS.plasma_functions.clean()

            # some wild shit I don't fully understand - numpy has got "broadcast" features that are supposed to make
            # complex matrix operations super efficient, but they let you do something like `five_thousand_dimensional_matrix * 3.0`
            # and have it actually work. Considering we don't care what the buffer actually contains, and we're just looking for 
            # a numbered range of x, y that numpy can use to broadcast a function across an array, ogrid basically gives you 
            # a numpy array of arange(0, height) as a column (1, height) and a numpy arange of (0, width) as a row (width, 1)
            # then does a matrix multiplication operation, but instead of for (x,y) == (3,4) doing 3 * 4, it does f(3,4)
            # when we use it in our plasma_function()
            # basically you can treat the x and y parameters as telling numpy "build the damned loop yourself, do this for every x and y"
            # Apparently there's also an mgrid, but it'll build the full width * height array for *both width and height* which seems wasteful
            # given that we don't care about anything other than the row number and column number.  Apparently this flavor is vastly more
            # performant than just looping too, because it's all happening in the numpy sorcery layer instead of in Python
            # The weird 1j is apparently the python version of `i`, the imaginary number, and turning that parameter into
            # a complex number is bullshit numpy shorthand for "treat this slice parameter as a sample count instead of slice size"
            y, x = np.ogrid[
                0:2*np.pi:PARAMETERS.height.value*1j, 
                0:2*np.pi:PARAMETERS.width.value*1j
            ]

        # Do the actual plasma function
        # palette midpoint offset + gamut width * (weighted sum of position and time dependent (co)sine functions)
        intermediate_map = 0.5 + 1 * plasma_function(x, y) # pyright: ignore[reportOptionalCall,reportPossiblyUnboundVariable]

        # turn the intermediate map into a paletted image and blit it to our intermediate render surface
        pygame.surfarray.blit_array(
            intermediate_surface, 
            # do palette lookup for whole array
            palette[(intermediate_map*255).astype(np.uint8)]
            # then swap width/height because, though it hardly matters here
            .transpose((1, 0, 2)))

        # then blit/scale the render surface to our actual window surface
        pygame.transform.scale(intermediate_surface, harness.screen.get_size(), harness.screen)

        # then flip the double buffer
        pygame.display.flip()
