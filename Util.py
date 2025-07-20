"""Miscellaneous functions and classes that are useful throughout the project."""
from string import ascii_uppercase
from contextlib import suppress
import numpy as np
import typing as tp
from os import path
import math
import Time
import platform
import functools
import subprocess
import pygame.transform
with suppress(ImportError):
    from ctypes import windll
COLORS = {"WHITE": (255, 255, 255),
          "RED": (255, 0, 0),
          "ORANGE": (255, 160, 20),
          "YELLOW": (222, 216, 149),
          "GREEN": (202, 255, 112),
          "BLUE": (26, 134, 219),
          "CYAN": (112, 197, 206),
          "PURPLE": (177, 29, 209),
          "GREY1": (240, 240, 240),
          "GREY2": (218, 218, 218),
          "GREY3": (209, 209, 209),
          "GREY4": (205, 205, 205),
          "GREY5": (166, 166, 166),
          "GREY6": (96, 96, 96),
          "GREY7": (72, 72, 72),
          "BLACK": (0, 0, 0),
          "TRANSPARENT": (1, 1, 1)}
folder_name = "Bubble Shooter"
global_app_data = {"Windows": "%programdata%/{}".format(folder_name),
                   "Darwin": "/Library/{}".format(folder_name),
                   "Linux": "/var/lib/{}".format(folder_name)}
user_app_data = {"Windows": "%appdata%/{}".format(folder_name),
                 "Darwin": "~/Library/{}".format(folder_name),
                 "Linux": "~/.{}".format(folder_name.lower().replace(" ", "_"))}
temp_path = {"Windows": "%temp%",
             "Darwin": ".",  # Need to research
             "Linux": "/var/tmp"}
current_os = platform.system()


class SinWave:
    def __init__(self, **coefficients: tp.Union[int, float]):
        """Customizable sin wave in the form of **y = a×sin(b×x − c) + d** that uses time as input. The coefficients
        can be modified after constructed if needed.

        :param coefficients: Can contain values to use for a, b, c, and d.
        """
        self.coefficients = coefficients
        self._timer = Time.Time()
        self._timer.reset_timer()

    def get_value(self) -> float:
        a, b, c, d = (self.coefficients.get(var, 1 - i // 2) for i, var in enumerate("abcd"))
        x = self._timer.get_time()
        period = self.get_period()
        value = a * math.sin(b * x - c) + d
        self._timer.force_elapsed_time(x % period)  # Keeps sin wave within the first period.
        return value

    def get_magnitude(self, half: bool = False) -> tp.Union[int, float]:
        a = self.coefficients.get("a", 1)
        return a if half else 2 * a

    def get_period(self) -> float:
        b = self.coefficients.get("b", 1)
        return (2 * math.pi) / abs(b)

    @staticmethod
    def sin_between_two_pts(pt1: tp.Union[int, float], pt2: tp.Union[int, float], freq: tp.Union[int, float] = 1,
                            h_shift: tp.Union[int, float] = 0) -> "SinWave":
        """Constructs a sin wave whose highest and lowest point stops at the two points given."""
        a, b, c = abs(pt2 - pt1) / 2, freq, h_shift
        d = max(pt1, pt2) - a
        return SinWave(a=a, b=b, c=c, d=d)


def get_platform_data_path(purpose: tp.Literal["global", "user"]) -> str:
    location = ""
    if purpose == "global":
        location = global_app_data.get(current_os, global_app_data["Linux"])
    elif purpose == "user":
        location = user_app_data.get(current_os, user_app_data["Linux"])
    return path.expandvars(path.expanduser(path.normpath(location)))


def get_temp_path() -> str:
    return path.expandvars(path.normpath(temp_path.get(current_os, temp_path["Linux"])))


def find_abs_path(rel_path: str) -> str:
    """Returns absolute version of the relative path given regardless of working directory."""
    return path.abspath(path.join(path.dirname(__file__), path.normpath(rel_path)))


def collide_function(sprite1: pygame.sprite.Sprite, sprite2: pygame.sprite.Sprite) -> bool:
    result = pygame.sprite.collide_mask(sprite1, sprite2)
    return result is not None


def resize_surf(display_surf: pygame.Surface,
                size: tp.Union[tp.List[tp.Union[int, float]], tp.Tuple[tp.Union[int, float], tp.Union[int, float]]],
                size_only: bool = False) -> tp.Union[pygame.Surface,
                                                     tp.Tuple[tp.Union[int, float], tp.Union[int, float]]]:
    current_size = display_surf.get_size()
    if current_size[0] * (size[1] / current_size[1]) < size[0]:
        new_size = (current_size[0] * (size[1] / current_size[1]), size[1])
    else:
        new_size = (size[0], current_size[1] * (size[0] / current_size[0]))
    if size_only:
        return new_size
    else:
        return pygame.transform.scale(display_surf, new_size)


def dilate_coordinates(pos: tp.Tuple[int, int], fixed_size: tp.Tuple[int, int], current_size: tp.List,
                       resized_surf: tp.Tuple[int, int]) -> tp.Tuple[float, float]:
    offset_pos = ((current_size[0] - resized_surf[0]) / 2, (current_size[1] - resized_surf[1]) / 2)
    return (offset_pos[0] + (resized_surf[0] * (pos[0] / fixed_size[0])),
            offset_pos[1] + (resized_surf[1] * (pos[1] / fixed_size[1])))


def resize_mouse_pos(pos: tp.Tuple[int, int],
                     fixed_size: tp.Tuple[int, int],
                     current_size: tp.List,
                     resized_surf: tp.Tuple[int, int]) -> tp.Tuple[float, float]:
    offset_pos = (pos[0] - ((current_size[0] - resized_surf[0]) / 2),
                  pos[1] - ((current_size[1] - resized_surf[1]) / 2))
    return (fixed_size[0] * (offset_pos[0] / resized_surf[0])), \
           (fixed_size[1] * (offset_pos[1] / resized_surf[1]))


def draw_rounded_rect(surface: pygame.Surface,
                      pos: tp.Tuple[int, int],
                      size: tp.Tuple[tp.Union[int, float], tp.Union[int, float]],
                      radius: int,
                      color: tp.Tuple[int, int, int]) -> None:
    positions = ([pos[0] + radius, pos[1] + radius],
                 [pos[0] + size[0] - radius, pos[1] + radius],
                 [pos[0] + radius, pos[1] + size[1] - radius],
                 [pos[0] + size[0] - radius, pos[1] + size[1] - radius])
    for position in positions:
        pygame.draw.circle(surface, color, position, radius, 0)
    pygame.draw.rect(surface, color, [pos[0], pos[1] + radius, size[0], size[1] - radius * 2], 0)
    pygame.draw.rect(surface, color, [pos[0] + radius, pos[1], size[0] - radius * 2, size[1]], 0)


def draw_button(surface: pygame.Surface,
                x: int,
                y: int,
                width: int,
                height: int,
                border: int,
                fg: tp.Tuple[int, int, int],
                bg: tp.Tuple[int, int, int],
                font: pygame.font.Font,
                text: str) -> None:
    current_size = font.size(text)
    new_size = (width - height - border * 2, height - border * 2)
    text_surf = font.render(text, True, fg)
    if current_size[0] * (new_size[1] / current_size[1]) < new_size[0]:
        text_width = current_size[0] * (new_size[1] / current_size[1])
        text_height = new_size[1]
    else:
        text_width = new_size[0]
        text_height = current_size[1] * (new_size[0] / current_size[0])
    text_surf = pygame.transform.scale(text_surf, (text_width, text_height))
    corner_radius = height / 2
    positions = ([x + corner_radius, y + corner_radius],
                 [x + width - corner_radius, y + corner_radius])
    for position in positions:
        pygame.draw.circle(surface, COLORS["BLACK"], position, corner_radius, 0)
    pygame.draw.rect(surface, COLORS["BLACK"], [x + corner_radius, y, width - corner_radius * 2, height], 0)
    positions = ([x + corner_radius + border, y + corner_radius],
                 [x + width - corner_radius - border, y + corner_radius])
    for position in positions:
        pygame.draw.circle(surface, bg, position, corner_radius - border, 0)
    pygame.draw.rect(surface, bg, [x + corner_radius + border, y + border, width - corner_radius * 2 - border * 2,
                                   height - border * 2], 0)
    surface.blit(text_surf, (surface.get_size()[0] / 2 - text_width / 2, surface.get_size()[1] / 2 - text_height / 2))


def draw_vtp_rounded_rect(surface: pygame.Surface,
                          pos: tp.Tuple[int, int],
                          size: tp.Tuple[int, int],
                          color: tp.Tuple[int, int, int]) -> None:
    # v.t.p. = vertical two-point
    y_positions = (pos[1] + size[0] / 2, pos[1] + size[1] - size[0] / 2)
    for y in y_positions:
        pygame.draw.circle(surface, color, (pos[0] + size[0] / 2, y), size[0] / 2)
    pygame.draw.rect(surface, color, (pos[0], pos[1] + size[0] / 2, size[0], size[1] - size[0]), 0)


def draw_triangle(surface: pygame.Surface,
                  pos: tp.Tuple[int, int],
                  size: tp.Tuple[int, int],
                  color: tp.Tuple[int, int, int],
                  direction: tp.Literal["up", "down", "left", "right"]) -> None:
    # Draws upward triangle if flip is False.
    if direction == "up":
        vertices = ((pos[0], pos[1] + size[1] - 1), (pos[0] + size[0] - 1, pos[1] + size[1] - 1),
                    (pos[0] + size[0] / 2, pos[1]))
    elif direction == "down":
        vertices = ((pos[0], pos[1]), (pos[0] + size[0] - 1, pos[1]),
                    (pos[0] + size[0] / 2, pos[1] + size[1] - 1))
    elif direction == "left":
        vertices = ((pos[0], pos[1] + size[1] / 2), (pos[0] + size[0], pos[1]), (pos[0] + size[0], pos[1] + size[1]))
    else:
        vertices = ((pos[0], pos[1]), (pos[0] + size[0], pos[1] + size[1] / 2), (pos[0], pos[1] + size[1]))
    pygame.draw.polygon(surface, color, vertices)


def draw_arrow(surface: pygame.Surface, color: tp.Tuple[int, int, int],
               pos: tp.Tuple[tp.Union[int, float], tp.Union[int, float]], size: tp.Tuple[int, int],
               direction: tp.Literal["up", "down", "left", "right"], thickness: int) -> None:
    if direction == "up":
        vertices = ((pos[0], pos[1] + size[1]), (pos[0] + size[0] / 2, pos[1]), (pos[0] + size[0], pos[1] + size[1]))
    elif direction == "down":
        vertices = ((pos[0], pos[1]), (pos[0] + size[0] / 2, pos[1] + size[1]), (pos[0] + size[0], pos[1]))
    elif direction == "left":
        vertices = ((pos[0] + size[0], pos[1]), (pos[0], pos[1] + size[1] / 2), (pos[0] + size[0], pos[1] + size[1]))
    else:
        vertices = ((pos[0], pos[1]), (pos[0] + size[0], pos[1] + size[1] / 2), (pos[0], pos[1] + size[1]))
    pygame.draw.lines(surface, color, False, vertices, width=thickness)


def draw_cross(surface: pygame.Surface,
               pos: tp.Tuple[int, int],
               size: tp.Tuple[int, int],
               width: int,
               color: tp.Tuple[int, int, int]) -> None:
    lines = ((pos, (pos[0] + size[0] - 1, pos[1] + size[1] - 1)),
             ((pos[0] + size[0] - 1, pos[1]), (pos[0], pos[1] + size[1] - 1)))
    for line in lines:
        pygame.draw.line(surface, color, line[0], line[1], width=width)


@tp.overload
def rgb_to_hex(color: tp.Union[tp.Tuple[int, int, int], tp.Tuple[int, int, int, int]],
               return_: tp.Type[str], upper: tp.Optional[bool] = False) -> str:
    pass


@tp.overload
def rgb_to_hex(color: tp.Union[tp.Tuple[int, int, int], tp.Tuple[int, int, int, int]],
               return_: tp.Type[int]) -> int:
    pass


@functools.lru_cache
def rgb_to_hex(color: tp.Union[tp.Tuple[int, int, int], tp.Tuple[int, int, int, int]],
               return_: tp.Type[tp.Union[str, int]], upper: tp.Optional[bool] = False) -> tp.Union[str, int]:
    """Converts a tuple of integers representing an RGB color to the type given to 'return_'. If 'return_' is given
    'str', the color is converted to a string representing a hex code. If given 'int', an integer with the same value
    as the hex representation of the color is returned."""
    if return_ is str:
        return ("%02{}".format("X" if upper else "x") * len(color)) % color
    # TODO: Improve 'rgb_to_hex' and 'hex_to_rgb':
    #  rgb: Tuple[int, int, int], Tuple[int, int, int, int]
    #  hex: str (RRGGBB), int (hex literal)


@functools.lru_cache
def hex_to_rgb(hex_color: tp.Union[str, int]) -> tp.Union[tp.Tuple[int, int, int], tp.Tuple[int, int, int, int]]:
    """Converts a string hex color to a tuple of integers. The string should not be prefixed with a hash symbol.
    If the hex color is a numeric or hexadecimal number, first use the 'hex' builtin function to convert it to a string.
    """
    if isinstance(hex_color, int):
        hex_color = "%08x" % hex_color
    # noinspection PyTypeChecker
    return tuple(int(hex_color[chl:chl + 2], base=16) for chl in range(0, len(hex_color), 2))


def decode_rgb_array(mapped_array: np.ndarray) -> np.ndarray:
    @np.vectorize(doc="Accepts a 2D numpy array of numeric literals representing hex colors, and returns a tuple of "
                      "four 2D arrays representing each decoded color channel.",
                  otypes=[int],
                  signature="()->(n)")  # noqa
    def decode_rgb_channels(hex_: int) -> np.ndarray:
        """Takes a hexadecimal number representing an RGB color and decodes it to a 4-item tuple representing the RGBA
        channels. If the number given doesn't include the 'alpha' channel, it would be `0` in the returned tuple."""
        print(hex_)
        str_hex = hex(hex_)[2:]  # the slice is for stripping the "0x" prefix.
        if len(str_hex) == 6:  # hex literal is in the form of `RRGGBB` instead of `RRGGBBAA`
            str_hex += "ff"  # append `AA` to end of `RRGGBB` value
        color = np.array(hex_to_rgb(str_hex))
        print("color", color)
        return color
    # `np.concatenate((a[:, :, np.newaxis], b[:, :, np.newaxis]), axis=2)` = make the innermost dimensions (the
    # scalar data) of both 'a' and 'b' one-item arrays, and then concatenate at the innermost dimension
    channels = decode_rgb_channels(mapped_array)  # noqa
    print(channels)
    return channels
    # return np.concatenate(tuple(arr[:, :, np.newaxis] for arr in decode_rgb_channels(mapped_array)), axis=2)  # noqa


def word_wrap_text(string: str, width: int, font: pygame.font.Font, br: str = "-") -> tp.List[str]:
    lines, break_locations = [[]], []
    for index, char in enumerate(string):
        if char == " ":
            break_locations.append(len(lines[-1]))
            lines[-1].append(char)
            continue
        elif char == "\n":
            break_locations.clear()
            lines.append([])
            continue
        if font.size("".join(lines[-1] + [char, br]))[0] <= width:
            lines[-1].append(char)
        else:
            if break_locations:
                last_word = lines[-1][break_locations[-1] + 1:]
                lines[-1] = lines[-1][:break_locations[-1]]
                break_locations.clear()
                lines.append(last_word)
                lines[-1].append(char)
            else:
                if lines and lines[-1]:
                    if lines[-1][-1].isascii():  # Chinese characters do not need a dash on line-breaking.
                        lines[-1].append(br)
                lines.append([char])
    return ["".join(line) for line in lines]


def launch_file_mgr(file_path: str) -> None:
    """Attempts to open the platform's file manager with the specified file or directory highlighted."""
    with suppress(OSError, subprocess.SubprocessError):
        if current_os == "Windows":
            # Start an explorer instance and hide its output (if any)
            # Helpful info found from here: https://www.geoffchappell.com/studies/windows/shell/explorer/cmdline.htm
            if file_path == "\\\\?\\":
                subprocess.Popen("explorer ,", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen("explorer /select,\"{}\"".format(file_path),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif current_os == "Mac":
            # Untested, but hopefully works.
            subprocess.Popen(["open", "-R", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif current_os == "Linux":
            # 'xdg-open' seems to actually open the file with the associated application instead of just highlighting
            # it, so only allow a path that points to a directory, not a file.
            if path.isdir(file_path):
                subprocess.Popen(["xdg-open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def get_drive_letters() -> tp.Optional[tp.List[str]]:
    """Returns all available drive letters. Returns a list on success, or None on error. Only works on Windows."""
    if current_os != "Windows":
        return None
    drives = []
    try:
        bitmask = windll.kernel32.GetLogicalDrives()
    except (OSError, AttributeError):
        return None
    for letter in ascii_uppercase:
        if bitmask & 1:
            drives.append("{}:\\".format(letter))
        bitmask >>= 1
    return drives


def show_messagebox(title_text: str, body_text: str, bitmask: int) -> None:
    """Displays a native Win32 message-box. Only works on Windows."""
    if current_os != "Windows":
        return None
    window_data = pygame.display.get_wm_info()
    windll.user32.MessageBoxW(window_data["window"], body_text, title_text, bitmask)


def configure_dpi() -> None:
    """If current OS is Windows, attempts to configure the Python process to be DPI aware."""
    if current_os == "Windows":
        if not post_win8_config_dpi():
            pre_win8_config_dpi()


def post_win8_config_dpi() -> bool:
    try:
        windll.shcore.SetProcessDpiAwareness(2)
    except (NameError, OSError, AttributeError):
        return False
    else:
        return True


def pre_win8_config_dpi() -> bool:
    try:
        windll.shcore.SetProcessDPIAware()
    except (NameError, OSError, AttributeError):
        return False
    else:
        return True


def output_3d_array(arr: np.ndarray) -> None:
    """Outputs the full contents of a 3D array with the same row of pixels on the same row in the output."""
    print("[", end="")
    rows = arr.shape[0]
    cols = arr.shape[1]
    if len(arr.shape) < 3:
        formatter = lambda x: "%6.2f" % x  # noqa
    elif arr.shape[-1] == 2:
        formatter = lambda x: "[%3d %3d]" % tuple(x)  # noqa
    else:
        formatter = lambda x: "[%3d %3d %3d]" % tuple(x)  # noqa
    for r in range(rows):
        for c in range(cols):
            print(formatter(arr[r][c]), end=" " if c < cols - 1 else "")
        print(end="\n\x20" if r < rows - 1 else "]\n")


if __name__ == "__main__":
    color_2d = np.array(((0x000001, 0x000002, 0x000003),
                         (0x000004, 0x000005, 0x000006),
                         (0x000007, 0x000008, 0x000009)))
    color_3d = decode_rgb_array(color_2d)
