import pygame


class Harness:
    """
    So the only thing a demo has to care about is that it has a screen to target and a clock to tick
    doesn't have to handle pygame exit or anything of the sort
    """
    screen: pygame.Surface
    clock: pygame.Clock
    _exit: bool = False


    def __init__(self, screen: pygame.Surface) -> None:
        self.clock = pygame.Clock()
        self.screen = screen

    @property
    def exit(self) -> bool:
        return self._exit

    @exit.setter
    def exit(self, value: bool):
        self._exit = value

    def tick(self, target_fps):
        for event in pygame.event.get():
            if event.type == pygame.QUIT or \
               (event.type == pygame.KEYDOWN
                and event.key == pygame.K_c
                and event.mod & pygame.KMOD_CTRL):
                    self.exit = True

        self.clock.tick(target_fps)
        return not self.exit
