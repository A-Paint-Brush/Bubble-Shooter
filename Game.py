from Util import COLORS, find_abs_path
from functools import partial
import typing as tp
import Notifier
import Dialogs
import Storage
import Mouse
import Widgets
import pygame
GAME_MIN_RES = (641, 858)
DIALOG_MIN_RES = (943, 592)


class SpecialWidget:
    def __init__(self, special_widget: tp.Any):
        self.initialized = False
        self.special_widget = special_widget

    def resize_widget(self, new_size: tp.Tuple[int, int]) -> None:
        if issubclass(self.special_widget.__class__, Widgets.BaseOverlay):
            self.special_widget.resize(new_size)
        elif isinstance(self.special_widget, Dialogs.BusyFrame):
            self.special_widget.widgets["overlay"].resize(new_size)

    def fetch_for_update(self) -> tp.Any:
        if not self.initialized:
            self.initialized = True
        return self.special_widget

    def fetch_for_draw(self) -> tp.Optional[tp.Any]:
        if self.initialized:
            return self.special_widget
        else:
            return None


class BaseSetup:
    def __init__(self, screen: pygame.Surface, hardware_res: tp.Tuple[int, int], window_res: tp.Tuple[int, int]):
        # region Pygame Setup
        self.hardware_res = hardware_res
        self.window_res = window_res
        self.clock = pygame.time.Clock()
        self.screen = screen
        pygame.event.set_blocked(None)
        pygame.event.set_allowed((pygame.QUIT, pygame.WINDOWFOCUSLOST, pygame.WINDOWENTER, pygame.WINDOWLEAVE,
                                  pygame.VIDEORESIZE, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL,
                                  pygame.KEYDOWN, pygame.KEYUP, pygame.TEXTINPUT, pygame.TEXTEDITING,
                                  pygame.WINDOWMOVED))
        pygame.key.stop_text_input()
        # endregion


class MainLoop(BaseSetup):
    def __init__(self, screen: pygame.Surface, hardware_res: tp.Tuple[int, int], window_res: tp.Tuple[int, int],
                 err_modules: tp.Dict[str, str]):
        super().__init__(screen, hardware_res, window_res)
        self.og_res = window_res
        self.achmt_strs = Storage.AchievementData()
        self.achmt_db = Storage.AchievementDB(self.achmt_strs.get_achievement_len())
        self.achmt_strs.load_achievements(self.achmt_db.read_data(), self.achmt_db.set_achievement)
        # region Widget Setup
        self.special_widgets: tp.Dict[str, SpecialWidget] = {}  # For widgets that paint over all other objects.
        self.ui_mgr: tp.Optional[tp.Any] = None  # Holds class instances for managing more complicated page layouts.
        self.key_events: tp.List[pygame.event.Event] = []  # Holds events that the UI needs to know about.
        self.game_board: tp.Optional[Dialogs.LevelBoard] = None
        self.display_frame: tp.Optional[Widgets.Frame] = None  # The frame object holding all widgets.
        self.notifiers = Notifier.ToastGroup(self.window_res,
                                             {i: pygame.image.load(
                                                 find_abs_path("./Images/toast_icons/{}.png" .format(i)))
                                                 .convert_alpha()
                                              for i in ("info", "error", "trophy")}, z_index=1)
        # "mixer" in err_modules  # Sound not working
        for msg in err_modules.values():
            self.notifiers.create_toast("error", "Application Error", msg)
        self._wid = 1  # widget_id
        self.font = pygame.font.SysFont("arial", 40)
        self.busy_frame = Dialogs.BusyFrame(self.window_res, self.font, 100, 125, 19, 90, 250, (205, 205, 205),
                                            (26, 134, 219))
        # Z-order = 1: toast-group, 2: transition/load-frame, 3: top-levels, 4: widget-frame, 5:game sprites
        self.mouse_obj = Mouse.Cursor()
        # endregion
        # region Basic Variables
        self.current_scr = "title"
        self.full_screen = False
        self.resize_lock = False
        fps = 60
        game_run = True
        # endregion
        self.display_frame: tp.Optional[Widgets.Frame] = None
        self.title_init()
        while game_run:
            self.clock.tick(fps)
            self.key_events.clear()
            self.mouse_obj.reset_scroll()
            self.resized = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game_run = False
                elif event.type == pygame.WINDOWENTER:
                    self.mouse_obj.mouse_enter()
                elif event.type == pygame.WINDOWLEAVE:
                    self.mouse_obj.mouse_leave()
                elif event.type == pygame.VIDEORESIZE and not self.full_screen:
                    self.resized = True
                    # noinspection PyTypeChecker
                    self.window_res: tp.Tuple[int, int] = tuple(new_res
                                                                if new_res >= GAME_MIN_RES[i] else GAME_MIN_RES[i]
                                                                for i, new_res in enumerate((event.w, event.h)))
                    self.screen = pygame.display.set_mode(self.window_res, pygame.RESIZABLE)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.mouse_obj.set_button_state(event.button, True)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.mouse_obj.set_button_state(event.button, False)
                elif event.type == pygame.MOUSEWHEEL:
                    self.mouse_obj.push_scroll(event.x, event.y)
                elif event.type == pygame.WINDOWMOVED:
                    pass  # Reset delta time of the game if it is in a level
                elif event.type in (pygame.WINDOWFOCUSLOST, pygame.KEYDOWN, pygame.KEYUP, pygame.TEXTINPUT,
                                    pygame.TEXTEDITING):
                    self.key_events.append(event)
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_F11:
                            self.toggle_full_screen()
                        elif event.mod & pygame.KMOD_LALT:
                            if event.key == pygame.K_a:
                                self.special_widgets["transition"] = SpecialWidget(Widgets.
                                                                                   SceneTransition(self.window_res[0],
                                                                                                   self.window_res[1],
                                                                                                   400,
                                                                                                   lambda: print("Hi")))
                            elif event.key == pygame.K_b:
                                self.notifiers.create_toast("info", "Dev Test",
                                                            "Lorem ipsum dolor sit amet.\n>>> print(\"Hello, world!\")")
            # print("\r{}, {}".format(repr(self.ui_mgr), repr(self.special_widgets)), end="", flush=True)
            self.mouse_obj.set_pos(*pygame.mouse.get_pos())
            self.mouse_obj.reset_z_index()
            if self.ui_mgr is not None:
                if self.current_scr == "help":
                    _ = self.ui_mgr.update()
                    if not self.ui_mgr.is_loading() and "load_frame" in self.special_widgets:
                        self.special_widgets.pop("load_frame")
            # region z-index: 1
            self.notifiers.send_mouse_pos(self.mouse_obj)
            self.notifiers.update(self.hardware_res if self.full_screen else self.window_res if self.resized else None)
            # endregion
            # region z-index: 2
            if "transition" not in self.special_widgets and "load_frame" not in self.special_widgets:
                self.mouse_obj.increment_z_index()
            # endregion
            # region z-index: 3
            if self.special_widgets:
                for w_name in tuple(self.special_widgets.keys()):
                    widget = self.special_widgets[w_name].fetch_for_update()
                    if w_name == "transition":
                        return_code = widget.update()
                        if return_code == 2:
                            self.special_widgets.pop(w_name)
                    elif w_name == "load_frame":
                        widget.update(self.mouse_obj, self.key_events)
                    if self.resized:
                        self.special_widgets[w_name].resize_widget(self.window_res)
            else:
                self.mouse_obj.increment_z_index()
            # endregion
            # region z-index: 4
            if self.display_frame is not None:
                if self.resized:
                    self.display_frame.update_size(self.hardware_res if self.full_screen else self.window_res)
                self.display_frame.update(self.mouse_obj, self.key_events)
                if self.resize_lock:  # A widget managed by 'ui_mgr' requests a resize
                    self.display_frame.update_size(self.hardware_res if self.full_screen else self.window_res)
                    self.resize_lock = False
                    dummy_mouse = Mouse.Cursor()
                    dummy_mouse.mouse_leave()
                    # Update again so the extra resize request is processed.
                    self.display_frame.update(dummy_mouse, [])
            # endregion
            self.screen.fill(COLORS["CYAN"])
            # region render z-index: 4
            if self.display_frame is not None:
                self.screen.blit(self.display_frame.image, self.display_frame.rect)
            # endregion
            # region render z-index: 3 & 2
            widgets = list(self.special_widgets.keys())
            # Ensures that "transition" is the last items in the render list. "load_frame" will be just before it, if it
            # exists.
            for w in ("load_frame", "transition"):
                if w in widgets:
                    widgets.remove(w)
                    widgets.append(w)
            for w_name in widgets:
                widget = self.special_widgets[w_name].fetch_for_draw()
                if widget is None:
                    continue
                elif w_name == "transition":
                    self.screen.blit(widget.image, widget.rect)
                elif w_name == "load_frame":
                    widget.draw(self.screen)
            # endregion
            # region render z-index: 1
            self.notifiers.draw(self.screen)
            # endregion
            pygame.display.update()
        pygame.quit()

    def force_resize(self) -> None:
        self.resized = True
        self.resize_lock = True

    def reset_frame(self) -> None:
        self.display_frame = Widgets.Frame(0, 0, self.og_res[0], self.og_res[1], 20, z_index=4)
        self.wid = 1
        if self.ui_mgr is not None:  # Is this a good place to put it?
            self.ui_mgr = None
        self.resized = True

    def title_init(self) -> None:
        self.current_scr = "title"
        self.reset_frame()
        self.wid = Dialogs.v_pack_buttons(
            self.og_res, self.display_frame, ["Create Level", "Load Level", "Instructions", "Achievements"],
            [(290, 70), (250, 70), (250, 70), (290, 70)],
            [partial(self.start_transition, self.level_sys_init), lambda: None,
             partial(self.start_transition, self.help_init),
             partial(self.start_transition, self.achievement_init)], self.font, 10)[0]

    def help_init(self) -> None:
        self.current_scr = "help"
        self.reset_frame()
        self.ui_mgr = Dialogs.HelpManager(self.display_frame, self.og_res, self.font, self.force_resize,
                                          partial(self.start_transition, self.title_init))
        self.special_widgets["load_frame"] = SpecialWidget(self.busy_frame)

    def achievement_init(self) -> None:
        self.current_scr = "achievements"
        self.reset_frame()
        self.ui_mgr = Dialogs.AchievementManager(self.display_frame, self.og_res, self.font,
                                                 pygame.font.SysFont("arial", 25),
                                                 pygame.font.SysFont("arial", 23),
                                                 self.achmt_strs.get_achievement_string,
                                                 partial(self.start_transition, self.title_init))
        self.ui_mgr.update_data(self.achmt_strs.get_state_data())

    def level_sys_init(self) -> None:
        """Both loading a level and creating a new level from the title screen should go through this method to
        initialize the level data structure. After calling this function, proceed to initialize the display frame for
        the respective screen. If switching into the level editor when a level is already loaded, it is not needed to
        go through this method, since the level data structure would already be initialized."""
        if self.game_board is not None:
            return None
        self.current_scr = "game"
        self.reset_frame()
        self.game_board = Dialogs.LevelBoard(self.og_res, 9, 90, 20, z_index=4)
        self.display_frame.add_widget(self.game_board)
        self.game_board.toggle_editor()

    def scene_trans(self, call: tp.Callable) -> SpecialWidget:
        return SpecialWidget(Widgets.SceneTransition(self.window_res[0], self.window_res[1], 400, call))

    def start_transition(self, call_func: tp.Callable):
        self.special_widgets["transition"] = self.scene_trans(call_func)

    def add_achievement(self, index: int) -> None:
        self.resized = True
        self.achmt_strs.get_new_achievement(index)
        if self.current_scr == "achievements":
            self.ui_mgr.update_data(self.achmt_strs.get_state_data())

    @property
    def wid(self) -> int:
        value = self._wid
        self._wid += 1
        return value

    @wid.setter
    def wid(self, value: int) -> None:
        self._wid = value

    def toggle_full_screen(self) -> None:
        self.resized = True
        self.full_screen = not self.full_screen
        if self.full_screen:
            self.screen = pygame.display.set_mode(self.hardware_res, pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.window_res, pygame.RESIZABLE)
