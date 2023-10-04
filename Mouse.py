import typing as t
import pygame


class CursorIcons:
    def __init__(self):
        self.cursor_data: t.Tuple[t.Union[int, t.Tuple[t.Tuple[int, int], t.Tuple[str, ...]]],
                                  ...] = (pygame.SYSTEM_CURSOR_ARROW, pygame.SYSTEM_CURSOR_IBEAM,
                                          ((0, 0),
                                           ("XX                      ",
                                            "X.X                     ",
                                            "X..X                    ",
                                            "X...X                   ",
                                            "X....X                  ",
                                            "X.....X                 ",
                                            "X......X                ",
                                            "X.......X               ",
                                            "X........X              ",
                                            "X.........X             ",
                                            "X......XXXXX            ",
                                            "X...X..X                ",
                                            "X..XX..X                ",
                                            "X.X  X..X               ",
                                            "XX   X..X               ",
                                            "X     X..X              ",
                                            "      X..X              ",
                                            "       X..X             ",
                                            "   X X X..XX X XX       ",
                                            "    X X XXX X X         ",
                                            "   X           XX       ",
                                            "    X         X         ",
                                            "   X           XX       ",
                                            "    X         X         ",
                                            "   X           XX       ",
                                            "    X X X X X X         ",
                                            "   X X X X X X XX       ",
                                            "                        ",
                                            "                        ",
                                            "                        ",
                                            "                        ",
                                            "                        ")))
        self.cursor_objects = []

    def get_number_of_cursors(self) -> int:
        return len(self.cursor_data)

    def init_cursors(self) -> None:
        for cursor in self.cursor_data:
            if isinstance(cursor, int):
                self.cursor_objects.append(pygame.cursors.Cursor(cursor))
            elif isinstance(cursor, tuple):
                cursor_string = cursor[1]
                cursor_bytes = pygame.cursors.compile(cursor_string)
                self.cursor_objects.append(pygame.cursors.Cursor((len(cursor_string[0]), len(cursor_string)),
                                                                 cursor[0],
                                                                 *cursor_bytes))

    def get_cursor(self, index: int = 0) -> pygame.cursors.Cursor:
        if 0 <= index < len(self.cursor_objects):
            return self.cursor_objects[index]


class Cursor(pygame.sprite.Sprite):
    # Cursor class used for Mask collision detection between the mouse cursor and a Sprite group.
    def __init__(self):
        super().__init__()
        # Stores the button state of each mouse button, in the form of [button1, button2, button3]
        self.buttons = [False] * 3
        self.scroll_amount = [0, 0]  # (x, y)
        # Used to determine if the mouse hover event should continue to pass down to the next lower z-level
        self.z_index = 1
        self.leave = False
        self.x = 0
        self.y = 0
        self.width = 1
        self.height = 1
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.mask = pygame.mask.Mask(size=(self.width, self.height), fill=True)

    def copy(self):
        new_cur = Cursor()
        new_cur.buttons = self.buttons.copy()
        new_cur.z_index = self.z_index
        new_cur.set_pos(self.x, self.y)
        new_cur.scroll_amount = self.scroll_amount.copy()
        if self.leave:
            new_cur.mask.clear()
            new_cur.leave = True
        return new_cur

    def reset_z_index(self) -> None:
        self.z_index = 1

    def increment_z_index(self) -> None:
        self.z_index += 1

    def get_z_index(self) -> int:
        return self.z_index

    def set_pos(self, new_x: int, new_y: int) -> None:
        if not self.leave:  # Ignore position update if the mouse cursor is not within the window.
            self.x = new_x
            self.y = new_y
            self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def get_pos(self) -> t.Tuple[int, int]:
        return self.x, self.y

    def set_button_state(self, button_number: int, state: bool) -> None:
        """Sets the state of a mouse button.

        E.g. To click mouse button 1: `set_button_state(1, True)`
        """
        if button_number <= len(self.buttons):
            self.buttons[button_number - 1] = state

    def get_button_state(self, button_number: int) -> bool:
        if button_number <= len(self.buttons):
            return self.buttons[button_number - 1]

    def reset_scroll(self) -> None:
        self.scroll_amount = [0, 0]

    def push_scroll(self, x_amount, y_amount) -> None:
        if not self.leave:
            self.scroll_amount[0] += x_amount
            self.scroll_amount[1] += y_amount

    def get_scroll(self, direction: t.Literal["vertical", "horizontal"]) -> int:
        return self.scroll_amount[1] if direction == "vertical" else self.scroll_amount[0]

    def mouse_enter(self) -> None:
        self.mask.fill()
        self.leave = False

    def mouse_leave(self) -> None:
        """Should be called when the mouse cursor exits the window."""
        self.set_pos(-1, -1)
        self.mask.clear()
        self.scroll_amount = [0, 0]
        self.leave = True
        if any(self.buttons):
            for i in range(len(self.buttons)):
                self.buttons[i] = False

    def has_left(self) -> bool:
        return self.leave
