import pygame.time


class Time:
    def __init__(self):
        self.timer = 0
        self.previous_result = 0
        self.paused = False

    def reset_timer(self) -> None:
        self.timer = pygame.time.get_ticks() / 1000
        self.previous_result = 0

    def get_time(self) -> float:
        if not self.paused:
            self.previous_result = pygame.time.get_ticks() / 1000 - self.timer
        return self.previous_result

    def force_elapsed_time(self, value: float) -> None:
        self.timer = pygame.time.get_ticks() / 1000 - value

    def pause(self) -> None:
        self.paused = True

    def unpause(self) -> None:
        if self.paused:
            self.paused = False
            self.force_elapsed_time(self.previous_result)

    def is_paused(self) -> bool:
        return self.paused

    def get_prev_time(self) -> float:
        return self.previous_result
