#!/usr/bin/env python3
import Env
import typing as tp
from Util import configure_dpi
from Dialogs import file_dialog
from Game import MainLoop, GAME_MIN_RES
import pygame
import argparse
del Env
configure_dpi()
# pygame.mixer.init = lambda: exec("raise pygame.error")


def video_setup(title: str,
                window_res: tp.Tuple[int, int]) -> tp.Tuple[pygame.Surface, tp.Tuple[int, int], tp.Tuple[int, int],
                                                            tp.Dict[str, str]]:
    modules = {"display": "The application could not start because the video system failed to initialize.",
               "font": "The application could not start because the font rendering engine failed to initialize.",
               "mixer": "The sound system failed to initialize! This may be due to a problematic driver or hardware "
                        "malfunction. The game will not attempt to play any sounds until the next restart."}
    required = ("display", "font")
    errors = {}
    for m in modules:
        try:
            getattr(pygame, m).init()
        except pygame.error:
            err_msg = modules[m]
            if m in required:
                raise RuntimeError(err_msg)
            else:
                errors[m] = err_msg
    display_info = pygame.display.Info()
    hardware_res = (display_info.current_w, display_info.current_h)
    pygame.display.set_caption(title)
    screen = pygame.display.set_mode(window_res, pygame.RESIZABLE)
    return screen, hardware_res, window_res, errors


def main(window_res: tp.Tuple[int, int] = GAME_MIN_RES) -> None:
    MainLoop(*video_setup("Bubble Shooter", window_res))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entry point of this game. The game itself also starts subprocesses "
                                                 "of itself from this file. Will start the game if run with no args.")
    subparsers = parser.add_subparsers(help="Sub-command to pass command-line arguments into. Put the '-h' flag "
                                            "*after* the sub-command to get help on it.")
    filedialog = subparsers.add_parser("filedialog", help="Displays a file-dialog instead of running the game. This "
                                                          "dialog is used by the game itself.")
    filedialog.add_argument("title", type=str, help="The title of the file-dialog.")
    filedialog.add_argument("mode", type=str, choices=["open_file", "save_file"], help="What mode to open the "
                                                                                       "file-dialog in.")
    filedialog.add_argument("--ext_labels", action="extend", nargs="*", default=["All Files"], type=str,
                            help="Adds a file-type label to the dropdown that will be displayed in the dialog. Can have"
                                 " multiple arguments (which will add multiple items to the list), and can be used "
                                 "multiple times.")
    filedialog.add_argument("--ext_patterns", action="extend", nargs="*", default=["*.*"], type=str,
                            help="Adds a file-extension pattern to the types of files that the dialog will display. "
                                 "Behaves in the same way as '--ext_labels'. The number of items passed to "
                                 "'--ext_labels' and '--ext_patterns' should be equal. A label and pattern at the same "
                                 "index will belong to the same file.")
    args = parser.parse_args()
    if vars(args):
        f_path = file_dialog(args.title, args.mode, args.ext_labels, args.ext_patterns)
        if f_path is not None:
            print(f_path, end="")
    else:
        main()
