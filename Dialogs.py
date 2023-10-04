"""Stores classes for managing screen layouts or pop-up dialogs."""
from collections import namedtuple
from tkinter import filedialog
import itertools as itools
import operator as op
import tkinter as tk
from Util import *
import itertools
import Storage
import Widgets
import getpass
import pygame
import copy
import math
if t.TYPE_CHECKING:
    import Counters
    import Mouse


def v_pack_buttons(container_size: t.Tuple[int, int], widget_frame: Widgets.Frame, widget_labels: t.List[str],
                   widget_sizes: t.List[t.Tuple[int, int]], widget_callbacks: t.List[t.Callable[[], None]],
                   font: pygame.font.Font, padding: int, start_y: t.Optional[int] = None,
                   start_id: int = 1) -> t.Tuple[int, int]:
    """Vertically stack a group of buttons on the same column. Each button will be horizontally centered, and the
    amount of vertical padding between each button will be uniform. The column of buttons will also be vertically
    centered within the height of the container area, unless a value is passed to the 'start_y' parameter, in which case
    the top of the column will be positioned at the y value given. Returns a two-item tuple with the first item being
    the value the widget-ID counter should be updated to, and the second being the total height of the buttons."""
    wid = start_id
    buttons: t.List[Widgets.Button] = []
    for size, label, callback in zip(widget_sizes, widget_labels, widget_callbacks):
        btn = Widgets.Button(0, 0, size[0], size[1], 1, COLORS["BLACK"], COLORS["ORANGE"], font, label, callback,
                             widget_name="!button{}".format(wid := wid + 1))
        buttons.append(btn)
    sum_height = sum(i.height + padding for i in buttons) - padding
    start_y = container_size[1] / 2 - sum_height / 2 if start_y is None else start_y
    offset_y = 0
    for idx, b in enumerate(buttons):
        b.x = container_size[0] / 2 - b.width / 2
        b.y = start_y + offset_y
        b.rect.x, b.rect.y = b.x, b.y
        widget_frame.add_widget(b)
        offset_y += b.rect.height + padding
    return wid, sum_height


def h_pack_buttons_se(container_size: t.Tuple[int, int], widget_frame: Widgets.Frame,
                      widget_surfaces: t.List[pygame.Surface], widget_callbacks: t.List[t.Callable[[], None]],
                      padding: int, widen_amount: int, start_y: t.Optional[int] = None,
                      start_id: int = 1) -> t.Tuple[int, int]:
    """Create a row of buttons that is positioned in the bottom-right corner of the container. The bottom side of the
    row of buttons will be one padding away from the bottom border of the container, unless a y position is given by the
    caller. The amount of horizontal padding between each button will be uniform. Each button will be vertically
    centered within the height of the tallest button in the row. Returns a two-item tuple with the first item being
    the value the widget-ID counter should be updated to, and the second being the height of the tallest button."""
    wid = start_id
    widgets = []
    btn_x = container_size[0]
    max_height = 0
    for surf, callback in reversed(zip(widget_surfaces, widget_callbacks)):
        w = Widgets.AnimatedSurface(0, 0, surf, callback, widen_amount=widen_amount,
                                    widget_name="!animated_surf{}".format(wid := wid + 1))
        size = (w.width, w.height)
        btn_x -= padding + size[0]
        w.x, w.rect.x = (btn_x,) * 2
        widgets.append(w)
        if w.height > max_height:
            max_height = w.height
    btn_start_y = container_size[1] - max_height
    for w in widgets:
        w.y = btn_start_y + (max_height[1] / 2 - w.height / 2) if start_y is None else start_y
        w.rect.y = w.y
        widget_frame.add_widget(w)
    return wid, max_height


def file_dialog(title: str, mode: t.Literal["open_file", "save_file"], ext_labels: t.List[str],
                ext_patterns: t.List[str]) -> t.Optional[str]:
    """Displays a tk file dialog and returns the path selected by the user or None."""
    root = tk.Tk()
    root.withdraw()
    f_types = list(zip(ext_labels, ext_patterns))
    if mode == "open_file":
        result = filedialog.askopenfilename(filetypes=f_types, initialdir=path.expanduser("~"), parent=root,
                                            title=title)
    else:
        result = filedialog.asksaveasfilename(confirmoverwrite=True, filetypes=f_types, initialdir=path.expanduser("~"),
                                              parent=root, title=title)
    if result:  # short for `result is not None and len(result) > 0`
        return path.normpath(path.abspath(result))
    else:
        return None


class BaseDialog:
    def __init__(self, surface: pygame.Surface, resolution: t.Tuple[int, int], max_window_size: t.Tuple[int, int],
                 border_radius: int, button_length: int, button_padding: int, button_thickness: int,
                 animation_speed: t.Union[int, float], max_widget_width: int, z_index: int = 1):
        """Base class for all dialogs. If the height that the content of the dialog occupies is less than the value
        given in the 'max_window_size' parameter, the dialog's height will be shortened to fit the contents, or else a
        scrollbar is added to the content area."""
        self.surface = surface
        self.resolution = resolution
        self.border_radius = border_radius
        self.button_length = button_length
        self.button_padding = button_padding
        self.button_thickness = button_thickness
        self.animation_speed = animation_speed
        self.z_index = z_index
        self.small_font = pygame.font.Font(find_abs_path("./Fonts/Arial/normal.ttf"), 25)
        self.large_font = pygame.font.Font(find_abs_path("./Fonts/Arial/normal.ttf"), 35)
        self.height_difference = self.border_radius * 2 + button_length + button_padding
        self.frame_size = [max_window_size[0] - self.border_radius * 2,
                           max_window_size[1] - self.height_difference]
        self.max_window_size = max_window_size
        self.final_window_pos = (self.resolution[0] / 2 - self.max_window_size[0] / 2,
                                 self.resolution[1] / 2 - (self.frame_size[1] + self.height_difference) / 2)
        self.scrollbar_width = 20
        self.max_widget_width = max_widget_width - self.border_radius * 2
        self.content_width = self.frame_size[0]
        self.widget_id = 1
        self.accumulated_y = 0
        # The real top-left coordinates of the frame has to be given so the IME candidate list will appear at the
        # correct place, but they will be ignored by the Widgets.Window class when rendering.
        self.content_frame = Widgets.Frame(self.final_window_pos[0] + border_radius,
                                           self.final_window_pos[1] + border_radius + button_length + button_padding,
                                           self.frame_size[0], self.frame_size[1], 20, z_index=z_index)
        self.window: t.Optional[Widgets.Window] = None  # The size cannot be determined until all widgets are added

    def h_shift_widgets(self, amount: t.Union[int, float]) -> None:
        for widget in self.content_frame.child_widgets.values():
            if isinstance(widget, Widgets.ScrollBar):  # The scrollbar should not be moved.
                continue
            widget.x += amount
            # Widgets that don't subclass 'AnimatedSurface' only update the rect on initialization. Therefore, it is
            # necessary to manually update the rect.
            widget.rect.move_ip(amount, 0)

    def create_label(self, text: str, padding: int, font: pygame.font.Font,
                     align: t.Literal["left", "center", "right"] = "center") -> None:
        label = Widgets.Label(self.content_width / 2 - self.max_widget_width / 2, self.accumulated_y, text,
                              COLORS["BLACK"], self.max_widget_width, font, align=align,
                              widget_name="!label{}".format(self.widget_id))
        self.content_frame.add_widget(label)
        self.accumulated_y += label.rect.height + padding
        self.widget_id += 1

    def create_slider(self, text_height: int, max_value: int, thumb_width: int, text_padding: int,
                      widget_padding: int) -> Widgets.Slider:
        text_size = self.large_font.size(str(max_value))
        max_text_width = text_height * (text_size[0] / text_size[1])
        widget_size = namedtuple("slider_args", ["text_height", "line_length", "thumb_width", "thumb_height", "font",
                                                 "max_value",
                                                 "text_padding"])(text_height=text_height,
                                                                  line_length=round(self.max_widget_width
                                                                                    - max_text_width - text_padding
                                                                                    - thumb_width),
                                                                  thumb_width=thumb_width, thumb_height=38,
                                                                  font=self.large_font, max_value=max_value,
                                                                  text_padding=text_padding)
        widget_data = Widgets.Slider.calc_size(*widget_size)
        slider = Widgets.Slider(round(self.content_width / 2 - widget_data[0] / 2), self.accumulated_y,
                                widget_size.text_height, COLORS["BLACK"], widget_size.line_length, 5, (250, 50, 50),
                                (0, 255, 0), widget_size.thumb_width, widget_size.thumb_height, (0, 130, 205),
                                (155, 205, 0), widget_size.font, 0, widget_size.max_value,
                                widget_name="!slider{}".format(self.widget_id))
        self.content_frame.add_widget(slider)
        self.accumulated_y += widget_data[1] + widget_padding
        self.widget_id += 1
        return slider

    def fit_to_content(self, force_scroll: bool = False) -> None:
        if self.content_frame.get_content_height() > self.frame_size[1] or force_scroll:
            self.max_widget_width -= self.scrollbar_width
            self.content_width -= self.scrollbar_width
            self.h_shift_widgets(self.scrollbar_width / -2)
            self.content_frame.update_ime_rect()
            self.content_frame.add_widget(Widgets.ScrollBar(width=self.scrollbar_width))
        else:
            self.frame_size[1] = self.content_frame.get_content_height()
            # The frame's size now has to be forcibly updated.
            self.content_frame.height = self.frame_size[1]
            # Updating the rect is not necessary as it'll be updated by the parent window.
        self.window = Widgets.Window(self.final_window_pos[0], self.resolution[1], self.final_window_pos[1],
                                     COLORS["GREEN"], 100, COLORS["RED"], COLORS["GREY6"], self.border_radius,
                                     self.button_length, self.button_padding, self.button_thickness,
                                     self.animation_speed, self.content_frame, self.surface, self.z_index)

    def update(self, mouse_obj: "Mouse.Cursor", keyboard_events: t.List[pygame.event.Event]) -> bool:
        return self.window.update(mouse_obj, keyboard_events)

    def draw(self) -> None:
        self.window.draw()


class Settings(BaseDialog):
    def __init__(self, surface: pygame.Surface, resolution: t.Tuple[int, int], max_window_size: t.Tuple[int, int],
                 border_radius: int, button_length: int, button_padding: int, button_thickness: int,
                 animation_speed: t.Union[int, float], max_widget_width: int, current_volume: int, z_index: int = 1):
        super().__init__(surface, resolution, max_window_size, border_radius, button_length, button_padding,
                         button_thickness, animation_speed, max_widget_width, z_index)
        vertical_padding = 20
        self.create_label("Settings", vertical_padding, self.large_font)
        self.create_label("Volume", vertical_padding, self.small_font)
        self.slider = self.create_slider(31, 100, 13, 10, vertical_padding)
        self.slider.set_slider_value(current_volume)
        self.fit_to_content()  # Adds a scrollbar if the content height exceeds the frame height.

    def get_volume(self) -> int:
        return self.slider.get_slider_value()


class Pause(BaseDialog):
    def __init__(self, surface: pygame.Surface, resolution: t.Tuple[int, int], max_window_size: t.Tuple[int, int],
                 border_radius: int, button_length: int, button_padding: int, button_thickness: int,
                 full_screen_icon: pygame.Surface, animation_speed: t.Union[int, float], max_widget_width: int,
                 current_volume: int, callbacks: t.List[t.Callable[[], None]], z_index: int = 1):
        super().__init__(surface, resolution, max_window_size, border_radius, button_length, button_padding,
                         button_thickness, animation_speed, max_widget_width, z_index)
        vertical_padding = 20
        self.create_label("Paused", vertical_padding // 3, self.large_font)
        data = v_pack_buttons((max_widget_width, 0), self.content_frame,
                              ["Main Menu"],
                              [(178, 51)],
                              [callbacks[0]],
                              self.large_font, vertical_padding // 3, self.accumulated_y, self.widget_id)
        self.widget_id = data[0]
        self.accumulated_y += data[1] + vertical_padding
        self.create_label("Volume", vertical_padding, self.small_font)
        self.slider = self.create_slider(31, 100, 13, 10, vertical_padding // 2)
        self.slider.set_slider_value(current_volume)
        data = h_pack_buttons_se((max_widget_width, 0), self.content_frame,
                                 [full_screen_icon],
                                 [callbacks[1]],
                                 vertical_padding, 20, self.accumulated_y, self.widget_id)
        self.widget_id = data[0]
        self.accumulated_y += data[1]
        self.fit_to_content()

    def get_volume(self) -> int:
        return self.slider.get_slider_value()


class SubmitScore(BaseDialog):
    def __init__(self, surface: pygame.Surface, resolution: t.Tuple[int, int], max_window_size: t.Tuple[int, int],
                 border_radius: int, button_length: int, button_padding: int, button_thickness: int,
                 animation_speed: t.Union[int, float], max_widget_width: int, callback: t.Callable[[str], None],
                 z_index: int = 1):
        super().__init__(surface, resolution, max_window_size, border_radius, button_length, button_padding,
                         button_thickness, animation_speed, max_widget_width, z_index)
        self.label_font = pygame.font.Font(find_abs_path("./Fonts/Arial/normal.ttf"), 22)
        self.entry_font = pygame.font.Font(find_abs_path("./Fonts/JhengHei/normal.ttc"), 20)
        self.submitted = False
        self.callback = callback
        vertical_padding = 10
        self.create_label("New high score! Submit your score?", 2 * vertical_padding, self.label_font)
        self.create_label("Name:", vertical_padding, self.label_font, align="left")
        entry_size = (160, 38)
        self.length_limit = 50
        self.entry = Widgets.Entry(self.scrollbar_width / 2 + vertical_padding, self.accumulated_y, entry_size[0],
                                   entry_size[1], 4, self.entry_font, COLORS["BLACK"])
        self.accumulated_y += entry_size[1] + vertical_padding
        self.content_frame.add_widget(self.entry)
        with suppress(Exception):  # In case getuser() fails
            self.entry.set_auto_typed_text(getpass.getuser()[:self.length_limit])
        original_size = (144, 60)
        widen_amount = 60
        offset_data = Widgets.Button.calc_size(0, original_size[0], original_size[1], widen_amount=widen_amount)
        true_size = (original_size[0] + widen_amount, abs(offset_data[0]) + offset_data[1])
        button = Widgets.Button(max_widget_width / 2 - true_size[0] / 2 + widen_amount / 2,
                                self.accumulated_y + abs(offset_data[0]),
                                original_size[0], original_size[1], 1, COLORS["BLACK"], COLORS["ORANGE"],
                                self.large_font, "Submit", self.submit, widen_amount=widen_amount)
        self.accumulated_y += true_size[1] + vertical_padding
        self.content_frame.add_widget(button)
        self.msg_y = self.accumulated_y
        self.update_info_label("", no_delete=True)
        self.fit_to_content(force_scroll=True)  # Force the scrollbar to appear to accommodate for the info label.

    def window_resize_event(self, current_res: t.List[int],
                            resized_res: t.Tuple[t.Union[int, float], t.Union[int, float]]) -> None:
        self.content_frame.update_window_data(self.resolution, current_res, resized_res)

    def update_info_label(self, message: str, no_delete: bool = False) -> None:
        if not no_delete:
            self.content_frame.delete_widget("!info_label")
        label = Widgets.Label(self.content_width / 2 - self.max_widget_width / 2, self.msg_y, message, COLORS["BLACK"],
                              self.max_widget_width, self.label_font, widget_name="!info_label")
        self.content_frame.add_widget(label)

    def check_valid(self, value: str) -> t.Optional[str]:
        message = None
        if not value:  # Empty string.
            message = "Please enter at least one non-whitespace character."
        elif len(value) > self.length_limit:
            message = "You've exceeded the limit of {} characters.".format(self.length_limit)
        return message

    def submit(self) -> None:
        if self.submitted:
            return None
        entry_value = self.entry.get_entry_content().strip()
        err_msg = self.check_valid(entry_value)
        if err_msg is None:
            self.window.close_window(bypass_idle_check=True)
            self.callback(entry_value)
            self.submitted = True
        else:
            self.update_info_label(err_msg)


class LevelBoard(Widgets.Frame):
    def __init__(self, res: t.Tuple[int, int], h_bubbles_num: int, nav_bar_h: int,
                 scrollbar_width: int, z_index: int, widget_name: str = "!lvl_editor"):
        """Custom widget in charge of rendering the whole screen during levels and the level editor."""
        super().__init__(0, 0, *res, 100, bg=COLORS["CYAN"], z_index=z_index, widget_name=widget_name)
        # Add the h_nav_bar widget to self when level editor starts?
        colors = [(249, 152, 40), (249, 137, 206)]
        self.h_nav_bar = NavBar(res[1] - nav_bar_h, (res[0], nav_bar_h), scrollbar_width, colors, z_index)
        self.nav_bar_h = nav_bar_h
        self.bubbles = BubbleCanvas((res[0], res[1] - nav_bar_h), scrollbar_width, colors, h_bubbles_num,
                                    self.h_nav_bar.get_selected_color, z_index)
        self.add_widget(self.bubbles)
        self.scrollbar_width = scrollbar_width
        # Render the bubbles in a different surface
        self.h_bubbles_num = h_bubbles_num  # Max num of bubbles in a row
        self.editor = False

    def update_size(self, new_size: t.Tuple[int, int]) -> None:
        if self.editor:
            self.bubbles.update_size((new_size[0], new_size[1] - self.nav_bar_h))

    def toggle_editor(self) -> None:
        self.editor = not self.editor
        if self.editor:
            self.add_widget(self.h_nav_bar)
            self.update_size((self.width, self.height))
            self.bubbles.toggle_editor()
        else:
            self.delete_widget(self.h_nav_bar.get_widget_name())

    def encode_lvl_file(self) -> bytes:
        pass

    def decode_lvl_file(self, file_data: bytes) -> None:
        pass


class Bubble:
    def __init__(self, exists: bool = False, color: int = 0):
        self.exists = exists
        self.color = color


class BubbleCanvas(Widgets.Frame):
    def __init__(self, size: t.Tuple[int, int], scrollbar_width: int, avail_colors: t.List[t.Tuple[int, int, int]],
                 h_bubbles_num: int, nav_bar_func: t.Callable[[], int], z_index: int,
                 widget_name: str = "!bubble_canvas"):
        """Sub-frame in charge of rendering the bubbles in levels and the level editor."""
        super().__init__(0, 0, size[0], size[1], scrollbar_width + 100, bg=COLORS["CYAN"], z_index=z_index,
                         widget_name=widget_name)
        self.editor = False
        self.board: t.List[t.List[Bubble]] = []
        self.radius, self.diameter = (0, 0)
        self.nav_bar_func = nav_bar_func
        self.scrollbar_width = scrollbar_width
        self.h_bubbles_num = h_bubbles_num
        self.new_row = [Bubble() for _ in range(self.h_bubbles_num)]
        self.colors = avail_colors
        self.color_surfs = []
        # 0 % 2 = 0, 1 % 2 = 1, 2 % 2 = 0, 3 % 2 = 1, ...
        self.len_f = lambda idx: self.h_bubbles_num - idx % 2  # Calcs the result of 'len(self.board[x])', necessary?
        self.h_pos_f = lambda row, col: (row % 2) * self.radius + col * self.diameter
        self.bubble_rect = pygame.Rect(0, 0, size[0] - self.scrollbar_width, size[1])
        self.bubble_surf = pygame.Surface(size)
        self.bubble_surf.set_colorkey(COLORS["TRANSPARENT"])
        self.scrollbar = Widgets.ScrollBar(width=scrollbar_width)
        self.add_widget(self.scrollbar)

    def toggle_editor(self) -> None:
        self.editor = not self.editor

    def update_size(self, new_res: t.Tuple[int, int]) -> None:
        super().update_size(new_res)
        # FIXME: The 'Frame' widget does not automatically call the 'update_size' method of child frames. This should be
        #  fixed.
        width = self.width - self.scrollbar_width
        self.diameter = width / self.h_bubbles_num
        self.radius = self.diameter / 2
        self.color_surfs.clear()
        for c in self.colors:
            surf = pygame.Surface((self.diameter,) * 2)
            surf.set_colorkey(COLORS["TRANSPARENT"])
            surf.fill(COLORS["TRANSPARENT"])
            pygame.draw.circle(surf, c, (self.radius,) * 2, self.radius)
            self.color_surfs.append(surf)

    def get_content_height(self) -> int:
        return self.diameter * len(self.board) + self.padding_bottom

    def render_bubbles(self) -> None:
        self.bubble_surf.fill(COLORS["TRANSPARENT"])
        for row in range(math.floor(abs(self.y_scroll_offset) // self.diameter), len(self.board)):
            for col in range(len(self.board[row])):
                bubble = self.board[row][col]
                if bubble.exists:
                    self.bubble_surf.blit(self.color_surfs[bubble.color], (self.h_pos_f(row, col),
                                                                           row * self.diameter + self.y_scroll_offset))
        # Remember to not fill the surface as that would erase the rendered widgets.
        self.image.blit(self.bubble_surf, (0, 0))

    def update_bubbles(self, mouse_obj: "Mouse.Cursor") -> None:
        if self.editor:
            mouse_x, mouse_y = mouse_obj.get_pos()
            mouse_y -= self.y_scroll_offset
            row = math.floor(mouse_y // self.diameter)
            col = math.floor((mouse_x - (row % 2) * self.radius) // self.diameter)
            if any((row < 0, col < 0, col > self.len_f(row) - 1, self.scrollbar.thumb.mouse_down)):
                return None
            if not mouse_obj.get_button_state(1):
                return None
            sel_color = self.nav_bar_func()
            while row > len(self.board) - 1:
                # Hilarious results ensue if a shallow copy of 'self.new_row' is used instead of a deep copy.
                self.board.append(copy.deepcopy(self.new_row))
            sel_cell = self.board[row][col]
            if sel_color == -1:
                sel_cell.exists = False
                self.free_ram()
                return None
            if not sel_cell.exists:
                sel_cell.exists = True
            sel_cell.color = sel_color
        else:
            pass

    def free_ram(self) -> None:
        # Number of empty rows counting from the end of the board.
        row = len(self.board) - 1
        while row >= 0:
            if any(i.exists for i in map(op.getitem, itools.repeat(self.board[row]), range(0, self.h_bubbles_num))):
                break
            row -= 1
        self.board[:] = self.board[:row + 1]

    def update(self, mouse_obj: "Mouse.Cursor", keyboard_events: t.List[pygame.event.Event]) -> None:
        super().update(mouse_obj.copy(), keyboard_events)  # Process and render normal widgets
        if self.bubble_rect.collidepoint(mouse_obj.get_pos()):
            self.update_bubbles(mouse_obj)
        self.render_bubbles()


class NavBar(Widgets.Frame):
    def __init__(self, y_pos: int, size: t.Tuple[int, int], scrollbar_width: int,
                 avail_colors: t.List[t.Tuple[int, int, int]], z_index: int, widget_name: str = "!nav_bar"):
        """Custom widget for rendering the tool palate along the bottom of the screen in the level editor."""
        super().__init__(0, y_pos, *size, 0, bg=COLORS["GREEN"], z_index=z_index, widget_name=widget_name)
        item_length = size[1] - scrollbar_width
        self.tool_objects: t.List[NavItem] = [
            self.create_item(NavItem(item_length * len(avail_colors) if idx == -1 else item_length * idx, item_length,
                                     item_length - 20, idx, self.select_event, color,
                                     widget_name="!nav_item{}".format(idx)))
            for idx, color in itertools.chain(enumerate(avail_colors), ((-1, None),))
        ]
        self.add_widget(Widgets.ScrollBar(orientation="horizontal"))
        self.selected_idx = 0

    def update(self, mouse_obj: "Mouse.Cursor", keyboard_events: t.List[pygame.event.Event]) -> None:
        super().update(mouse_obj.copy(), keyboard_events)

    def create_item(self, item: "NavItem") -> "NavItem":
        self.add_widget(item)
        return item

    def select_event(self, tool_id: int) -> None:
        if tool_id == self.selected_idx:
            return None
        self.tool_objects[self.selected_idx].unselect()
        self.selected_idx = tool_id

    def get_selected_color(self) -> int:
        return self.selected_idx


class NavItem(Widgets.BaseWidget):
    def __init__(self, x_pos: int, length: int, icon_length: int, tool_id: int, sel_callback: t.Callable[[int], None],
                 tool_color: t.Optional[t.Tuple[int, int, int]] = None, widget_name: str = "!nav_item"):
        super().__init__(widget_name)
        # length = size[1] - scrollbar_width; 'tool_color' should be None if 'tool_id' equals -1
        # A custom icon loaded from an image (or a special rendered icon) will be used if 'tool_id' equals -1
        self.x, self.y = (x_pos, 0)
        self.width, self.height = (length,) * 2
        self.radius = icon_length / 2  # For rendering the circle
        if tool_id == -1:
            self.icon = pygame.image.load(find_abs_path("./Images/level_editor/delete_tool.png")).convert_alpha()
            if self.icon.get_width() > icon_length or self.icon.get_height() > icon_length:
                self.icon = resize_surf(self.icon, (icon_length,) * 2)
        else:
            self.icon = pygame.Surface((icon_length,) * 2)
            self.icon.set_colorkey(COLORS["TRANSPARENT"])
            self.icon.fill(COLORS["TRANSPARENT"])
            pygame.draw.circle(self.icon, tool_color, (self.radius, self.radius), self.radius)
        self.icon_pos = (self.width / 2 - self.radius, self.height / 2 - self.radius)
        self.tool_id = tool_id
        self.lock = True
        self.mouse_down = False
        self.callback = sel_callback
        self.selected_color = COLORS["ORANGE"]
        self.active_color = COLORS["BLUE"]
        self.normal_color = COLORS["GREEN"]
        self.current_color = self.normal_color
        self.selected = self.tool_id == 0
        self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def unselect(self) -> None:
        self.selected = False

    def render_surface(self) -> None:
        if self.selected:
            self.image.fill(self.selected_color)
        else:
            self.image.fill(self.current_color)
        self.image.blit(self.icon, self.icon_pos)

    def update(self, mouse_obj: "Mouse.Cursor", keyboard_events: t.List[pygame.event.Event]) -> None:
        collide = self.rect.collidepoint(*mouse_obj.get_pos())
        if not collide:
            if not mouse_obj.get_button_state(1):
                self.mouse_down = False
            self.lock = True
            self.current_color = self.normal_color
        else:
            if mouse_obj.get_button_state(1) and (not self.lock):
                self.mouse_down = True
            elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                self.mouse_down = False
                self.selected = True
                self.callback(self.tool_id)
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()


class ScoreBoard(Widgets.Frame):
    def __init__(self, x: int, y: int, width: int, height: int, radius: int, padding: int, font: pygame.font.Font,
                 score_data: t.Optional[t.List[t.Dict[str, str]]], score_max_width: int, z_index: int = 1,
                 widget_name: str = "!scoreboard"):
        super().__init__(x, y, width, height, padding, bg=COLORS["GREEN"], z_index=z_index, widget_name=widget_name)
        self.score_data = score_data
        scrollbar_width = 20
        content_width = width - 2 * radius - 3 * padding - scrollbar_width
        name_width = content_width - score_max_width
        if self.score_data is None:
            label = Widgets.Label(0, padding, "Failed to load high-score data.", COLORS["BLACK"],
                                  width - scrollbar_width, font)
            self.add_widget(label)
        elif self.score_data:
            accumulated_y = padding
            for index, entry in enumerate(self.score_data):
                row = Widgets.SplitLabel(padding, accumulated_y, (entry["player-name"], entry["score"]),
                                         (name_width, score_max_width), font, COLORS["BLACK"], COLORS["ORANGE"], radius,
                                         padding, widget_name="!row{}".format(index))
                accumulated_y += row.rect.height + padding
                self.add_widget(row)
        else:
            label = Widgets.Label(0, padding, "(Empty)", COLORS["BLACK"], width - scrollbar_width, font)
            self.add_widget(label)
        self.add_widget(Widgets.ScrollBar(width=scrollbar_width))

    def get_score_data(self) -> t.List[t.Dict[str, str]]:
        return [] if self.score_data is None else self.score_data


class LoseScreen:
    def __init__(self, parent_frame: Widgets.Frame, resolution: t.Tuple[int, int], score: "Counters.Score",
                 callbacks: t.List[t.Callable[[], None]]):
        self.parent_frame = parent_frame
        self.resolution = resolution
        self.large_font = pygame.font.Font(find_abs_path("./Fonts/Arial/normal.ttf"), 50)
        self.small_font = pygame.font.Font(find_abs_path("./Fonts/JhengHei/normal.ttc"), 16)
        self.score = score
        self.state: t.Literal["idle", "fetching", "writing"] = "idle"
        self.widget_id = 1
        self.padding = 20
        self.accumulated_y = self.padding * 6
        self.add_centered_label("Your score:", COLORS["PURPLE"])
        size = self.score.calc_size()
        self.score_pos = (resolution[0] / 2 - size[0] / 2, self.accumulated_y)
        self.accumulated_y += size[1] + self.padding
        scoreboard_size = (250, 200)
        self.scoreboard_rect = pygame.Rect(self.resolution[0] / 2 - scoreboard_size[0] / 2, self.accumulated_y,
                                           scoreboard_size[0], scoreboard_size[1])
        self.db_thread = Storage.ScoreDB()
        self.scoreboard_obj: t.Optional[ScoreBoard] = None
        self.accumulated_y += scoreboard_size[1] + self.padding
        v_pack_buttons(resolution, self.parent_frame, ["Retry", "Main Menu"], [(144, 69), (230, 69)],
                       callbacks, self.large_font, self.padding, start_y=self.accumulated_y)

    def get_score_position(self) -> t.Tuple[float, int]:
        return self.score_pos

    def update(self) -> t.Literal["loading", "fetch_done", "done"]:
        current_state = self.state
        if self.db_thread.is_busy():
            return "loading"
        else:
            self.state = "idle"
            if current_state == "fetching":
                return "fetch_done"
            elif current_state == "writing" or current_state == "idle":
                return "done"

    def add_centered_label(self, text: str, color: t.Tuple[int, int, int]) -> None:
        label = Widgets.Label(0, 0, text, color, self.resolution[0] - 2 * self.padding, self.large_font,
                              widget_name="!label{}".format(self.widget_id))
        label.update_position(self.resolution[0] / 2 - label.get_size()[0] / 2, self.accumulated_y)
        self.parent_frame.add_widget(label)
        self.widget_id += 1
        self.accumulated_y += label.get_size()[1] + self.padding

    def is_loading(self) -> bool:
        return self.db_thread.is_busy()

    def start_fetch_data(self) -> None:
        self.state = "fetching"
        self.db_thread.start_fetch_scores()

    def update_scoreboard(self, database_data: t.Optional[t.List[t.Dict[str, str]]], delete_old: bool = True):
        if delete_old:
            self.parent_frame.delete_widget("!scoreboard")
        score_width = 40
        self.scoreboard_obj = ScoreBoard(self.scoreboard_rect.x, self.scoreboard_rect.y, self.scoreboard_rect.width,
                                         self.scoreboard_rect.height, 13, 10, self.small_font, database_data,
                                         score_width, z_index=self.parent_frame.z_index, widget_name="!scoreboard")
        self.parent_frame.add_widget(self.scoreboard_obj)

    def check_record_score(self) -> bool:
        """Call this method after the thread started by calling 'self.start_fetch_data()' is done. A boolean will be
        returned indicating whether the 'SubmitScore' dialog should be opened."""
        return_code, db_data = self.db_thread.get_data()
        current_score = self.score.get_score()
        self.update_scoreboard(db_data, delete_old=False)
        if db_data:  # DB is not empty
            try:
                top_score = int(db_data[0]["score"])
            except ValueError:
                return False
            else:
                return current_score > top_score
        else:
            return current_score > 0

    def start_write_data(self, player_name: str) -> None:
        if not self.db_thread.is_busy():
            self.state = "writing"
            current_score = self.score.get_score()
            current_data = self.scoreboard_obj.get_score_data()
            current_data.insert(0, {self.db_thread.fields[0]: player_name,
                                    self.db_thread.fields[1]: str(current_score)})
            self.update_scoreboard(current_data)
            self.db_thread.start_write_score(player_name, current_score)


class HelpManager:
    def __init__(self, parent_frame: Widgets.Frame, resolution: t.Tuple[int, int], font: pygame.font.Font,
                 resize_func: t.Callable[[], None], callback: t.Callable[[], None]):
        # This class should handle all UI events. Should contain a method that returns a boolean indicating whether the
        # loading animation should continue to be shown.
        self.parent_frame = parent_frame
        self.resolution = resolution
        self.loading = True
        self.font = font
        self.line_height = font.size("█")[1]
        self.padding = 15
        self.resize_func = resize_func
        # region Page Controls
        prev_btn = Widgets.Button(0, 0, 260, 69, 1, COLORS["BLACK"], COLORS["ORANGE"], self.font, "Prev Page",
                                  self.prev_page, widen_amount=60, widget_name="!prev_btn")
        prev_btn.x, prev_btn.rect.x = (self.resolution[0] / 4 - prev_btn.width / 2,) * 2
        prev_btn.y, prev_btn.rect.y = (self.resolution[1] - self.padding - prev_btn.height,) * 2
        self.parent_frame.add_widget(prev_btn)
        next_btn = Widgets.Button(0, 0, 260, 69, 1, COLORS["BLACK"], COLORS["ORANGE"], self.font, "Next Page",
                                  self.next_page, widen_amount=60, widget_name="!next_btn")
        # a / 2 + (a / 4 - b / 2)
        # self.resolution[0] / 2 + (self.resolution[0] / 4 - next_btn.width / 2)
        next_btn.x, next_btn.rect.x = ((3 * self.resolution[0] - 2 * next_btn.width) / 4,) * 2
        next_btn.y, next_btn.rect.y = (self.resolution[1] - self.padding - next_btn.height,) * 2
        self.parent_frame.add_widget(next_btn)
        self.footer_height = prev_btn.height
        # endregion
        # region Header Frame
        back_btn = Widgets.Button(self.padding, self.padding, 173, 69, 1, COLORS["BLACK"], COLORS["ORANGE"], self.font,
                                  "◄ Back", callback, widen_amount=45, widget_name="!back_btn")
        self.header_height = max(back_btn.height, self.line_height)
        self.parent_frame.add_widget(back_btn)
        # endregion
        # region Page System
        self.text_rect = pygame.Rect(self.padding, 2 * self.padding + self.header_height,
                                     self.resolution[0] - 2 * self.padding,
                                     self.resolution[1] - 4 * self.padding - self.footer_height - self.header_height)
        self.lines_per_page = self.text_rect.height // self.line_height
        self.wrapped_lines = []
        self.page = 0
        self.max_page = -1
        self.page_string = "Page {} of {}"
        self.help_data = Storage.HelpFile()
        # endregion

    def update(self) -> None:
        if self.loading:
            if not self.help_data.is_running():
                self.loading = False
                self.init_page_sys()

    def init_page_sys(self) -> None:
        self.wrapped_lines = word_wrap_text(self.help_data.get_data().strip("\n"), self.text_rect.width, self.font)
        filled_pages, extra_lines = divmod(len(self.wrapped_lines), self.lines_per_page)
        self.max_page = filled_pages - (not extra_lines)  # filled_pages - 1 if extra_lines is non-zero.
        self.update_text_widget(True)

    def update_text_widget(self, first_update: bool = False) -> None:
        if not first_update:
            self.parent_frame.delete_widget("!page_num")
            self.parent_frame.delete_widget("!help_text")
        self.resize_func()
        page_num_display = Widgets.Label(self.resolution[0] / 2,
                                         self.padding + (self.header_height / 2 - self.line_height / 2),
                                         self.page_string.format(self.page + 1, self.max_page + 1), COLORS["BLACK"],
                                         round(self.resolution[0] / 2), self.font, widget_name="!page_num")
        self.parent_frame.add_widget(page_num_display)
        text_widget = Widgets.Label(self.text_rect.x, self.text_rect.y,
                                    self.wrapped_lines[self.page * self.lines_per_page:
                                                       (self.page + 1) * self.lines_per_page],
                                    COLORS["BLACK"], self.text_rect.width, self.font, align="left", no_wrap=True,
                                    widget_name="!help_text")
        self.parent_frame.add_widget(text_widget)

    def next_page(self) -> None:
        if self.page < self.max_page:
            self.page += 1
            self.update_text_widget()

    def prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.update_text_widget()

    def is_loading(self) -> bool:
        return self.loading


class AchievementFrame(Widgets.Frame):
    def __init__(self, x: int, y: int, width: int, height: int, radius: int, padding: int,
                 achievement_data: t.List[bool], string_callback: t.Callable[[int], t.Tuple[str, str]],
                 heading_font: pygame.font.Font, body_font: pygame.font.Font, fg: t.Tuple[int, int, int],
                 div_bg: t.Tuple[int, int, int, int], active_bg: t.Tuple[int, int, int],
                 locked_bg: t.Tuple[int, int, int], z_index: int = 1, widget_name: str = "!achievement_frame"):
        super().__init__(x, y, width, height, padding, bg=div_bg, z_index=z_index, widget_name=widget_name)
        scrollbar_width = 20
        accumulated_y = padding
        for index, achievement in enumerate(achievement_data):
            if achievement:
                strings = string_callback(index)
            else:
                strings = ("Locked Achievement", "I wonder what this could be...")
            div = Widgets.ParagraphRect(padding, accumulated_y, width - scrollbar_width - 2 * padding, radius, padding,
                                        fg, active_bg if achievement else locked_bg, strings[0], strings[1],
                                        heading_font, body_font, widget_name="!p_rect{}".format(index))
            accumulated_y += div.get_size()[1] + padding
            self.add_widget(div)
        self.add_widget(Widgets.ScrollBar(width=scrollbar_width))


class AchievementManager:
    def __init__(self, parent_frame: Widgets.Frame, resolution: t.Tuple[int, int], button_font: pygame.font.Font,
                 heading_font: pygame.font.Font, body_font: pygame.font.Font,
                 string_callback: t.Callable[[int], t.Tuple[str, str]], exit_callback: t.Callable[[], None]):
        self.parent_frame = parent_frame
        self.heading_font = heading_font
        self.body_font = body_font
        self.string_callback = string_callback
        padding = 15
        back_btn = Widgets.Button(padding, padding, 173, 69, 1, COLORS["BLACK"],
                                  COLORS["ORANGE"], button_font, "◄ Back", exit_callback, widen_amount=45,
                                  widget_name="!back_btn")
        self.parent_frame.add_widget(back_btn)
        content_y = 2 * padding + back_btn.height
        self.content_rect = pygame.Rect(padding, content_y, resolution[0] - 2 * padding,
                                        resolution[1] - content_y - padding)
        self.content_obj: t.Optional[AchievementFrame] = None
        self.content_id = "!achievement_frame"

    def update_data(self, state_data: t.List[bool]) -> None:
        if self.content_obj is not None:
            self.parent_frame.delete_widget(self.content_id)
        self.content_obj = AchievementFrame(self.content_rect.x, self.content_rect.y, self.content_rect.width,
                                            self.content_rect.height, 15, 10, state_data, self.string_callback,
                                            self.heading_font, self.body_font, COLORS["BLACK"], (249, 152, 40, 123),
                                            (140, 183, 255), (224, 238, 224), self.parent_frame.z_index,
                                            widget_name=self.content_id)
        self.parent_frame.add_widget(self.content_obj)


class BusyFrame:
    def __init__(self, resolution: t.Tuple[int, int], font: pygame.font.Font, alpha: int, size: int, thickness: int,
                 lit_length: int, speed: t.Union[int, float], unlit_color: t.Tuple[int, int, int],
                 lit_color: t.Tuple[int, int, int]):
        padding = 20
        self.widgets: t.Dict[str, t.Optional[t.Union[Widgets.BaseWidget,
                                                     Widgets.BaseOverlay]]] = {}
        self.z_order: t.List[str] = []
        label = Widgets.Label(0, 0, "Loading...", COLORS["WHITE"], resolution[0] - 2 * padding, font)
        frame_height = size + padding + label.get_size()[1]
        frame_y = resolution[1] / 2 - frame_height / 2
        label.update_position(resolution[0] / 2 - label.get_size()[0] / 2, frame_y + size + padding)
        self.spinner_args = (resolution[0] / 2 - size / 2, frame_y, size, thickness, lit_length, speed, unlit_color,
                             lit_color)
        overlay = Widgets.BaseOverlay(*resolution)
        overlay.image.set_alpha(alpha)
        self.add_widget("overlay", overlay)
        self.add_widget("spinner", None)
        self.add_widget("label", label)
        self.reset_animation()

    def add_widget(self, widget_id: str,
                   widget_obj: t.Optional[t.Union[Widgets.BaseWidget, Widgets.BaseOverlay]]) -> None:
        self.widgets[widget_id] = widget_obj
        self.z_order.append(widget_id)

    def reset_animation(self) -> None:
        """Resets the loading animation."""
        self.widgets["spinner"] = Widgets.Spinner(*self.spinner_args)

    def update(self, mouse_obj: "Mouse.Cursor", keyboard_events: t.List[pygame.event.Event]) -> None:
        # 'Spinner' is the only widget in this class that needs to be updated.
        # 'BaseOverlay' does not have an update method, and the update method of 'Label' only runs 'pass'.
        self.widgets["spinner"].update(mouse_obj, keyboard_events)

    def draw(self, surface: pygame.Surface) -> None:
        for w in self.z_order:
            surface.blit(self.widgets[w].image, self.widgets[w].rect)
