from argparse import ArgumentParser
from typing import Callable

import pygame

import tomdemos
import tomdemos.common


# new exception type so I don't end up accidentally catching unexpected ValueErrors
class Help(ValueError): pass


# Overkill, just getting the first positional argument
def parse_args():
    parser = ArgumentParser()
    parser.add_argument("demo", default="help")
    return parser.parse_args()


# __all__ is an actual conventional dunder value, not just some sauce I cooked up
# it's only by convention, but it explicitly enumerates the intentional exports of a module
def available_demos():
    return tomdemos.__all__


# adding a type hint to keep my type checking happy - this will always contain a demo function/method that take a harness as the only positional argument
def load_demo_module(demo_name: str) -> Callable[[tomdemos.common.Harness,],None]:
    available = available_demos()

    if demo_name == "help" or demo_name not in available:
        raise Help()
    
    demo: Callable[[tomdemos.common.Harness,], None] = tomdemos.__dict__[demo_name]
    return demo

# pygame window setup, oldschool aspect ratio
def main_window() -> pygame.Surface:
    window_size = (800, 600)
    pygame.init()
    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("Demo Window")
    return screen


def main():
    demo_name = parse_args().demo

    try:
        # this will blow up by raising Help if it can't find the demo
        demo = load_demo_module(demo_name)

        # otherwise indicate we're trying
        print(f"Running demo: {demo_name} - Ctrl+C to exit")

        # make a new demo harness
        harness = tomdemos.common.Harness(main_window())

        # ...and running the demo's main loop
        demo(harness)

        # being lazy here and overloading keyboard interrupt to indicate we've intentionally exited the program 
        # either with Ctrl+C on the console which would get caught below anyway, or with bailing from the harness
        # with Ctrl+C in the pygame window or clicking the window close button
        if harness.exit:
            raise KeyboardInterrupt
    except Help:
        # can't find the demo or none was specified
        print(f"Available demos: {'\n- '.join([''] + available_demos())}")

    except KeyboardInterrupt:
        # every graceful exit
        print("\nExiting demo.")
