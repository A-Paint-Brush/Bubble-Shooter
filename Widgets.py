"""
This is a GUI toolkit for SDL that I made mainly for my own use, but feel free to use it in your project if you want.

|
How to use:

First, construct a 'Frame' class instance. Then, initialize each widget you want to use, and add the class object to the
frame via the 'Frame.add_widget' method. Note that radio buttons are a bit special, as you have to first create a
'RadioGroup' instance, then create radio buttons for the group with the 'RadioGroup.create_radio_button' method. After
that, you can pass the 'RadioGroup' object to the 'Frame.add_widget' method like a normal widget.

Every game tick, make sure to pass user events to the frame by calling the 'Frame.update' method and passing a
'Mouse.Cursor' object and a list of 'pygame.event.Event' objects as parameters. You should initialize a 'Mouse.Cursor'
object at the beginning of your code, and continuously call its 'mouse_enter', 'mouse_leave', 'reset_scroll',
'push_scroll', 'set_button_state', 'set_pos', and 'reset_z_index' methods at the correct times in the game-loop. The
list should contain all keyboard-related events that has appeared since the last time 'Frame.update' was called. This
can easily be achieved by declaring an empty list, then looping through the event queue every frame and appending
keyboard-related events to the end of the list, then clearing the list after passing it to the 'Frame.update' method.
After that, you can "blit" the frame to the display surface using the frame's 'image' and 'rect'
attributes.

As widgets solely rely on the data you pass to it to handle user events, make sure to correctly update the data you're
passing to the 'Frame.update' method to ensure widgets respond to hovers, clicks, scroll events, key-presses, and window
events correctly.

'UI_Demo.py' is a UI that demonstrates how to use this module. It was created for testing purposes during
development, but I'm sure it'll also help you on getting started.

|
Notes:

1. This module also needs 'Global.py', 'Mouse.py', and 'Time.py' to work. Include them in your project if you want to
   use this module.
2. Since this module needs access to window events, Pygame version >= 2.0.1 is required.
3. Apart from the 'Pygame' module, this file also requires the 'Pyperclip' module to be installed in order to access the
   clipboard. Make sure to install it with 'pip install pyperclip' if you don't already have it.
"""
from tempfile import mkdtemp
from shutil import rmtree
from time import sleep
from Util import *
import csv
import math
import Mouse
import Time
import os
import pygame
import pyperclip
import threading
import queue
import atexit
os.environ["SDL_IME_SHOW_UI"] = "1"  # Enable showing the IME candidate list.


class BaseWidget(pygame.sprite.Sprite):
    def __init__(self, widget_name: str = "!base_widget"):
        """Base class for all widgets."""
        super().__init__()
        self.widget_name = widget_name
        self.parent = None

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        pass

    def get_widget_name(self) -> str:
        return self.widget_name

    def set_parent(self, parent_widget: "Frame") -> None:
        self.parent = parent_widget

    def has_parent(self) -> bool:
        return self.parent is not None


class AnimatedSurface(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 surface: pygame.Surface,
                 callback: t.Optional[t.Callable[[], None]],
                 widen_amount: int = 60,
                 widget_name: str = "!animated_surf"):
        """Animates a static surface image to dilate on mouse-hover and shrink on mouse-leave. When clicked, the surface
        flashes and calls the callback function given at initialization."""
        super().__init__(widget_name)
        # region Sprite Data
        max_size = self.calc_size(0, surface.get_width(), surface.get_height(), widen_amount)
        self.x = x
        self.y = y
        self.width = surface.get_width() + widen_amount
        self.height = abs(max_size[0]) + max_size[1]
        self.original_surface = surface
        self.original_width, self.original_height = self.original_surface.get_size()
        self.current_width = self.original_width
        self.current_height = self.original_height
        self.max_width = self.original_width + widen_amount
        self.min_width = self.original_width
        self.aspect_ratio = self.original_height / self.original_width
        # endregion
        # region Flash Animation Data
        self.brightness = 1
        self.max_brightness = 100
        self.brighten_step = 330
        self.flash_state = "idle"  # Literal["idle", "brighten", "darken"]
        self.flash_timer = Time.Time()
        # endregion
        # region Resize Animation Data
        self.difference = self.max_width - self.min_width
        self.reducing_fraction = 0.2
        self.resize_state = "small"  # Literal["small", "large", "dilating", "shrinking"]
        self.delta_timer = Time.Time()
        self.delta_timer.reset_timer()
        # endregion
        self.lock = True
        self.mouse_down = False
        self.callback_func = callback  # Stores the reference to the function to call when clicked.
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0))
        self.image.blit(self.original_surface, (self.width / 2 - self.current_width / 2,
                                                self.height / 2 - self.current_height / 2))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.mask = pygame.mask.from_surface(self.image)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        # region Tick Size
        collide = pygame.sprite.collide_mask(self, mouse_obj)
        if collide is None:
            if not mouse_obj.get_button_state(1):
                # Cancel click if mouse is released after being dragged off the button.
                self.mouse_down = False
            self.lock = True
            self.change_size("decrease")
        else:
            if mouse_obj.get_button_state(1) and (not self.lock):
                self.mouse_down = True
            elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                self.mouse_down = False
                if self.callback_func is not None:
                    self.flash_timer.reset_timer()
                    self.flash_state = "brighten"  # Start flash animation.
                    self.callback_func()  # Fire button-click event.
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.change_size("increase")
        # endregion
        # region Tick Brightness
        delta_time = self.flash_timer.get_time()
        self.flash_timer.reset_timer()
        if self.flash_state != "idle":
            if self.flash_state == "brighten":
                self.brightness += self.brighten_step * delta_time
                if self.brightness >= self.max_brightness:
                    self.brightness = self.max_brightness
                    self.flash_state = "darken"
            elif self.flash_state == "darken":
                self.brightness -= self.brighten_step * delta_time
                if self.brightness <= 1:
                    self.brightness = 1
                    self.flash_state = "idle"
            # Obtain the button surface that is at the correct size, but not brightened.
            if self.resize_state == "small":
                # Copy from original surface if resizing is not needed.
                self.image = self.original_surface.copy()
            elif self.resize_state == "large":
                # Scale original surface to max size.
                large_surf = pygame.transform.scale(self.original_surface,
                                                    (self.max_width, self.max_width * self.aspect_ratio))
                self.image.fill((0, 0, 0, 0))
                self.image.blit(large_surf, (0, 0))
            # If button is currently changing size, the surface will already be the un-brightened version.
            self.image.fill((self.brightness,) * 3, special_flags=pygame.BLEND_RGB_ADD)
            # endregion

    def set_size(self, new_size: float) -> None:
        self.current_width = round(new_size)
        self.current_height = round(self.current_width * self.aspect_ratio)
        resized_surf = pygame.transform.scale(self.original_surface, (self.current_width, self.current_height))
        self.image.fill((0, 0, 0, 0))
        self.image.blit(resized_surf, (self.width / 2 - self.current_width / 2,
                                       self.height / 2 - self.current_height / 2))
        self.mask = pygame.mask.from_surface(self.image)

    def calc_physics(self, delta_time: float, direction: t.Literal["increase", "decrease"]) -> float:
        self.difference *= math.pow(self.reducing_fraction, delta_time)
        if self.resize_state == "dilating" and direction == "decrease" or \
                self.resize_state == "shrinking" and direction == "increase":
            self.difference = self.max_width - self.min_width - self.difference
            self.resize_state = "shrinking" if self.resize_state == "dilating" else "dilating"
        new_width = None
        if direction == "increase":
            new_width = self.max_width - self.difference
        elif direction == "decrease":
            new_width = self.min_width + self.difference
        if round(new_width) == self.min_width and direction == "decrease":
            self.resize_state = "small"
            self.difference = self.max_width - self.min_width
        elif round(new_width) == self.max_width and direction == "increase":
            self.resize_state = "large"
            self.difference = self.max_width - self.min_width
        return new_width

    def change_size(self, direction: t.Literal["increase", "decrease"]) -> None:
        if (self.resize_state, direction) in (("small", "decrease"), ("large", "increase")):
            self.delta_timer.reset_timer()
            return None
        if self.resize_state == "small":
            self.resize_state = "dilating"
        elif self.resize_state == "large":
            self.resize_state = "shrinking"
        self.set_size(self.calc_physics(self.delta_timer.get_time(), direction))
        self.delta_timer.reset_timer()

    @staticmethod
    def calc_size(y_pos: int, og_width: int, og_height: int, widen_amount: int = 60) -> t.Tuple[float, float]:
        """Returns the top and bottom y coordinates of the button when it is at its max size."""
        aspect_ratio = og_height / og_width
        max_width = og_width + widen_amount
        min_height = og_width * aspect_ratio
        max_height = max_width * aspect_ratio
        min_top_y = y_pos - (max_height - min_height) / 2
        max_bottom_y = min_top_y + max_height
        return min_top_y, max_bottom_y


class Button(AnimatedSurface):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 width: int,
                 height: int,
                 border: int,
                 fg: t.Tuple[int, int, int],
                 bg: t.Tuple[int, int, int],
                 font: pygame.font.Font,
                 text: str,
                 callback: t.Optional[t.Callable[[], None]],
                 widen_amount: int = 60,
                 widget_name: str = "!button"):
        """Similar to AnimatedSurface, except it accepts a font object and a string in order to create the surface
        dynamically. The shape of the button is a two-cornered rounded rect."""
        button_surf = pygame.Surface((width, height), flags=pygame.SRCALPHA)
        button_surf.fill((0, 0, 0, 0))
        draw_button(button_surf, 0, 0, width, height, border, fg, bg, font, text)
        super().__init__(x, y, button_surf, callback, widen_amount, widget_name)


class Label(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 text: t.Union[str, t.List[str]],
                 fg: t.Tuple[int, int, int],
                 width: int,
                 font: pygame.font.Font,
                 align: t.Literal["left", "center", "right"] = "center",
                 no_wrap: bool = False,
                 widget_name: str = "!label"):
        """Accepts text to be displayed, width in pixels, and a font object. The text will be word-wrapped to guarantee
        that it fits the requested width."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.text_lines = text if no_wrap else word_wrap_text(text, width, font)
        self.line_height = font.size("█")[1]
        self.rect = pygame.Rect(self.x, self.y, width, self.line_height * len(self.text_lines))
        self.image = pygame.Surface((self.rect.width, self.rect.height), flags=pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0))
        for index, line in enumerate(self.text_lines):
            size = font.size(line)
            surface = font.render(line, True, fg)
            if align == "left":
                x = 0
            elif align == "center":
                x = width / 2 - size[0] / 2
            else:
                x = width - size[0]
            self.image.blit(surface, (x, index * self.line_height))

    def update_position(self, x: t.Union[int, float], y: t.Union[int, float]) -> None:
        self.x = x
        self.y = y
        self.rect = pygame.Rect(self.x, self.y, self.rect.width, self.rect.height)

    def get_size(self) -> t.Tuple[int, int]:
        return self.rect.size


class SplitLabel(BaseWidget):
    def __init__(self, x: t.Union[int, float], y: t.Union[int, float], lines: t.Tuple[str, str],
                 wrap_widths: t.Tuple[int, int], font: pygame.font.Font, fg: t.Tuple[int, int, int],
                 bg: t.Tuple[int, int, int], radius: int, padding: int, widget_name: str = "!split_label"):
        """Appears as a rounded rect with a line of word-wrapped text on either side horizontally. Great for displaying
        tables with two columns."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.width = 2 * radius + sum(wrap_widths) + padding
        self.wrapped_lines: t.List[Label] = []
        self.wrapped_lines.append(Label(radius, radius, lines[0], fg, wrap_widths[0], font, align="left"))
        label = Label(0, radius, lines[1], fg, wrap_widths[1], font, align="right")
        label.update_position(self.width - radius - label.get_size()[0], radius)
        self.wrapped_lines.append(label)
        self.height = 2 * radius + max(line.get_size()[1] for line in self.wrapped_lines)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0))
        draw_rounded_rect(self.image, (0, 0), (self.width, self.height), radius, bg)
        for line in self.wrapped_lines:
            self.image.blit(line.image, line.rect)


class ParagraphRect(BaseWidget):
    def __init__(self, x: t.Union[int, float], y: t.Union[int, float], width: int, radius: int, padding: int,
                 fg: t.Tuple[int, int, int], bg: t.Tuple[int, int, int], heading: str, body: str,
                 heading_font: pygame.font.Font, body_font: pygame.font.Font, widget_name: str = "!p_rect"):
        """Displays a heading and a word-wrapped paragraph in a rounded rect."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.width = width
        heading_label = Label(padding, padding, heading, fg, self.width - 2 * padding, heading_font,
                              align="left")
        body_label = Label(padding, heading_label.rect.bottom + padding, body, fg, self.width - 2 * padding,
                           body_font, align="left")
        self.height = body_label.rect.bottom + padding
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0))
        draw_rounded_rect(self.image, (0, 0), (self.width, self.height), radius, bg)
        self.image.blit(heading_label.image, heading_label.rect)
        self.image.blit(body_label.image, body_label.rect)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def get_size(self) -> t.Tuple[int, int]:
        return self.width, self.height


class Checkbox(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 label_text: str,
                 button_length: int,
                 border_radius: int,
                 text_color: t.Tuple[int, int, int],
                 bg: t.Tuple[int, int, int],
                 width: int,
                 font: pygame.font.Font,
                 padding: int,
                 border: int,
                 widget_name: str = "!checkbox"):
        """A simple checkbox with rounded corners both on the button and the surrounding rect. The caption text will be
        word-wrapped to fit the requested width."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.button_length = button_length
        self.button_radius = border_radius
        self.text_lines = word_wrap_text(label_text, width - padding * 3 - self.button_length, font)
        self.line_height = font.size("█")[1]
        self.checked = False
        self.image = pygame.Surface((width,
                                     padding * 2 + self.line_height * len(self.text_lines)), flags=pygame.SRCALPHA)
        self.image.fill((0, 0, 0, 0))
        draw_rounded_rect(self.image, (0, 0), self.image.get_size(), self.button_radius, bg)
        for index, text in enumerate(self.text_lines):
            surface = font.render(text, True, text_color)
            self.image.blit(surface, (padding * 2 + self.button_length, padding + self.line_height * index))
        self.rect = pygame.Rect(self.x, self.y, *self.image.get_size())
        self.__button = Box(padding, padding, self.button_length, self.button_radius, border)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        abs_pos = mouse_obj.get_pos()
        rel_mouse = mouse_obj.copy()
        rel_mouse.set_pos(abs_pos[0] - self.x, abs_pos[1] - self.y)
        self.__button.update(rel_mouse)
        self.image.blit(self.__button.image, self.__button.rect)

    def get_data(self) -> bool:
        return self.__button.get_data()

    def get_size(self) -> t.Tuple[int, int]:
        return self.image.get_size()


class Box(pygame.sprite.Sprite):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 length: int,
                 radius: int,
                 border: int):
        super().__init__()
        self.x = x
        self.y = y
        self.length = length
        self.radius = radius
        self.border = border
        self.lock = True
        self.mouse_down = False
        self.checked = False
        self.image = pygame.Surface((length, length))
        self.image.set_colorkey(COLORS["TRANSPARENT"])
        self.normal_color = COLORS["GREY3"]
        self.active_color = COLORS["CYAN"]
        self.current_color = self.normal_color
        self.render_surface()
        self.rect = pygame.Rect(self.x, self.y, length, length)
        self.mask = pygame.mask.from_surface(self.image)

    def render_surface(self) -> None:
        self.image.fill(COLORS["TRANSPARENT"])
        draw_rounded_rect(self.image, (0, 0), (self.length, self.length), self.radius, COLORS["BLACK"])
        draw_rounded_rect(self.image,
                          (self.border, self.border),
                          (self.length - self.border * 2, self.length - self.border * 2),
                          self.radius - self.border,
                          self.current_color)
        if self.checked:
            pygame.draw.lines(self.image, COLORS["BLACK"], False, ((5, self.length / 2 + 3),
                                                                   (self.length / 2 - 5, self.length - 5),
                                                                   (self.length - 5, 5)), 3)

    def update(self, mouse_obj: Mouse.Cursor) -> None:
        collide = pygame.sprite.collide_mask(self, mouse_obj)
        if collide is None:
            if not mouse_obj.get_button_state(1):
                self.mouse_down = False
            self.lock = True
            self.current_color = self.normal_color
        else:
            if mouse_obj.get_button_state(1) and (not self.lock):
                self.mouse_down = True
            elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                self.mouse_down = False
                self.checked = not self.checked
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()  # Mask and rect updates are not needed, since the shape of the surface stays the same.

    def get_data(self) -> bool:
        return self.checked


class RadioGroup:
    def __init__(self, default: int = 0):
        """Used for managing a group of radio buttons. Create all needed radio buttons with the 'create_radio_button'
        method, then add this class instance to a frame when done."""
        super().__init__()
        self.default = default
        self.counter_id = 0
        self.selected_id = default
        self.children = []

    def create_radio_button(self,
                            x: t.Union[int, float],
                            y: t.Union[int, float],
                            label_text: str,
                            button_length: int,
                            border_radius: int,
                            selected_radius: int,
                            text_color: t.Tuple[int, int, int],
                            bg: t.Tuple[int, int, int],
                            width: int,
                            font: pygame.font.Font,
                            padding: int,
                            border: int,
                            widget_name: str = "!radio_button") -> None:
        radio_button = RadioButton(self.counter_id, self.update_selection, self.counter_id == self.default, x, y,
                                   label_text, button_length, border_radius, selected_radius, text_color, bg, width,
                                   font, padding, border, widget_name)
        self.children.append(radio_button)
        self.counter_id += 1

    def update_selection(self, new_id: int) -> None:
        self.selected_id = new_id
        for index, radio_button in enumerate(self.children):
            if index != self.selected_id:
                radio_button.unselect()

    def get_children(self) -> list:
        return self.children

    def get_button_num(self) -> int:
        return len(self.children)

    def get_selected(self) -> int:
        return self.selected_id


class RadioButton(Checkbox):
    def __init__(self,
                 radio_id: int,
                 callback: t.Callable[[int], None],
                 selected: bool,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 label_text: str,
                 button_length: int,
                 border_radius: int,
                 selected_radius: int,
                 text_color: t.Tuple[int, int, int],
                 bg: t.Tuple[int, int, int],
                 width: int,
                 font: pygame.font.Font,
                 padding: int,
                 border: int,
                 widget_name: str = "!radio_button"):
        """A simple radio button widget. When a radio button is selected, all other radio-buttons in the same group will
         be unselected. The radio button which is selected by default is determined by the 'default' parameter passed to
         the RadioGroup class."""
        super().__init__(x, y, label_text, button_length, border_radius, text_color, bg, width, font, padding, border,
                         widget_name)
        self.id = radio_id
        self.button_radius = round(button_length / 2)
        self.__button = Circle(padding, padding, self.button_radius, border, selected_radius, radio_id, callback,
                               selected)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        abs_pos = mouse_obj.get_pos()
        rel_mouse = mouse_obj.copy()
        rel_mouse.set_pos(abs_pos[0] - self.x, abs_pos[1] - self.y)
        self.__button.update(rel_mouse)
        self.image.blit(self.__button.image, self.__button.rect)

    def unselect(self) -> None:
        self.__button.unselect()

    def get_size(self) -> t.Tuple[int, int]:
        return self.image.get_size()


class Circle(pygame.sprite.Sprite):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 radius: int,
                 border: int,
                 selected_radius: int,
                 radio_id: int,
                 on_click: t.Callable[[int], None],
                 selected: bool = False):
        super().__init__()
        self.id = radio_id
        self.x = x
        self.y = y
        self.radius = radius
        self.border = border
        self.selected_radius = selected_radius
        self.callback = on_click
        self.normal_color = COLORS["GREY3"]
        self.active_color = COLORS["CYAN"]
        self.current_color = self.normal_color
        self.selected = selected
        self.lock = True
        self.mouse_down = False
        self.image = pygame.Surface((radius * 2, radius * 2))
        self.image.set_colorkey(COLORS["TRANSPARENT"])
        self.image.fill(COLORS["TRANSPARENT"])
        pygame.draw.circle(self.image, COLORS["BLACK"], (radius, radius), radius, 0)
        pygame.draw.circle(self.image, self.current_color, (radius, radius), radius - border, 0)
        self.rect = pygame.Rect(self.x, self.y, radius, radius)
        self.mask = pygame.mask.from_surface(self.image)

    def update(self, mouse_obj: Mouse.Cursor) -> None:
        collide = pygame.sprite.collide_mask(self, mouse_obj)
        if collide is None:
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
                self.callback(self.id)
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        pygame.draw.circle(self.image, self.current_color, (self.radius, self.radius), self.radius - self.border, 0)
        if self.selected:
            pygame.draw.circle(self.image, COLORS["BLACK"], (self.radius, self.radius), self.selected_radius, 0)

    def unselect(self) -> None:
        self.selected = False


class Entry(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 width: int,
                 height: int,
                 padding: int,
                 font: pygame.font.Font,
                 fg: t.Tuple[int, int, int],
                 widget_name: str = "!entry"):
        """A simple text-box widget. Behaves virtually identical to the text-box widget of win32gui. Its copy-pasting
        functionality relies on the 'Pyperclip' module, so make sure to have it installed. Note that the environment
        variable 'SDL_IME_SHOW_UI' must be set to 1 for this widget to function correctly. This is done automatically
        when the module is imported."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.original_width = width
        self.height = height
        self.padding = padding
        self.font = font
        self.fg = fg
        self.border_thickness = 2
        self.text_input = False
        self.shift = False
        self.selecting = False
        self.start_select = True
        self.normal_border = COLORS["BLACK"]
        self.active_border = COLORS["BLUE"]
        self.current_border = self.normal_border
        self.block_select = False
        self.drag_pos = None
        self.drag_pos_recorded = False
        self.dnd_start_x = -1
        self.dnd_distance = 0
        self.dnd_x_recorded = False
        self.real_x = 0
        self.real_y = 0
        self.lock = True
        self.mouse_down = False
        self.text_canvas = EntryText(width - padding * 2, height - padding * 2, self.font, fg)
        self.ime_canvas = None
        self.caret_restore_pos = -1
        # (start sticky keys, start timer, has reset repeat, repeat timer)
        self.sticky_keys = {pygame.K_LEFT: [False,
                                            Time.Time(),
                                            False,
                                            Time.Time(),
                                            lambda: self.text_canvas.change_caret_pos("l")],
                            pygame.K_RIGHT: [False,
                                             Time.Time(),
                                             False,
                                             Time.Time(),
                                             lambda: self.text_canvas.change_caret_pos("r")],
                            pygame.K_BACKSPACE: [False,
                                                 Time.Time(),
                                                 False,
                                                 Time.Time(),
                                                 self.text_canvas.backspace],
                            pygame.K_DELETE: [False,
                                              Time.Time(),
                                              False,
                                              Time.Time(),
                                              self.text_canvas.delete]}
        self.start_delay = 0.5
        self.repeat_delay = 0.1
        self.scroll_hit_box = 30
        self.image = pygame.Surface((self.original_width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.original_width, self.height)

    def render_text_canvas(self) -> None:
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, self.current_border, [0, 0, self.original_width, self.height], 0)
        pygame.draw.rect(self.image,
                         COLORS["WHITE"],
                         [self.border_thickness,
                          self.border_thickness,
                          self.original_width - self.border_thickness * 2,
                          self.height - self.border_thickness * 2],
                         0)
        self.image.blit(source=self.text_canvas.get_surface(),
                        dest=(self.padding, self.padding),
                        area=self.text_canvas.get_view_rect())

    def update_real_pos(self, real_pos: t.Tuple[t.Union[int, float], t.Union[int, float]]) -> None:
        self.real_x, self.real_y = real_pos

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> t.Tuple[bool, bool, bool]:
        collide = pygame.sprite.collide_rect(self, mouse_obj)
        if collide:
            if mouse_obj.get_button_state(1):
                if (not self.lock) and (self.ime_canvas is None):
                    self.mouse_down = True
                    self.text_input = True
                    self.text_canvas.focus_get()
                    self.parent.raise_widget_layer(self.widget_name)
            else:
                self.mouse_down = False
                self.lock = False
            self.current_border = self.active_border
            if (not self.text_canvas.dnd_event_ongoing()) and self.block_select:
                self.block_select = False
        else:
            if mouse_obj.get_button_state(1):
                self.mouse_down = True
                if self.lock:
                    self.stop_focus()
            else:
                self.mouse_down = False
                self.lock = True
            self.current_border = self.normal_border
            if (not self.text_canvas.dnd_event_ongoing()) and self.block_select:
                self.block_select = False
        abs_pos = mouse_obj.get_pos()
        rel_mouse = mouse_obj.copy()
        rel_mouse.set_pos(abs_pos[0] - (self.x + self.padding), abs_pos[1] - (self.y + self.padding))
        for event in keyboard_events:
            if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                if event.mod & pygame.KMOD_SHIFT:
                    self.shift = True
                else:
                    if self.shift:
                        self.shift = False
                        if not self.start_select:
                            self.text_canvas.end_selection()
                            self.start_select = True
                        elif self.text_canvas.selection_event_ongoing():
                            # Special case for handling a text selection event that was initiated by a HOME or END
                            # key-press.
                            self.text_canvas.end_selection()
            if event.type == pygame.WINDOWFOCUSLOST:
                self.stop_focus()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.text_canvas.add_text("\t".expandtabs(tabsize=4))
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_BACKSPACE, pygame.K_DELETE):
                    if not self.sticky_keys[event.key][0]:
                        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                            if self.shift and self.start_select and \
                                    (not self.text_canvas.selection_event_ongoing()):
                                # The last one in the boolean expression is to make sure a selection event won't be
                                # triggered again if it has already been initiated by a HOME or END key-press.
                                self.text_canvas.start_selection()
                                self.start_select = False
                        self.sticky_keys[event.key][4]()
                        self.sticky_keys[event.key][0] = True
                        self.sticky_keys[event.key][1].reset_timer()
                elif event.key == pygame.K_HOME:
                    self.text_canvas.caret_home(self.shift)
                elif event.key == pygame.K_END:
                    self.text_canvas.caret_end(self.shift)
                elif event.key == pygame.K_RETURN:
                    if self.ime_canvas is not None:
                        self.stop_ime_input()
                elif event.mod & pygame.KMOD_CTRL:
                    if event.key == pygame.K_c:
                        self.text_canvas.copy_text()
                    elif event.key == pygame.K_v:
                        self.paste_text()
                    elif event.key == pygame.K_a:
                        self.text_canvas.select_all()
                    elif event.key == pygame.K_x:
                        if self.text_canvas.copy_text():
                            self.text_canvas.backspace()
                    elif event.key == pygame.K_z:
                        if self.shift:
                            self.text_canvas.redo()
                        else:
                            self.text_canvas.undo()
                    elif event.key == pygame.K_y:
                        self.text_canvas.redo()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_BACKSPACE, pygame.K_DELETE):
                    self.sticky_keys[event.key][0] = False
                    self.sticky_keys[event.key][2] = False
            elif event.type == pygame.TEXTINPUT:
                self.text_canvas.add_text(event.text)
            elif event.type == pygame.TEXTEDITING:
                if self.ime_canvas is None and self.text_canvas.has_focus() and event.text:
                    self.caret_restore_pos = self.text_canvas.get_caret_index()
                    self.text_canvas.focus_lose(False)
                    self.ime_canvas = EntryText(self.original_width - self.padding * 2,
                                                self.height - self.padding * 2,
                                                self.font,
                                                self.fg)
                    self.ime_canvas.focus_get()
                if self.ime_canvas is not None:
                    self.ime_canvas.ime_update_text(event.text, event.start)
                    width_diff = (self.padding
                                  + self.text_canvas.get_x()
                                  + self.text_canvas.calc_location_width()
                                  - self.text_canvas.get_caret_width()
                                  + self.ime_canvas.calc_text_size(self.ime_canvas.get_text())[0]
                                  + self.ime_canvas.get_caret_width()) - self.original_width
                    if width_diff > 0:
                        # (self.original_width + width_diff, self.height)
                        self.image = pygame.Surface((self.original_width + width_diff, self.height),
                                                    flags=pygame.SRCALPHA)
                    else:
                        self.image = pygame.Surface((self.original_width, self.height))
                    text_rect = pygame.Rect(self.real_x + self.padding + self.text_canvas.get_x()
                                            + self.text_canvas.calc_location_width()
                                            - self.text_canvas.get_caret_width() + self.ime_canvas.calc_ime_x_pos(),
                                            self.real_y + self.height - self.padding,
                                            0,
                                            0)
                    # It is unclear what effect the size of the rect has on the IME candidate list.
                    pygame.key.set_text_input_rect(self.parent.calc_resized_ime_rect(text_rect))
                    if not self.ime_canvas.get_text():
                        self.stop_ime_input()
        for key in self.sticky_keys.values():
            if key[0]:
                if key[1].get_time() > self.start_delay and (not key[2]):
                    key[2] = True
                    key[3].reset_timer()
            if key[2]:
                delta_time = key[3].get_time()
                if delta_time > self.repeat_delay:
                    compensation = delta_time - self.repeat_delay
                    key[4]()
                    if compensation > self.repeat_delay:
                        for i in range(math.floor(compensation / self.repeat_delay)):
                            key[4]()
                        compensation %= self.repeat_delay
                    key[3].force_elapsed_time(compensation)
        if mouse_obj.get_button_state(1):
            if self.drag_pos_recorded and self.text_canvas.mouse_collision(self.drag_pos):
                if mouse_obj.get_pos()[0] < self.x + self.scroll_hit_box:
                    self.text_canvas.move_view_by_pos("r")
                elif mouse_obj.get_pos()[0] > self.x + (self.original_width - self.scroll_hit_box):
                    self.text_canvas.move_view_by_pos("l")
            if self.text_canvas.mouse_collision(rel_mouse):
                if not self.drag_pos_recorded:
                    self.drag_pos_recorded = True
                    self.drag_pos = rel_mouse.copy()
                self.text_canvas.update_caret_pos(rel_mouse.get_pos())
                if not self.dnd_x_recorded:
                    self.dnd_x_recorded = True
                    self.dnd_start_x = rel_mouse.get_pos()[0]
                if self.text_canvas.text_block_selected() and (not self.text_canvas.dnd_event_ongoing()):
                    if abs(rel_mouse.get_pos()[0] - self.dnd_start_x) > self.dnd_distance:
                        self.text_canvas.start_dnd_event(rel_mouse)
                        if not self.block_select:
                            self.block_select = True
                if (not self.selecting) and \
                        (not self.text_canvas.dnd_event_ongoing()) and \
                        (not self.text_canvas.selection_rect_collide(rel_mouse.get_pos())):
                    self.text_canvas.start_selection()
                    self.selecting = True
        else:
            if self.text_canvas.mouse_collision(rel_mouse):
                if self.dnd_start_x != -1 and self.text_canvas.text_block_selected():
                    if self.text_canvas.selection_rect_collide(rel_mouse.get_pos()):
                        if abs(rel_mouse.get_pos()[0] - self.dnd_start_x) <= self.dnd_distance:
                            # Unselect text
                            self.text_canvas.cancel_dnd_event()
                            self.text_canvas.start_selection()
                            self.text_canvas.end_selection()
            if self.text_canvas.dnd_event_ongoing():
                self.text_canvas.end_dnd_event()
            if self.selecting:
                self.selecting = False
                if not mouse_obj.has_left():
                    self.text_canvas.update_caret_pos(rel_mouse.get_pos())
                self.text_canvas.end_selection()
            self.drag_pos_recorded = False
            self.drag_pos = None
            self.dnd_x_recorded = False
            self.dnd_start_x = -1
        self.text_canvas.update(False)
        self.render_text_canvas()
        if self.ime_canvas is not None:
            self.ime_canvas.update(True)
            self.image.blit(self.ime_canvas.get_surface(),
                            (self.padding
                             + self.text_canvas.get_x()
                             + self.text_canvas.calc_location_width()
                             - self.text_canvas.get_caret_width(),
                             self.padding))
        return collide, self.block_select, self.text_input

    def stop_focus(self) -> None:
        if self.ime_canvas is not None:
            # The IME text will be deleted.
            self.stop_ime_input()
        self.text_canvas.focus_lose()
        self.text_input = False

    def stop_ime_input(self):
        self.image = pygame.Surface((self.original_width, self.height))
        self.ime_canvas = None
        self.text_canvas.focus_get()
        self.text_canvas.set_caret_index(self.caret_restore_pos)
        self.caret_restore_pos = -1

    def paste_text(self) -> None:
        try:
            text = pyperclip.paste()
        except pyperclip.PyperclipException:
            return None
        if text:
            # The paste will be ignored if the Entry does not have keyboard focus.
            self.text_canvas.add_text("".join(c for c in text if c.isprintable()))

    def set_auto_typed_text(self, text: str) -> None:
        """Does the equivalent of clicking the entry, typing the text given, then pressing Ctrl+A."""
        self.text_input = True
        self.text_canvas.focus_get()
        self.parent.raise_widget_layer(self.widget_name)
        self.text_canvas.add_text(text)
        self.text_canvas.select_all()

    def get_pos(self) -> t.Tuple[int, int]:
        return self.x, self.y

    def get_entry_content(self) -> str:
        return self.text_canvas.get_text()


class EntryText:
    def __init__(self, width: int, height: int, font: pygame.font.Font, text_color: t.Tuple[int, int, int]):
        self.font = font
        self.text_color = text_color
        self.scroll_padding = 5
        self.x = 0
        self.y = 0
        self.view_width = width
        self.view_height = height
        self.caret_width = 2
        self.caret_height = height - 4
        self.caret_surf = pygame.Surface((self.caret_width, self.caret_height))
        self.caret_surf.fill(COLORS["BLACK"])
        self.caret_timer = Time.Time()
        self.caret_delay = 0.5
        self.scroll_amount = 70
        self.scroll_time = 0
        self.scroll_timer = Time.Time()
        self.scroll_timer.reset_timer()
        self.display_caret = True
        self.focus = False
        self.surface = pygame.Surface((self.caret_width, self.view_height))
        self.surface.fill(COLORS["WHITE"])
        self.text = ""
        self.undo_history = [""]
        self.redo_history = []
        self.caret_index = 0
        self.select_start = -1
        self.select_end = -1
        self.selecting = False
        self.select_rect = None
        self.dnd_event = False

    def record_undo(self) -> None:
        self.undo_history.append(self.text)

    def undo(self) -> None:
        if len(self.undo_history) and self.focus:
            temp = self.text
            while len(self.undo_history) and temp == self.text:
                temp = self.undo_history.pop()
            self.redo_history.append(temp)
            self.text = temp
            if self.caret_index > len(self.text):
                self.caret_index = len(self.text)
            current_width = self.calc_location_width()
            if current_width < self.view_width:
                self.x = 0
            elif self.x + current_width < self.view_width:
                self.move_view_by_caret("l")

    def redo(self) -> None:
        if len(self.redo_history) and self.focus:
            temp = self.text
            while len(self.redo_history) and temp == self.text:
                temp = self.redo_history.pop()
            self.undo_history.append(temp)
            self.text = temp
            if self.caret_index > len(self.text):
                self.caret_index = len(self.text)
            current_width = self.calc_location_width()
            if current_width < self.view_width:
                self.x = 0
            elif self.x + current_width < self.view_width:
                self.move_view_by_caret("l")

    def text_block_selected(self) -> bool:
        # Returns True if a block of text has already been selected, and the selection event has ENDED.
        return self.select_start != -1 and self.select_end != -1 and (not self.selecting)

    def selection_event_ongoing(self) -> bool:
        # Returns True if a selection event is *currently* ongoing.
        # (e.g. the shift key is still held down, or the left mouse button is still held down)
        return self.selecting

    def selection_rect_collide(self, position: t.Tuple[int, int]) -> bool:
        if (self.select_rect is not None) and (self.select_start != -1 and self.select_end != -1):
            rect = pygame.Rect(self.select_rect.x + self.x, self.select_rect.y, *self.select_rect.size)
            return rect.collidepoint(*position)
        else:
            return False

    def start_dnd_event(self, mouse_obj: Mouse.Cursor) -> None:
        if not self.dnd_event:
            if self.selection_rect_collide(mouse_obj.get_pos()) and \
                    (self.select_start != -1 and self.select_end != -1) and \
                    (not self.selecting):
                self.dnd_event = True

    def end_dnd_event(self) -> None:
        if self.dnd_event and (self.select_start != -1 and self.select_end != -1) and (not self.selecting):
            self.dnd_event = False
            if self.select_start <= self.caret_index <= self.select_end:
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
                return None
            selection = self.text[self.select_start:self.select_end]
            before_sel = self.text[:self.select_start]
            after_sel = self.text[self.select_end:]
            self.text = before_sel + after_sel
            if self.caret_index > self.select_end:
                temp_caret_idx = self.caret_index - len(selection)
            else:
                temp_caret_idx = self.caret_index
            before_sel = self.text[:temp_caret_idx]
            after_sel = self.text[temp_caret_idx:]
            self.text = before_sel + selection + after_sel
            self.select_start = -1
            self.select_end = -1
            self.select_rect = None
            self.record_undo()

    def cancel_dnd_event(self) -> None:
        self.dnd_event = False

    def dnd_event_ongoing(self) -> bool:
        return self.dnd_event

    def add_text(self, text: str) -> None:
        if not self.focus:
            return None
        overwrite = False
        if self.select_start != -1 or self.selecting:
            overwrite = True
            if self.selecting:
                if self.caret_index > self.select_start:
                    front = self.text[:self.select_start]
                    back = self.text[self.caret_index:]
                    self.caret_index = self.select_start + len(text)
                else:
                    front = self.text[:self.caret_index]
                    back = self.text[self.select_start:]
                    self.caret_index += len(text)
                self.select_start = self.caret_index
                self.select_end = -1
                self.select_rect = None
            else:
                front = self.text[:self.select_start]
                back = self.text[self.select_end:]
                self.caret_index = self.select_start + len(text)
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
            self.text = front + text + back
        else:
            temp = list(self.text)
            self.text = "".join(temp[:self.caret_index] + list(text) + temp[self.caret_index:])
        self.reset_caret()
        if not overwrite:
            self.caret_index += len(text)
        current_width = self.calc_location_width()
        if self.x + current_width > self.view_width:
            self.move_view_by_caret("l")
        self.record_undo()
        self.cancel_dnd_event()

    def backspace(self) -> None:
        if not self.focus:
            return None
        if self.select_start != -1 or self.selecting:
            if self.selecting:
                if self.caret_index > self.select_start:
                    front = self.text[:self.select_start]
                    back = self.text[self.caret_index:]
                    self.text = front + back
                    self.caret_index = self.select_start
                else:
                    front = self.text[:self.caret_index]
                    back = self.text[self.select_start:]
                    self.text = front + back
                self.select_start = self.caret_index
                self.select_end = -1
                self.select_rect = None
            else:
                self.text = self.text[:self.select_start] + self.text[self.select_end:]
                self.caret_index = self.select_start
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
        else:
            original_len = len(self.text)
            front = self.text[:self.caret_index]
            back = self.text[self.caret_index:]
            front = front[:-1]
            self.text = front + back
            if len(self.text) != original_len:
                self.caret_index -= 1
        if self.calc_text_size(self.text)[0] + self.caret_width < self.view_width:
            self.x = 0
        elif self.x + self.calc_text_size(self.text)[0] + self.caret_width < self.view_width:
            self.x = -(self.calc_text_size(self.text)[0] + self.caret_width + self.scroll_padding - self.view_width)
        self.record_undo()
        self.cancel_dnd_event()
        self.reset_caret()

    def delete(self) -> None:
        if not self.focus:
            return None
        if self.select_start != -1 or self.selecting:
            if self.selecting:
                if self.caret_index > self.select_start:
                    self.text = self.text[:self.select_start] + self.text[self.caret_index:]
                    self.caret_index = self.select_start
                else:
                    self.text = self.text[:self.caret_index] + self.text[self.select_start:]
                self.select_start = self.caret_index
                self.select_end = -1
                self.select_rect = None
            else:
                self.text = self.text[:self.select_start] + self.text[self.select_end:]
                self.caret_index = self.select_start
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
        else:
            front = self.text[:self.caret_index]
            back = self.text[self.caret_index:]
            back = back[1:]
            self.text = front + back
        if self.calc_text_size(self.text)[0] + self.caret_width < self.view_width:
            self.x = 0
        elif self.x + self.calc_text_size(self.text)[0] + self.caret_width < self.view_width:
            self.x = -(self.calc_text_size(self.text)[0] + self.caret_width + self.scroll_padding - self.view_width)
        self.record_undo()
        self.cancel_dnd_event()
        self.reset_caret()

    def copy_text(self) -> bool:
        """
        Returns True if there is text currently selected (which was just copied to the clipboard), False if otherwise.
        """
        if (self.select_start != -1 or self.selecting) and self.focus:
            if self.selecting:
                if self.caret_index > self.select_start:
                    selection = self.text[self.select_start:self.caret_index]
                else:
                    selection = self.text[self.caret_index:self.select_start]
            else:
                selection = self.text[self.select_start:self.select_end]
            try:
                pyperclip.copy(selection)
            except pyperclip.PyperclipException:
                pass
            return True
        else:
            return False

    def calc_location_width(self) -> float:
        return self.calc_text_size(self.text[:self.caret_index])[0] + self.caret_width

    def reset_caret(self) -> None:
        self.display_caret = True
        self.caret_timer.reset_timer()

    def update_caret_pos(self, mouse_pos) -> None:
        if not self.focus:
            return None
        text_index = -1
        width_counter = 0
        mouse_pos = (mouse_pos[0] + abs(self.x), mouse_pos[1])
        while width_counter < mouse_pos[0]:
            if text_index == len(self.text) - 1:
                break
            text_index += 1
            width_counter = self.calc_text_size(self.text[:text_index])[0]
        distances = (abs(mouse_pos[0]),
                     abs(self.calc_text_size(self.text[:text_index - 1])[0] - mouse_pos[0]),
                     abs(self.calc_text_size(self.text[:text_index])[0] - mouse_pos[0]),
                     abs(self.calc_text_size(self.text)[0] - mouse_pos[0]))
        self.caret_index = (0,
                            text_index - 1,
                            text_index,
                            len(self.text))[min(enumerate(distances), key=lambda x: x[1])[0]]
        if self.select_start != -1 or self.selecting:
            if self.selecting:
                start_pos = self.calc_text_size(self.text[:self.select_start])[0]
                end_pos = self.calc_text_size(self.text[:self.caret_index])[0]
            else:
                start_pos = self.calc_text_size(self.text[:self.select_start])[0]
                end_pos = self.calc_text_size(self.text[:self.select_end])[0]
            if start_pos < end_pos:
                self.select_rect = pygame.Rect(start_pos,
                                               0,
                                               abs(end_pos - start_pos) + self.caret_width,
                                               self.view_height)
            else:
                self.select_rect = pygame.Rect(end_pos,
                                               0,
                                               abs(end_pos - start_pos) + self.caret_width,
                                               self.view_height)

    def select_all(self) -> None:
        if self.focus:
            self.select_start = 0
            self.select_end = len(self.text)
            start_pos = self.calc_text_size(self.text[:self.select_start])[0]
            end_pos = self.calc_text_size(self.text[:self.select_end])[0]
            self.select_rect = pygame.Rect(start_pos, 0, end_pos - start_pos + self.caret_width, self.view_height)
            self.cancel_dnd_event()

    def start_selection(self) -> None:
        self.select_start = self.caret_index
        self.selecting = True

    def end_selection(self) -> None:
        self.select_end = self.caret_index
        self.selecting = False
        if self.select_start == self.select_end:
            self.select_start = -1
            self.select_end = -1
            self.select_rect = None
        else:
            if self.select_end < self.select_start:
                self.select_start, self.select_end = self.select_end, self.select_start
            start_pos = self.calc_text_size(self.text[:self.select_start])[0]
            end_pos = self.calc_text_size(self.text[:self.select_end])[0]
            self.select_rect = pygame.Rect(start_pos, 0, end_pos - start_pos + self.caret_width, self.view_height)

    def change_caret_pos(self, direction: t.Literal["l", "r"]) -> None:
        if not self.focus:
            return None
        if direction == "l":
            self.caret_index -= 1
            if self.caret_index < 0:
                self.caret_index = 0
        elif direction == "r":
            self.caret_index += 1
            if self.caret_index > len(self.text):
                self.caret_index = len(self.text)
        if self.selecting:
            if self.caret_index > self.select_start:
                start_pos = self.calc_text_size(self.text[:self.select_start])[0]
                end_pos = self.calc_text_size(self.text[:self.caret_index])[0]
            else:
                start_pos = self.calc_text_size(self.text[:self.caret_index])[0]
                end_pos = self.calc_text_size(self.text[:self.select_start])[0]
            if start_pos < end_pos:
                self.select_rect = pygame.Rect(start_pos,
                                               0,
                                               abs(end_pos - start_pos) + self.caret_width,
                                               self.view_height)
            else:
                self.select_rect = pygame.Rect(end_pos,
                                               0,
                                               abs(end_pos - start_pos) + self.caret_width,
                                               self.view_height)
        else:
            self.select_start = -1
            self.select_end = -1
            self.select_rect = None
        self.reset_caret()
        self.cancel_dnd_event()
        current_width = self.calc_location_width()
        if self.x + current_width < self.scroll_padding:
            self.move_view_by_caret("r")
        elif self.x + current_width > self.view_width - self.scroll_padding:
            self.move_view_by_caret("l")

    def ime_update_text(self, new_text: str, caret_pos: int) -> None:
        self.text = new_text
        self.caret_index = caret_pos

    def calc_ime_x_pos(self) -> float:
        if self.caret_index >= len(self.text):
            # Do not change the greater or equal to, because the caret pos reported by Pygame seems to go out of range
            # sometimes.
            return self.calc_text_size(self.text)[0]
        else:
            return self.calc_text_size(self.text[:self.caret_index])[0] \
                + self.calc_text_size(self.text[self.caret_index])[0]

    def caret_home(self, shift_down: bool) -> None:
        if self.focus:
            if (self.select_start != -1 and self.select_end != -1) and (not self.selecting):
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
            elif self.selecting:
                start_pos = self.calc_text_size(self.text[:self.select_start])[0]
                end_pos = 0
                self.select_rect = pygame.Rect(end_pos, 0, start_pos - end_pos + self.caret_width, self.view_height)
            elif shift_down:  # No text is selected (select_start == -1), but the shift key is down.
                start_pos = self.calc_text_size(self.text[:self.caret_index])[0]
                end_pos = 0
                self.selecting = True
                self.select_start = self.caret_index
                self.select_rect = pygame.Rect(end_pos, 0, start_pos - end_pos + self.caret_width, self.view_height)
            self.caret_index = 0
            self.x = 0
            self.cancel_dnd_event()

    def caret_end(self, shift_down: bool) -> None:
        if self.focus:
            if (self.select_start != -1 and self.select_end != -1) and (not self.selecting):
                self.select_start = -1
                self.select_end = -1
                self.select_rect = None
            elif self.selecting:
                start_pos = self.calc_text_size(self.text[:self.select_start])[0]
                end_pos = self.calc_text_size(self.text)[0]
                self.select_rect = pygame.Rect(start_pos, 0, end_pos - start_pos + self.caret_width, self.view_height)
            elif shift_down:
                start_pos = self.calc_text_size(self.text[:self.caret_index])[0]
                end_pos = self.calc_text_size(self.text)[0]
                self.selecting = True
                self.select_start = self.caret_index
                self.select_rect = pygame.Rect(start_pos, 0, end_pos - start_pos + self.caret_width, self.view_height)
            self.caret_index = len(self.text)
            if self.calc_text_size(self.text)[0] + self.caret_width > self.view_width:
                self.move_view_by_caret("l")
            self.cancel_dnd_event()

    def update(self, underline: bool) -> None:
        self.scroll_time = self.scroll_timer.get_time()
        self.scroll_timer.reset_timer()
        if not self.focus:
            new_size = self.calc_text_size(self.text)
            self.surface = pygame.Surface((new_size[0] + self.caret_width, self.view_height))
            self.surface.fill(COLORS["WHITE"])
            self.surface.blit(self.render_text(), (0, 0))
            return None
        delta_time = self.caret_timer.get_time()
        if delta_time > self.caret_delay:
            compensation = delta_time - self.caret_delay
            self.display_caret = not self.display_caret
            if compensation > self.caret_delay:
                for i in range(math.floor(compensation / self.caret_delay)):
                    self.display_caret = not self.display_caret
                compensation %= self.caret_delay
            self.caret_timer.force_elapsed_time(compensation)
        new_size = self.calc_text_size(self.text)
        self.surface = pygame.Surface((new_size[0] + self.caret_width, self.view_height))
        self.surface.fill(COLORS["WHITE"])
        if self.select_rect is not None:
            pygame.draw.rect(self.surface, (166, 210, 255), self.select_rect, 0)
        self.surface.blit(self.render_text(), (0, 0))
        if underline:
            for x in range(0, self.surface.get_width() - 2, 3):
                pygame.draw.rect(self.surface, COLORS["BLACK"], [x, self.view_height - 1, 2, 1], 0)
        if self.display_caret:
            x = self.calc_text_size(self.text[:self.caret_index])[0]
            self.surface.blit(self.caret_surf, (x, (self.view_height - self.caret_height) / 2))

    def render_text(self) -> pygame.Surface:
        text = self.font.render(self.text, True, self.text_color)
        text = pygame.transform.scale(text, self.calc_text_size(self.text))
        if len(self.text) == 0:
            return pygame.Surface((0, self.view_height))
        else:
            return text

    def calc_text_size(self, text: str) -> t.Tuple[float, int]:
        text_size = self.font.size(text)
        wh_ratio = text_size[0] / text_size[1]
        new_size = (self.view_height * wh_ratio, self.view_height)
        return new_size

    def focus_get(self) -> None:
        self.focus = True
        self.display_caret = True
        self.caret_timer.reset_timer()

    def focus_lose(self, reset_scroll: bool = True) -> None:
        if not self.focus:
            return None
        if reset_scroll:
            self.x = 0
        self.focus = False
        self.display_caret = False
        if (self.select_start != -1 and self.select_end != -1) or self.selecting:
            self.selecting = False
            self.select_start = -1
            self.select_end = -1
            self.select_rect = None

    def mouse_collision(self, mouse_obj: Mouse.Cursor) -> bool:
        return pygame.Rect(0, 0, self.view_width, self.view_height).collidepoint(*mouse_obj.get_pos())

    def move_view_by_caret(self, direction: t.Literal["l", "r"]) -> None:
        if direction == "l":
            width = self.calc_text_size(self.text[:self.caret_index])[0] + self.caret_width
            self.x = -(width - self.view_width + self.scroll_padding)
        elif direction == "r":
            width = self.calc_text_size(self.text[:self.caret_index])[0]
            if self.caret_index == 0:
                self.x = 0
            else:
                self.x = -(width - self.caret_width - self.scroll_padding)

    def move_view_by_pos(self, direction: t.Literal["l", "r"]) -> None:
        if not self.focus:
            return None
        if direction == "l":
            if self.calc_text_size(self.text)[0] + self.caret_width <= self.view_width:
                self.x = 0
                return None
            self.x -= self.scroll_amount * self.scroll_time
            if self.x < -(self.calc_text_size(self.text)[0] + self.caret_width + self.scroll_padding - self.view_width):
                self.x = -(self.calc_text_size(self.text)[0] + self.caret_width + self.scroll_padding - self.view_width)
        elif direction == "r":
            self.x += self.scroll_amount * self.scroll_time
            if self.x > 0:
                self.x = 0

    def get_surface(self) -> pygame.Surface:
        return self.surface

    def get_view_rect(self) -> pygame.Rect:
        return pygame.Rect(abs(self.x), self.y, self.view_width, self.view_height)

    def has_focus(self) -> bool:
        return self.focus

    def get_text(self) -> str:
        return self.text

    def get_x(self) -> int:
        return self.x

    def get_caret_width(self) -> int:
        return self.caret_width

    def set_caret_index(self, index: int) -> None:
        self.caret_index = index

    def get_caret_index(self) -> int:
        return self.caret_index


class Slider(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 text_height: int,
                 text_color: t.Tuple[int, int, int],
                 line_length: int,
                 line_thickness: int,
                 dormant_line_color: t.Tuple[int, int, int],
                 active_line_color: t.Tuple[int, int, int],
                 thumb_width: int,
                 thumb_height: int,
                 dormant_color: t.Tuple[int, int, int],
                 active_color: t.Tuple[int, int, int],
                 font: pygame.font.Font,
                 min_value: int,
                 max_value: int,
                 text_padding: int = 10,
                 mark_height: int = 0,
                 widget_name: str = "!slider"):
        """A simple slider widget. When the parameter 'mark_height' is greater than 0, lines of that height will be
        drawn at every unit."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.font = font
        self.text_height = text_height
        self.text_color = text_color
        self.line_length = line_length
        self.line_thickness = line_thickness
        self.dormant_line_color = dormant_line_color
        self.active_line_color = active_line_color
        self.thumb_width = thumb_width
        self.text_padding = text_padding  # The padding between the number display and the slider.
        self.gauge_height = mark_height
        self.max_text_width = self.resize_text(str(max_value))[0]
        self.width = self.thumb_width + self.line_length + self.text_padding + self.max_text_width
        self.height = max(text_height, thumb_height)
        self.slider_thumb = SliderButton(self.height / 2 - thumb_height / 2,
                                         self.thumb_width,
                                         thumb_height,
                                         dormant_color,
                                         active_color,
                                         self.line_length,
                                         min_value,
                                         max_value)
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def render_surface(self) -> None:
        self.image.fill((0, 0, 0, 0))
        # Draw a line from the beginning to the slider thumb's mid-point.
        pygame.draw.line(self.image, self.active_line_color,
                         (self.thumb_width / 2, self.height / 2),
                         (self.thumb_width + self.slider_thumb.get_position()[0], self.height / 2),
                         width=self.line_thickness)
        # Draw a line from the slider thumb's mid-point to the end of the slider.
        pygame.draw.line(self.image, self.dormant_line_color,
                         (self.thumb_width + self.slider_thumb.get_position()[0], self.height / 2),
                         (self.thumb_width / 2 + self.line_length, self.height / 2), width=self.line_thickness)
        if self.gauge_height > 0:
            for x in range(0, self.slider_thumb.value_distance + 1):
                # The lines are slightly inaccurate at large ranges due to float imprecision...
                pygame.draw.line(self.image,
                                 COLORS["BLACK"],
                                 (self.thumb_width / 2 + self.slider_thumb.px_per_value * x, 0),
                                 (self.thumb_width / 2 + self.slider_thumb.px_per_value * x, self.gauge_height - 1),
                                 1)
        self.image.blit(self.slider_thumb.get_surface(),
                        (self.slider_thumb.get_position()[0] + self.thumb_width / 2,
                         self.slider_thumb.get_position()[1]))
        text_surf = self.render_text(str(self.slider_thumb.get_value()))
        self.image.blit(text_surf,
                        (sum((self.thumb_width, self.line_length, self.text_padding))
                         + self.max_text_width / 2 - text_surf.get_width() / 2,
                         self.height / 2 - text_surf.get_height() / 2))

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        relative_mouse = mouse_obj.copy()
        relative_mouse.set_pos(mouse_obj.get_pos()[0] - self.x - self.thumb_width / 2,
                               mouse_obj.get_pos()[1] - self.y - self.slider_thumb.get_position()[1])
        self.slider_thumb.update(relative_mouse)
        self.render_surface()

    def render_text(self, text: str) -> pygame.Surface:
        return pygame.transform.scale(self.font.render(text, True, self.text_color), self.resize_text(text))

    def resize_text(self, text: str) -> t.Tuple[float, int]:
        text_size = self.font.size(text)
        wh_ratio = text_size[0] / text_size[1]
        new_size = (self.text_height * wh_ratio, self.text_height)
        return new_size

    def set_slider_value(self, value: int) -> None:
        self.slider_thumb.set_value(value)

    def get_slider_value(self) -> int:
        return self.slider_thumb.get_value()

    @staticmethod
    def calc_size(text_height: int,
                  line_length: int,
                  thumb_width: int,
                  thumb_height: int,
                  font: pygame.font.Font,
                  max_value: int,
                  text_padding: int = 10) -> t.Tuple[float, int]:
        text_size = font.size(str(max_value))
        max_text_width = text_height * (text_size[0] / text_size[1])
        width = thumb_width + line_length + text_padding + max_text_width
        height = max(text_height, thumb_height)
        return width, height


class SliderButton(pygame.sprite.Sprite):
    def __init__(self,
                 y: t.Union[int, float],
                 width: int,
                 height: int,
                 dormant_color: t.Tuple[int, int, int],
                 active_color: t.Tuple[int, int, int],
                 slider_length: int,
                 min_value: int,
                 max_value: int):
        super().__init__()
        self.x = -width / 2
        self.y = y
        self.width = width
        self.height = height
        self.dormant_color = dormant_color
        self.active_color = active_color
        self.current_color = self.dormant_color
        self.slider_length = slider_length
        self.min_value = min_value
        self.max_value = max_value
        self.value_distance = self.max_value - self.min_value
        self.px_per_value = self.slider_length / self.value_distance
        self.current_value = self.min_value
        self.lock = True
        self.mouse_down = False
        self.mouse_offset = -1
        self.image = pygame.Surface((self.width, self.height))
        self.image.set_colorkey(COLORS["TRANSPARENT"])
        self.render_surface()
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.mask = pygame.mask.from_surface(self.image)

    def render_surface(self) -> None:
        self.image.fill(COLORS["TRANSPARENT"])
        draw_vtp_rounded_rect(self.image, (0, 0), (self.width, self.height), self.current_color)

    def update(self, mouse_obj: Mouse.Cursor) -> None:
        # Handle mouse-drag movement.
        if self.mouse_down and not mouse_obj.has_left():
            self.x = mouse_obj.get_pos()[0] - self.mouse_offset
            if self.x < -self.width / 2:
                self.x = -self.width / 2
            elif self.x > self.slider_length - self.width / 2:
                self.x = self.slider_length - self.width / 2
            mid_x = self.x + self.width / 2
            self.current_value = math.floor(self.min_value + mid_x // self.px_per_value
                                            + (mid_x % self.px_per_value > self.px_per_value / 2))
            self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        # Handle collisions.
        collision = pygame.sprite.collide_mask(self, mouse_obj)
        if collision is None:
            if not mouse_obj.get_button_state(1) and self.mouse_down:
                self.mouse_down = False
                self.stop_drag()
            self.lock = True
            self.current_color = self.dormant_color
        else:
            if mouse_obj.get_button_state(1) and not self.mouse_down and not self.lock:
                self.mouse_down = True
                self.start_drag(mouse_obj)
            elif not mouse_obj.get_button_state(1):
                if self.mouse_down:
                    self.mouse_down = False
                    self.stop_drag()
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def start_drag(self, mouse_obj: Mouse.Cursor) -> None:
        self.mouse_offset = mouse_obj.get_pos()[0] - self.x

    def stop_drag(self) -> None:
        self.mouse_offset = -1
        mid_x = self.x + self.width / 2
        whole, remainder = divmod(mid_x, self.px_per_value)
        if remainder:
            mid_x = whole * self.px_per_value + (self.px_per_value if remainder > self.px_per_value / 2 else 0)
            self.x = mid_x - self.width / 2

    def set_value(self, value: int) -> None:
        mid_x = (value - self.min_value) * self.px_per_value
        self.x = mid_x - self.width / 2
        self.current_value = value

    def get_position(self) -> t.Tuple[float, float]:
        return self.x, self.y

    def get_surface(self) -> pygame.Surface:
        return self.image

    def get_value(self) -> int:
        return self.current_value


class ScrollBar(BaseWidget):
    def __init__(self, width: int = 20, orientation: t.Literal["vertical", "horizontal"] = "vertical",
                 shorten: bool = False, widget_name: str = "!scrollbar"):
        """A simple, functional scrollbar. It can be interacted with by dragging the thumb, clicking or holding down the
        up and down buttons, or using the scroll-wheel. The width of the scrollbar can be customized by passing a value
        to the 'width' parameter, but 20 pixels (the default) is the recommended width."""
        super().__init__(widget_name)
        self.orientation = orientation
        self.shorten = shorten
        # The values of most attributes cannot be calculated until the scrollbar is added to a parent.
        if self.orientation == "vertical":
            self.x = None
            self.y = 0
            self.width = width
            self.height = None
        else:
            self.x = 0
            self.y = None
            self.width = None
            self.height = width
        self.content_height = 0
        self.scroll_factor = None
        self.button_scroll_amount = 10
        self.thumb: t.Optional[ScrollThumb] = None
        self.up_button = None
        self.down_button = None
        self.image = None
        self.rect = None

    def set_parent(self, parent_widget: "Frame") -> None:
        self.parent = parent_widget
        if self.orientation == "vertical":
            self.x = self.parent.width - self.width
            self.height = self.parent.height - (self.width if self.shorten else 0)
        else:
            self.y = self.parent.height - self.height
            self.width = self.parent.width - (self.height if self.shorten else 0)
        if self.orientation == "horizontal" and self.shorten:
            # Fixes the ugly square at the place where the two scrollbars meet.
            self.image = pygame.Surface((self.width + self.height, self.height))
        else:
            self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.update_scrollbar_length(first_run=True)
        if self.orientation == "vertical":
            self.up_button = ScrollButton(0, 0, self.width, "up")
            self.down_button = ScrollButton(0, self.height - self.width, self.width, "down")
        else:
            self.up_button = ScrollButton(0, 0, self.height, "left")  # Actually left_button
            self.down_button = ScrollButton(self.width - self.height, 0, self.height, "right")  # right_button

    def update_scrollbar_length(self, first_run: bool = False, resize: bool = False) -> None:
        if self.orientation == "vertical":
            track_length = self.height - self.width * 2
            content_height = self.parent.get_content_height()
        else:
            track_length = self.width - self.height * 2
            content_height = self.parent.get_content_width()
        if not first_run and not resize and content_height == self.content_height:
            return None
        self.content_height = content_height  # Could be content width despite the variable name
        if self.orientation == "vertical":
            cs_ratio = content_height / self.height
        else:
            cs_ratio = content_height / self.width
        thumb_length = track_length / cs_ratio
        if thumb_length > track_length:
            thumb_length = track_length
        elif thumb_length < 30:
            thumb_length = 30
        if thumb_length == track_length:
            self.parent.set_scroll_offset(0, self.orientation)
        if first_run:
            self.thumb = ScrollThumb(self.width, self.height, thumb_length, self.orientation)
        else:
            if resize:
                self.thumb.update_track_length(track_length)
            self.thumb.update_thumb_length(thumb_length)
        scrollbar_distance = track_length - thumb_length
        if self.orientation == "vertical":
            content_distance = content_height - self.parent.height
        else:
            content_distance = content_height - self.parent.width
        if scrollbar_distance and content_distance:
            self.scroll_factor = content_distance / scrollbar_distance
        else:
            # 'scrollbar_distance' is zero, that means no scrolling is needed.
            self.scroll_factor = None

    def resize_scrollbar(self, new_size: t.Tuple[int, int]) -> None:
        if self.orientation == "vertical":
            self.x = new_size[0] - self.width
            self.height = new_size[1] - (self.width if self.shorten else 0)
        else:
            self.y = new_size[1] - self.height
            self.width = new_size[0] - (self.height if self.shorten else 0)
        self.rect.x, self.rect.y = self.x, self.y
        self.rect.width, height = self.width, self.height
        self.image = pygame.Surface((self.width, self.height))
        if self.orientation == "vertical":
            self.down_button.y = self.height - self.width
        else:
            self.down_button.x = self.width - self.height
        self.down_button.rect.x = self.down_button.x
        self.down_button.rect.y = self.down_button.y
        self.update_scrollbar_length(resize=True)
        self.scroll_by_content(0)

    def render_surface(self) -> None:
        self.image.fill(COLORS["GREY1"])
        if self.orientation == "vertical":
            self.image.blit(self.thumb.image, (self.thumb.x, self.thumb.y + self.width))
        else:
            self.image.blit(self.thumb.image, (self.thumb.x + self.height, self.thumb.y))
        self.image.blit(self.up_button.image, self.up_button.rect)
        self.image.blit(self.down_button.image, self.down_button.rect)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        relative_mouse = mouse_obj.copy()
        relative_mouse.set_pos(mouse_obj.get_pos()[0] - self.x, mouse_obj.get_pos()[1] - self.y)
        self.update_scrollbar_length()
        up_val = self.up_button.update(relative_mouse)
        down_val = self.down_button.update(relative_mouse)
        if self.orientation == "vertical":
            relative_mouse.set_pos(mouse_obj.get_pos()[0] - self.x, mouse_obj.get_pos()[1] - self.y - self.width)
        else:
            relative_mouse.set_pos(mouse_obj.get_pos()[0] - self.x - self.height, mouse_obj.get_pos()[1] - self.y)
        did_scroll = self.thumb.update(relative_mouse)
        if self.scroll_factor is not None:
            if did_scroll:
                # If the scrollbar was dragged, and there is space to scroll...
                self.parent.set_scroll_offset(-(self.scroll_factor * (self.thumb.y if self.orientation == "vertical"
                                                                      else self.thumb.x)), self.orientation)
            else:
                if mouse_obj.get_scroll(self.orientation) != 0:
                    self.scroll_by_content(mouse_obj.get_scroll(self.orientation)
                                           * (1 if self.orientation == "vertical" else -1))
                if up_val:
                    self.scroll_by_content(+self.button_scroll_amount)
                if down_val:
                    self.scroll_by_content(-self.button_scroll_amount)
        self.render_surface()

    def mouse_colliding(self, mouse_obj: Mouse.Cursor) -> bool:
        return self.rect.collidepoint(*mouse_obj.get_pos())

    def scroll_by_content(self, value: int) -> None:
        if self.scroll_factor is None:
            return None
        new_content_y = self.parent.add_scroll_offset(value, self.orientation)
        new_thumb_y = -new_content_y / self.scroll_factor
        self.thumb.force_set_pos(new_thumb_y)


class ScrollThumb(pygame.sprite.Sprite):
    def __init__(self, scrollbar_width: int, scrollbar_height: int, thumb_length: float,
                 orientation: t.Literal["vertical", "horizontal"]):
        super().__init__()
        self.x = 0
        self.y = 0
        self.orientation = orientation
        if self.orientation == "vertical":
            self.width = scrollbar_width
            self.height = 0
            self.track_length = scrollbar_height - self.width * 2
        else:
            self.width = 0
            self.height = scrollbar_height
            self.track_length = scrollbar_width - self.height * 2
        self.scroll_distance = 0
        self.dormant_color = COLORS["GREY4"]
        self.active_color = COLORS["GREY5"]
        self.dragged_color = COLORS["GREY6"]
        self.current_color = self.dormant_color
        self.length_updated = False
        self.update_thumb_length(thumb_length)
        self.lock = True
        self.mouse_down = False
        self.mouse_offset = -1
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def update_thumb_length(self, thumb_length: float) -> None:
        self.length_updated = True
        if self.orientation == "vertical":
            self.height = thumb_length
            self.scroll_distance = self.track_length - self.height
        else:
            self.width = thumb_length
            self.scroll_distance = self.track_length - self.width
        self.check_bounds()
        self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.render_surface()

    def update_track_length(self, track_len: int) -> None:
        self.track_length = track_len

    def check_bounds(self) -> None:
        if self.orientation == "vertical":
            if self.y < 0:
                self.y = 0
            elif self.y > self.scroll_distance:
                self.y = self.scroll_distance
        else:
            if self.x < 0:
                self.x = 0
            elif self.x > self.scroll_distance:
                self.x = self.scroll_distance

    def render_surface(self) -> None:
        self.image.fill(self.current_color)

    def force_set_pos(self, new_y: float) -> None:
        if self.orientation == "vertical":
            self.y = new_y
        else:
            self.x = new_y
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self, mouse_obj: Mouse.Cursor) -> bool:
        did_scroll = False
        if self.mouse_down and not mouse_obj.has_left():
            did_scroll = True
            if self.orientation == "vertical":
                self.y = mouse_obj.get_pos()[1] - self.mouse_offset
            else:
                self.x = mouse_obj.get_pos()[0] - self.mouse_offset
            self.check_bounds()
            self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        collision = pygame.sprite.collide_rect(self, mouse_obj)
        if collision:
            if mouse_obj.get_button_state(1) and not self.mouse_down and not self.lock:
                self.mouse_down = True
                self.start_drag(mouse_obj)
            elif not mouse_obj.get_button_state(1):
                if self.mouse_down:
                    self.mouse_down = False
                    self.stop_drag()
                self.lock = False
            self.current_color = self.active_color
        else:
            if not mouse_obj.get_button_state(1) and self.mouse_down:
                self.mouse_down = False
                self.stop_drag()
            self.lock = True
            self.current_color = self.dormant_color
        if did_scroll:
            self.current_color = self.dragged_color
        if self.length_updated:
            self.length_updated = False
            did_scroll = True
        self.render_surface()
        return did_scroll

    def start_drag(self, mouse_obj: Mouse.Cursor) -> None:
        if self.orientation == "vertical":
            self.mouse_offset = mouse_obj.get_pos()[1] - self.y
        else:
            self.mouse_offset = mouse_obj.get_pos()[0] - self.x

    def stop_drag(self) -> None:
        self.mouse_offset = -1


class ScrollButton(pygame.sprite.Sprite):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 button_length: int,
                 direction: t.Literal["up", "down", "left", "right"]):
        super().__init__()
        self.x = x
        self.y = y
        self.length = button_length
        self.direction = direction
        self.arrow_size = (self.length - 11, self.length - 15)
        self.lock = True
        self.mouse_down = False
        self.start_delay = 0.2
        self.repeat_delay = 0.1
        self.button_timer = Time.Time()
        self.repeating = False
        # Color format: (bg, fg)
        self.dormant_color = (COLORS["GREY1"], COLORS["GREY6"])
        self.active_color = (COLORS["GREY2"], COLORS["BLACK"])
        self.dragged_color = (COLORS["GREY6"], COLORS["WHITE"])
        self.current_color = self.dormant_color
        self.image = pygame.Surface((self.length, self.length))
        self.rect = pygame.Rect(self.x, self.y, self.length, self.length)

    def render_surface(self) -> None:
        self.image.fill(self.current_color[0])
        size = self.arrow_size
        if self.direction in ("left", "right"):
            size = tuple(reversed(self.arrow_size))
        draw_triangle(self.image,
                      (round(self.length / 2 - size[0] / 2) - 1,
                       round(self.length / 2 - size[1] / 2) - 1),
                      size,
                      self.current_color[1],
                      self.direction)

    def update(self, mouse_obj: Mouse.Cursor) -> bool:
        trigger = False
        collision = pygame.sprite.collide_rect(self, mouse_obj)
        if collision:
            if mouse_obj.get_button_state(1) and not self.mouse_down and not self.lock:
                self.mouse_down = True
                trigger = True
                self.button_timer.reset_timer()
            elif not mouse_obj.get_button_state(1):
                if self.mouse_down:
                    self.mouse_down = False
                self.lock = False
            self.current_color = self.active_color
        else:
            if not mouse_obj.get_button_state(1) and self.mouse_down:
                self.mouse_down = False
            self.lock = True
            self.current_color = self.dormant_color
        if self.mouse_down:
            if self.repeating and self.button_timer.get_time() > self.repeat_delay:
                trigger = True
                self.button_timer.reset_timer()
            elif self.button_timer.get_time() > self.start_delay:
                self.repeating = True
                self.button_timer.reset_timer()
            self.current_color = self.dragged_color
        else:
            self.repeating = False
        self.render_surface()
        return trigger


class Spinner(BaseWidget):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 size: int,
                 thickness: int,
                 lit_length: int,
                 speed: t.Union[int, float],
                 unlit_color: t.Tuple[int, int, int],
                 lit_color: t.Tuple[int, int, int],
                 widget_name: str = "!spinner"):
        """A simple, highly customizable spinner widget. Unfortunately, the arc that makes up the spinner will have
        'holes' in it at higher thicknesses due to limitations in the 'pygame.draw.arc' function."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.length = size
        self.lit_length = lit_length
        self.thickness = thickness
        self.speed = speed
        self.angle = 0
        self.delta_timer = Time.Time()
        self.unlit_color = unlit_color
        self.lit_color = lit_color
        self.image = pygame.Surface((self.length, self.length))
        self.image.set_colorkey(COLORS["TRANSPARENT"])
        self.rect = pygame.Rect(self.x, self.y, self.length, self.length)
        self.delta_timer.reset_timer()

    def render_surface(self) -> None:
        # radians = degrees × (π ÷ 180)
        # Angle system: 0° = EAST, 90° = NORTH, 180° = WEST, 360° = SOUTH
        self.image.fill(COLORS["TRANSPARENT"])
        pygame.draw.arc(self.image,
                        self.unlit_color,
                        (0, 0, self.length, self.length),
                        0,
                        math.radians(360),
                        self.thickness)
        start_angle = 360 - ((self.angle + self.lit_length) % 360)
        end_angle = 360 - self.angle
        pygame.draw.arc(self.image,
                        self.lit_color,
                        (0, 0, self.length, self.length),
                        math.radians(start_angle),
                        math.radians(end_angle),
                        self.thickness)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        d_t = self.delta_timer.get_time()
        self.delta_timer.reset_timer()
        self.angle += self.speed * d_t
        self.angle %= 360
        self.render_surface()


class Frame(BaseWidget):
    def __init__(self, x: t.Union[int, float], y: t.Union[int, float], width: int, height: int, padding_bottom: int,
                 bg: t.Union[t.Tuple[int, int, int], t.Tuple[int, int, int, int]] = (0, 0, 0, 0), z_index: int = 1,
                 widget_name: str = "!frame"):
        """Container class for all widgets. Every widget should be added to a frame after initialization. User input can
        then be passed to all widgets in the frame by calling the frame's 'update' method and passing a 'Mouse.Cursor'
        object and a list of 'pygame.event.Event' objects as parameters. After updating, the frame can be directly
        rendered to the screen using its 'image' and 'rect' attributes."""
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.real_width = width
        self.width = width
        self.real_height = height
        self.height = height
        self.window_data: t.Dict[str, t.Optional[t.Union[t.List[int],
                                                         t.Tuple[t.Union[int, float], t.Union[int, float]]]]] = {}
        self.padding_bottom = padding_bottom
        self.bg = bg
        self.scroll_constant = 20
        self.z_index = z_index
        self.new_size = False
        self.resize_exclude: t.Dict[str, t.Literal["x", "y", "both"]] = {}
        self.text_input = False
        self.cursor_display = "arrow"  # Literal["arrow", "i_beam", "text_drag"]
        self.cursor_icons = Mouse.CursorIcons()
        self.cursor_icons.init_cursors()
        self.x_scroll_offset = 0
        self.y_scroll_offset = 0
        # Using per-pixel alpha is necessary because we don't know what colors the surface returned by
        # `pygame.font.Font.render` might contain, and the surfaces of most child widgets will contain text.
        self.image = pygame.Surface((width, height), flags=pygame.SRCALPHA)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.child_widgets: t.Dict[str, BaseWidget] = {}
        self.real_positions: t.Dict[str, t.Tuple[t.Union[int, float], t.Union[int, float]]] = {}
        self.scrollbar_names = []
        # Stores the order in which widgets will be rendered. The last item will be rendered last, and therefore
        # will be on the topmost layer.
        self.render_z_order = []

    def add_widget(self, widget_obj: t.Union[BaseWidget, RadioGroup]) -> None:
        if isinstance(widget_obj, RadioGroup):
            for w in widget_obj.get_children():
                self.add_widget(w)
        else:
            w_name = widget_obj.get_widget_name()
            if w_name in self.child_widgets:
                raise FrameError(widget_obj, 1)
            elif widget_obj.has_parent():
                raise FrameError(widget_obj, 2)
            else:
                if isinstance(widget_obj, ScrollBar):
                    self.scrollbar_names.append(w_name)
                widget_obj.set_parent(self)
                self.child_widgets[w_name] = widget_obj
                if isinstance(widget_obj, OptionMenu):
                    self.real_positions[w_name] = widget_obj.get_real_pos("center")
                else:
                    self.real_positions[w_name] = (widget_obj.rect.centerx, widget_obj.rect.centery)
                self.render_z_order.append(w_name)
                if isinstance(widget_obj, Entry):
                    widget_obj.update_real_pos((self.x + widget_obj.get_pos()[0] + self.x_scroll_offset,
                                                self.y + widget_obj.get_pos()[1] + self.y_scroll_offset))

    def delete_widget(self, widget_id: str) -> None:
        if widget_id in self.child_widgets:
            if isinstance(self.child_widgets[widget_id], ScrollBar):
                self.scrollbar_names.remove(widget_id)
            self.child_widgets.pop(widget_id)
            self.real_positions.pop(widget_id)
            self.render_z_order.remove(widget_id)
        else:
            raise WidgetIDError(widget_id)

    def get_content_width(self) -> int:
        return max((widget.x + widget.image.get_width())
                   for widget in self.child_widgets.values() if not isinstance(widget, ScrollBar)) + self.padding_bottom

    def get_content_height(self) -> int:
        w_bottoms = []
        for widget in self.child_widgets.values():
            if isinstance(widget, ScrollBar):
                continue
            w_bottoms.append(widget.y + widget.image.get_height())
        return (max(w_bottoms) if w_bottoms else 0) + self.padding_bottom

    def add_scroll_offset(self, amount: int, direction: t.Literal["vertical", "horizontal"]) -> float:
        """Adds a value to the current scroll offset and returns the result."""
        if direction == "vertical":
            self.y_scroll_offset += amount + math.copysign(self.scroll_constant, amount)
            if self.y_scroll_offset > 0:
                self.y_scroll_offset = 0
            elif self.y_scroll_offset < -(self.get_content_height() - self.height):
                self.y_scroll_offset = -(self.get_content_height() - self.height)
        else:
            self.x_scroll_offset += amount + math.copysign(self.scroll_constant, amount)
            if self.x_scroll_offset > 0:
                self.x_scroll_offset = 0
            elif self.x_scroll_offset < -(self.get_content_width() - self.width):
                self.x_scroll_offset = -(self.get_content_width() - self.width)
        self.update_ime_rect()
        if direction == "vertical":
            return self.y_scroll_offset
        else:
            return self.x_scroll_offset

    def set_scroll_offset(self, offset: int, direction: t.Literal["vertical", "horizontal"]) -> None:
        if direction == "vertical":
            self.y_scroll_offset = offset
        else:
            self.x_scroll_offset = offset
        self.update_ime_rect()

    def calc_resized_ime_rect(self, original_rect: pygame.Rect) -> pygame.Rect:
        if self.window_data:
            return pygame.Rect(*dilate_coordinates(original_rect.topleft, self.window_data["fixed_res"],
                                                   self.window_data["current_res"], self.window_data["resized_res"]),
                               original_rect.width, original_rect.height)
        else:
            return original_rect

    def update_window_data(self, fixed_res: t.Tuple[int, int], current_res: t.List[int],
                           resized_res: t.Tuple[t.Union[int, float], t.Union[int, float]]) -> None:
        """Only needed for frames that contain entry widgets. Every time the window is resized, this method should be
        called before the 'update' method. This method can be ignored if the window is not resizable or actually moves
        the position of on-screen objects on resizing."""
        self.window_data["fixed_res"] = fixed_res
        self.window_data["current_res"] = current_res
        self.window_data["resized_res"] = resized_res

    def update_ime_rect(self) -> None:
        for widget in self.child_widgets.values():
            if isinstance(widget, Entry):
                self.update_entry_widget(widget)

    def update_entry_widget(self, widget: Entry) -> None:
        widget.update_real_pos((self.x + widget.get_pos()[0] + self.x_scroll_offset,
                                self.y + widget.get_pos()[1] + self.y_scroll_offset))

    def update_size(self, new_size: t.Tuple[int, int]) -> None:
        self.new_size = True
        self.width, self.height = new_size
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def manual_move_widget(self, widget_name: str,
                           new_pos: t.Tuple[t.Optional[t.Union[int, float]], t.Optional[t.Union[int, float]]]) -> None:
        if widget_name not in self.child_widgets:
            raise WidgetIDError(widget_name)
        else:
            resize_dir: t.Literal["x", "y", "both"]
            if new_pos[0] is None and new_pos[1] is not None:
                resize_dir = "y"
            elif new_pos[0] is not None and new_pos[1] is None:
                resize_dir = "x"
            else:
                resize_dir = "both"
            self.resize_exclude[widget_name] = resize_dir
            self.update_widget_pos(self.child_widgets[widget_name], new_pos)

    def update_widget_pos(self, widget: BaseWidget,
                          new_pos: t.Tuple[t.Optional[t.Union[int, float]], t.Optional[t.Union[int, float]]],
                          anchor: t.Literal["nw", "center"] = "nw") -> None:
        new_pos = list(new_pos)
        if new_pos[0] is None:
            new_pos[0] = widget.x
        if new_pos[1] is None:
            new_pos[1] = widget.y
        if isinstance(widget, OptionMenu):
            widget.update_position(tuple(new_pos), anchor)
            return None
        if anchor == "nw":  # Anchor "nw" is used by manual resizing
            widget.x, widget.y = new_pos
            widget.rect.x, widget.rect.y = widget.x, widget.y
        elif anchor == "center":
            widget.rect.center = new_pos
            widget.x, widget.y = widget.rect.topleft
        if isinstance(widget, Entry):
            self.update_entry_widget(widget)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        if self.z_index == mouse_obj.get_z_index() and self.rect.collidepoint(*mouse_obj.get_pos()):
            pointer_events = True
            abs_pos = mouse_obj.get_pos()
            scrolled_rel_mouse = mouse_obj.copy()
            scrolled_rel_mouse.set_pos(abs_pos[0] - self.x - self.x_scroll_offset,
                                       abs_pos[1] - self.y - self.y_scroll_offset)
        else:
            pointer_events = False
            scrolled_rel_mouse = Mouse.Cursor()
            scrolled_rel_mouse.mouse_leave()  # Dummy mouse object to prevent collision.
            if self.z_index != mouse_obj.get_z_index():
                keyboard_events = []
        if self.z_index == mouse_obj.get_z_index():
            abs_pos = mouse_obj.get_pos()
            rel_mouse = mouse_obj.copy()
            rel_mouse.set_pos(abs_pos[0] - self.x, abs_pos[1] - self.y)
        else:
            rel_mouse = Mouse.Cursor()
            rel_mouse.mouse_leave()
        mouse_blocked = False
        for w_name in self.scrollbar_names:
            self.raise_widget_layer(w_name)  # Ensures scrollbar is topmost
            if self.child_widgets[w_name].mouse_colliding(rel_mouse):
                mouse_blocked = True
                break
        collide = False
        return_values = []
        if mouse_blocked:
            scrolled_rel_mouse.mouse_leave()
            collide = True
        for widget in self.child_widgets.values():
            if not collide:
                collide = bool(pygame.sprite.collide_mask(widget, scrolled_rel_mouse)) if hasattr(widget, "mask")\
                          else pygame.sprite.collide_rect(widget, scrolled_rel_mouse)
            w_name = widget.get_widget_name()
            if self.new_size:
                if isinstance(widget, ScrollBar):
                    widget.resize_scrollbar((self.width, self.height))
                else:
                    new_pos = [self.width * (self.real_positions[w_name][0] / self.real_width),
                               self.height * (self.real_positions[w_name][1] / self.real_height)]
                    if w_name in self.resize_exclude:
                        if self.resize_exclude[w_name] == "x":
                            new_pos[0] = None
                        elif self.resize_exclude[w_name] == "y":
                            new_pos[1] = None
                        elif self.resize_exclude[w_name] == "both":
                            new_pos = [None, None]
                    self.update_widget_pos(widget, tuple(new_pos), anchor="center")
            if isinstance(widget, Entry):
                value = widget.update(scrolled_rel_mouse, keyboard_events)
                return_values.append(value)
            elif isinstance(widget, ScrollBar):
                widget.update(rel_mouse, keyboard_events)
            else:
                widget.update(scrolled_rel_mouse, keyboard_events)
        if self.new_size:
            self.new_size = False
            self.resize_exclude.clear()
        if return_values:
            if any(i[2] for i in return_values):
                if not self.text_input:
                    self.text_input = True
                    pygame.key.start_text_input()
            else:
                if self.text_input:
                    self.text_input = False
                    pygame.key.stop_text_input()
            if any(i[1] for i in return_values):
                if self.cursor_display != "text_drag":
                    self.cursor_display = "text_drag"
                    pygame.mouse.set_cursor(self.cursor_icons.get_cursor(2))
            elif any(i[0] for i in return_values):
                if self.cursor_display != "i_beam":
                    self.cursor_display = "i_beam"
                    pygame.mouse.set_cursor(self.cursor_icons.get_cursor(1))
            else:
                if self.cursor_display != "arrow":
                    self.cursor_display = "arrow"
                    pygame.mouse.set_cursor(self.cursor_icons.get_cursor(0))
        self.render_widgets()
        if pointer_events and (not collide):
            mouse_obj.increment_z_index()

    def render_widgets(self) -> None:
        self.image.fill(self.bg)
        for w_name in self.render_z_order:
            widget_pos = (self.child_widgets[w_name].x
                          + (0 if isinstance(self.child_widgets[w_name], ScrollBar) else self.x_scroll_offset),
                          self.child_widgets[w_name].y
                          + (0 if isinstance(self.child_widgets[w_name], ScrollBar) else self.y_scroll_offset))
            if widget_pos[0] + self.child_widgets[w_name].image.get_width() >= 0 and \
               widget_pos[0] < self.width and \
               widget_pos[1] + self.child_widgets[w_name].image.get_height() >= 0 and \
               widget_pos[1] < self.height:
                self.image.blit(self.child_widgets[w_name].image, widget_pos)

    def raise_widget_layer(self, widget_name: str) -> None:
        """
        Raises the widget with the given name to the top of the render z-order.
        """
        if widget_name in self.render_z_order:
            # Move the widget name to the end of the list.
            index = self.render_z_order.index(widget_name)
            if index < len(self.render_z_order) - 1:
                self.render_z_order.append(self.render_z_order.pop(index))
        else:
            raise WidgetIDError(widget_name)

    def update_position(self, new_x: int, new_y: int) -> None:
        self.x = new_x
        self.y = new_y
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)


class OptionMenu(BaseWidget):
    def __init__(self, pos: t.Tuple[t.Union[int, float], t.Union[int, float]],
                 size: t.Tuple[t.Union[int, float], t.Union[int, float]], padding: int, font: pygame.font.Font,
                 options: t.Tuple[str, ...], menu_side: t.Literal["top", "bottom"],
                 menu_height: int, widget_name: str = "!option_menu"):
        """OptionMenu widget. Takes a tuple of strings as the options to be displayed. The 'get_info' method can be
        called to get the currently selected option and whether the selected option has changed since the last call."""
        super().__init__(widget_name)
        self.x = pos[0]
        self.y = pos[1] - (menu_height if menu_side == "top" else 0)
        self.width, self.height = size
        self.padding = padding
        self.font = font
        self.options = options
        self.opt_height = self.height
        self.text_height = self.opt_height - 2 * self.padding
        self.dropdown_shown = False
        self.scrollbar_size = 20
        self.text_surfs = []
        for opt in self.options:
            self.text_surfs.append(pygame.transform.scale(self.font.render(opt, False, COLORS["BLACK"]),
                                                          (round(self.calc_opt_width(opt)), self.text_height)))
        self.max_width = max(surf.get_width() for surf in self.text_surfs) + 2 * self.padding + self.scrollbar_size
        self.normal_color = (225, 225, 225)
        self.active_color = (229, 241, 251)
        self.current_color = self.normal_color
        self.lock = True
        self.mouse_down = False
        self.frame_mouse = False
        self.force_hide = False
        self.selected_id = 0
        self.opt_changed = False
        self.menu_side = menu_side
        self.dropdown_height = menu_height
        self.dropdown: t.Optional[Frame] = None
        self.image: t.Optional[pygame.Surface] = None
        self.rect: t.Optional[pygame.Rect] = None
        self.hit_box = pygame.Rect(0, self.dropdown_height if self.menu_side == "top" else 0, self.width, self.height)
        self.arrow_rect = pygame.Rect(self.width - self.height, self.hit_box.y, self.height, self.height)
        self.arrow_size = (self.height - 15, self.height - 25)

    def set_parent(self, parent_widget: Frame) -> None:
        self.parent = parent_widget
        use_h_scroll = False
        shortened_w = 0
        if self.x + self.max_width > self.parent.width:
            use_h_scroll = True
            shortened_w = self.parent.width - self.x
        self.rect = pygame.Rect(self.x, self.y - (self.dropdown_height if self.menu_side == "top" else 0),
                                max(self.width, shortened_w if use_h_scroll else self.max_width),
                                self.height + self.dropdown_height)
        self.image = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        self.dropdown = Frame(0, self.height if self.menu_side == "bottom" else 0,
                              shortened_w if use_h_scroll else self.max_width, self.dropdown_height,
                              self.scrollbar_size, bg=(255, 255, 255), z_index=self.parent.z_index,
                              widget_name="!option_menu_subframe")
        for opt_idx in range(len(self.options)):
            self.dropdown.add_widget(Option((0, opt_idx * self.opt_height),
                                            (self.max_width - self.scrollbar_size, self.opt_height), self.padding,
                                            self.text_surfs[opt_idx], opt_idx, self.option_callback,
                                            widget_name="!option{}".format(opt_idx)))
        self.dropdown.add_widget(ScrollBar(width=self.scrollbar_size, orientation="vertical", shorten=use_h_scroll,
                                           widget_name="!v_scroll"))
        if use_h_scroll:
            self.dropdown.add_widget(ScrollBar(width=self.scrollbar_size, orientation="horizontal", shorten=True,
                                               widget_name="!h_scroll"))

    def get_real_pos(self, anchor: t.Literal["nw", "center"]) -> t.Tuple[t.Union[int, float], t.Union[int, float]]:
        """Returns the position of the widget not including the dropdown."""
        nw = (self.x + self.hit_box.x, self.y + self.hit_box.y)
        if anchor == "nw":
            return nw
        else:
            return nw[0] + self.width / 2, nw[1] + self.height / 2

    def update_position(self, new_pos: t.Tuple[t.Union[int, float], t.Union[int, float]],
                        anchor: t.Literal["nw", "center"]) -> None:
        if anchor == "nw":
            self.x = new_pos[0]
            self.y = new_pos[1] - (self.dropdown_height if self.menu_side == "top" else 0)
        else:
            self.x = new_pos[0] - self.width / 2
            self.y = new_pos[1] - (self.dropdown_height if self.menu_side == "top" else 0) - self.hit_box.height / 2
        self.rect.x, self.rect.y = self.x, self.y

    def render_surface(self) -> None:
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, self.current_color, [self.hit_box.x, self.hit_box.y,
                                                          self.hit_box.width, self.hit_box.height])
        self.image.blit(self.text_surfs[self.selected_id], (self.padding, self.hit_box.y + self.padding),
                        area=[0, 0, self.arrow_rect.x - self.padding, self.text_height])
        draw_arrow(self.image, COLORS["GREY7"],
                   (self.arrow_rect.x + (self.arrow_rect.width / 2 - self.arrow_size[0] / 2),
                    self.arrow_rect.y + (self.arrow_rect.height / 2 - self.arrow_size[1] / 2)),
                   self.arrow_size, "down", 3)
        if self.dropdown_shown:
            self.image.blit(self.dropdown.image, self.dropdown.rect)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        abs_x, abs_y = mouse_obj.get_pos()
        rel_mouse = mouse_obj.copy()
        rel_mouse.set_pos(abs_x - self.x, abs_y - self.y)
        if self.dropdown.rect.colliderect(rel_mouse):
            if rel_mouse.get_button_state(1):
                self.frame_mouse = True
            else:
                self.frame_mouse = False
        else:
            if rel_mouse.get_button_state(1) and not self.frame_mouse:
                if self.dropdown_shown:
                    self.force_hide = True
                    self.dropdown_shown = False
            elif not rel_mouse.get_button_state(1):
                self.frame_mouse = False
        if self.dropdown_shown:
            self.dropdown.update(rel_mouse, keyboard_events)
        collide = self.hit_box.collidepoint(*rel_mouse.get_pos())
        if not collide:
            if not mouse_obj.get_button_state(1):
                if not self.dropdown_shown:
                    self.force_hide = False
                self.mouse_down = False
            self.lock = True
            self.current_color = self.normal_color
        else:
            if mouse_obj.get_button_state(1) and (not self.lock):
                self.mouse_down = True
            elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                self.mouse_down = False
                if self.force_hide:
                    self.force_hide = False
                else:
                    self.dropdown_shown = True
            elif mouse_obj.get_button_state(1) and self.lock:
                self.force_hide = False
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()

    def calc_opt_width(self, opt_text: str) -> float:
        text_size = self.font.size(opt_text)
        return self.text_height * (text_size[0] / text_size[1])

    def option_callback(self, opt_id: int) -> None:
        self.selected_id = opt_id
        self.opt_changed = True
        self.dropdown_shown = False

    def get_info(self) -> t.Tuple[int, bool]:
        """Intended to be called from outside the class, will return the selected option and whether it has changed
        since the last call."""
        val = False
        if self.opt_changed:
            val = True
            self.opt_changed = False
        return self.selected_id, val


class Option(BaseWidget):
    def __init__(self, pos: t.Tuple[t.Union[int, float], t.Union[int, float]],
                 size: t.Tuple[int, int], padding: int, text_surf: pygame.Surface,
                 opt_id: int, callback: t.Callable[[int], None], widget_name: str = "!option"):
        super().__init__(widget_name)
        self.x, self.y = pos
        self.width, self.height = size
        self.opt_id = opt_id
        self.callback = callback
        self.text_surf = text_surf
        self.normal_color = COLORS["WHITE"]
        self.active_color = (0, 120, 215)
        self.current_color = self.normal_color
        self.padding = padding
        self.lock = True
        self.mouse_down = False
        self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def get_text_surf(self) -> pygame.Surface:
        return self.text_surf

    def render_surface(self) -> None:
        self.image.fill(self.current_color)
        self.image.blit(self.text_surf, (self.padding, self.padding))

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
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
                self.callback(self.opt_id)
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()


class NodeLoader(threading.Thread):
    def __init__(self, abs_path: str, loader_func: t.Callable[[str, threading.Event], None]):
        super().__init__()
        self.abs_path = abs_path
        self.loader_func = loader_func
        self.canceled = threading.Event()  # Whether the node that this thread is in charge of loading is still expanded

    def run(self) -> None:
        self.loader_func(self.abs_path, self.canceled)


class DirTree(Frame):
    def __init__(self, x: t.Union[int, float], y: t.Union[int, float], width: int, height: int, font: pygame.font.Font,
                 entry_height: int, scroll_padding: int, entry_text_pad: int, entry_btn_pad: int,
                 path_binding: t.Callable[[str], None], widget_name: str = "!dir_tree"):
        """TreeView widget for browsing directories."""
        super().__init__(x, y, width, height, scroll_padding, COLORS["WHITE"], widget_name=widget_name)
        self.font = font
        self.entry_height = entry_height
        self.entry_text_pad = entry_text_pad
        self.entry_btn_pad = entry_btn_pad
        self.path_binding = path_binding  # Callback function to update the text of the path text-box.
        # Directory structure cache will be stored, the function call has an astronomical chance of failing.
        self.cache_path = mkdtemp(prefix="dir_tree_cache_", dir=get_temp_path())
        self.cache_fields = ("filetype", "path")
        self.win_root = "\\\\?\\"  # "\\?\", represents the parent directory of all drive letters.
        self.fs_root = self.win_root if current_os == "Windows" else path.normpath("/")
        self.indent_x = 20
        # Saves widget objects to be added in the next update.
        self.schded_widgets: t.List[t.Union["DirNode", "TextNode"]] = []
        self.schded_del_widgets: t.List[str] = []
        self.nodes: t.List[t.Optional[t.Union[DirNode, TextNode]]] = [
            self.add_widget(DirNode(0, 0, 0, self.fs_root,
                                    self.font, self.entry_height, self.entry_text_pad, self.entry_btn_pad,
                                    self.start_path_loader, self.register_selection, auto_select=True,
                                    widget_name="!dir_node_root"))
        ]
        self.selected_path = self.fs_root
        # {"abs_path": do_continue}, if a path is the key to a False value, the directory structure of that path should
        # not be added as nodes.
        # t.Tuple[str, t.Optional[t.List[str]]] = (abs_path, ["dir1", "dir2", "dir3"]), threads dumps the loaded
        # directory structure here, where the MainThread will create the nodes for it at the next update. If the second
        # tuple item is None, that means an error occurred while loading.
        self.pending_nodes = queue.Queue()
        # Holds thread objects, the exit protocol won't clear the cache until all threads in this list are stopped.
        self.thread_objs: t.Dict[str, t.Union[threading.Thread, NodeLoader]] = {}
        # For holding threads whose starting have been delayed by the fact that the cache is currently being cleared.
        self.spawn_wait_list: t.List[NodeLoader] = []
        self.clean_thread: t.Optional[threading.Thread] = None
        self.safety_lock = threading.Lock()
        self.add_widget(ScrollBar(width=scroll_padding, orientation="vertical", shorten=True, widget_name="!scroll1"))
        self.add_widget(ScrollBar(width=scroll_padding, orientation="horizontal", shorten=True, widget_name="!scroll2"))
        atexit.register(self.clean_cache)

    def set_parent(self, parent_widget: "Frame") -> None:
        self.parent = parent_widget
        self.z_index = self.parent.z_index

    def locate_node_obj(self, abs_path: str) -> int:
        """Returns the index of the node object that represents the specified absolute path."""
        try:
            idx = [node.get_abs_path() if isinstance(node, DirNode) else None for node in self.nodes].index(abs_path)
            return -1 if self.nodes[idx].del_node else idx
        except ValueError:
            return -1

    def clean_threads(self) -> None:
        # Filter out dead threads.
        self.thread_objs = {path_hash: td for path_hash, td in self.thread_objs.items()
                            if td.is_alive() and (type(td) == threading.Thread or not td.canceled.is_set())}

    def start_path_loader(self, mode: t.Literal["expand", "collapse"], abs_path: str) -> bool:
        """Returns True on success, False otherwise."""
        # Do not add widgets using 'self.add_widget' in this method, as this method is called while child widgets are
        # being updated.
        self.clean_threads()
        if mode == "expand":
            path_hash = str(hash(abs_path))
            node_index = self.locate_node_obj(abs_path)
            if node_index == -1 or (path_hash in self.thread_objs
                                    and not self.thread_objs[path_hash].canceled.is_set()):
                return False
            node_obj = self.nodes[node_index]
            # FIXME: Darn this widget, it's still buggy as anything.
            for n_idx in range(node_index + 1, len(self.nodes)):
                self.nodes[n_idx].shift_y_pos(self.entry_height)
            self.nodes.insert(node_index + 1,
                              self.schd_add_w(TextNode(node_obj.x + self.indent_x, node_obj.y + self.entry_height,
                                                       node_obj.get_nested_level() + 1, "Loading...", self.font,
                                                       self.entry_height, self.entry_text_pad,
                                                       widget_name=self.get_free_id("!text_node_{}"
                                                                                    .format(path_hash)))))
            new_thread = NodeLoader(abs_path, self.path_loader_thread)
            if self.clean_thread is not None and self.clean_thread.is_alive():
                # Delay starting of thread
                self.spawn_wait_list.append(new_thread)
            else:
                new_thread.start()
                self.thread_objs[path_hash] = new_thread
        else:
            # Node was un-expanded while it was loading.
            path_hash = str(hash(abs_path))
            if path_hash in self.thread_objs and not self.thread_objs[path_hash].canceled.is_set():
                self.thread_objs[path_hash].canceled.set()
            # Remove all child nodes from frame and memory. The directory structure will be read from memory next time.
            parent_index = self.locate_node_obj(abs_path)
            children_idx = parent_index + 1
            if parent_index == -1:
                return False
            parent_obj = self.nodes[parent_index]
            parent_lvl = parent_obj.get_nested_level()
            index = children_idx
            sel_node = self.locate_node_obj(self.selected_path)
            while index < len(self.nodes) and self.nodes[index].get_nested_level() > parent_lvl:
                if isinstance(self.nodes[index], DirNode) and \
                        str(hash(self.nodes[index].get_abs_path())) in self.thread_objs:
                    self.thread_objs[str(hash(self.nodes[index].get_abs_path()))].canceled.set()
                self.schd_del_w(self.nodes[index].get_widget_name())
                self.nodes[index].del_node = True
                index += 1
            shift_val = (children_idx - index) * self.entry_height  # The amount to shift upwards by
            for node_idx in range(index, len(self.nodes)):
                self.nodes[node_idx].shift_y_pos(shift_val)
            if children_idx <= sel_node < index:
                self.selected_path = parent_obj.get_abs_path()
                sel_node = self.locate_node_obj(self.selected_path)
                if sel_node != -1:
                    self.nodes[sel_node].mod_selection_state(True)
        return True

    def path_loader_thread(self, abs_path: str, cancel: threading.Event) -> None:
        if not os.path.isdir(self.cache_path):  # Create cache directory if it doesn't exist
            with suppress(OSError):
                os.mkdir(self.cache_path)
        sleep(5)
        path_hash = str(hash(abs_path))
        cache_path = os.path.join(self.cache_path, path_hash)
        got_data = False
        dir_data: t.List[str] = []
        if abs_path == self.win_root:
            available_drives = get_drive_letters()
            if available_drives is not None:
                got_data = True
                dir_data = available_drives
        else:
            if os.path.isfile(cache_path):  # Read from cache if it already exists
                got_data, dir_data = self.load_from_cache(cache_path)
            if not got_data:
                got_data, dir_data = self.scan_dir_gen_cache(abs_path, cache_path)
        if not cancel.is_set():  # Only add directory data to the queue if the load had not been canceled.
            self.pending_nodes.put((abs_path, dir_data if got_data else None))

    def load_from_cache(self, cache_path: str) -> t.Tuple[bool, t.List[str]]:
        directories = []
        try:
            with open(cache_path, "r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file, self.cache_fields)
                next(reader)  # Skip header line.
                entry: dict  # Type annotation
                for entry in reader:  # Only add directories.
                    if entry["filetype"] == "directory":
                        directories.append(entry["path"])
        except (OSError, StopIteration):
            return False, []
        else:
            return True, directories

    def scan_dir_gen_cache(self, abs_path: str, cache_path: str) -> t.Tuple[bool, t.List[str]]:
        directories = []
        try:
            with open(cache_path, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, self.cache_fields)
                writer.writeheader()
                for d in os.scandir(abs_path):
                    f_type = ""
                    if d.is_dir():
                        f_type = "directory"
                    elif d.is_file():
                        f_type = "file"
                    if not f_type:  # If object is neither a file nor a directory, ignore it.
                        continue
                    f_dict = {"filetype": f_type, "path": d.path}
                    if f_type == "directory":
                        directories.append(f_dict["path"])
                    writer.writerow(f_dict)
        except OSError:  # On error, delete the cache file as it contains corrupted/incomplete data.
            with suppress(OSError):
                os.remove(cache_path)
            return False, []
        else:
            return True, directories

    def scan_dir_no_errs(self, abs_path: str) -> t.List[str]:
        """Reads directory and returns an empty list both when it is actually empty and when there is an error."""
        if abs_path == self.win_root:
            drives = get_drive_letters()
            return [] if drives is None else drives
        else:
            cache_file = os.path.join(self.cache_path, str(hash(abs_path)))
            return self.scan_dir_gen_cache(abs_path, cache_file)[1]

    def register_selection(self, abs_path: str) -> None:
        if self.selected_path == abs_path:  # Check if the already-selected node was clicked again.
            return None
        old_node = self.locate_node_obj(self.selected_path)
        if old_node != -1:
            self.nodes[old_node].mod_selection_state(False)  # Clear the selection of the previous node.
        self.selected_path = abs_path
        # Updates the path text-box to display the path which the currently selected node represents
        self.path_binding(abs_path)

    def add_pending_nodes(self) -> None:
        """Creates new nodes to represent all newly loaded directory structures since the last update."""
        try:
            while True:
                abs_path, dirs = self.pending_nodes.get(block=False)  # str, t.Optional[t.List[str]]
                parent_index = self.locate_node_obj(abs_path)
                if parent_index == -1:
                    # Either something went wrong, or the node was un-expanded while it was loading
                    self.pending_nodes.task_done()
                    continue
                parent_obj = self.nodes[parent_index]
                parent_y = parent_obj.y
                children_nest_lvls = parent_obj.get_nested_level() + 1
                load_index = parent_index + 1  # Index of the text object that displays "Loading..."
                if not isinstance(self.nodes[load_index], TextNode):
                    self.pending_nodes.task_done()
                    continue
                if dirs is None:
                    self.nodes[load_index].change_text("Error")
                else:
                    for node_idx in range(load_index + 1, len(self.nodes)):
                        # Actually would work as expected even when len(dirs) equals zero, since that would make all
                        # following nodes shift upwards by -self.entry_height to fill the empty space left by the
                        # loading node being removed.
                        self.nodes[node_idx].shift_y_pos((len(dirs) - 1) * self.entry_height)
                    self.delete_widget(self.nodes[load_index].get_widget_name())
                    self.nodes[load_index:load_index + 1] = [
                        self.add_widget(DirNode(children_nest_lvls * self.indent_x,
                                                parent_y + index * self.entry_height, children_nest_lvls, dir_path,
                                                self.font, self.entry_height, self.entry_text_pad, self.entry_btn_pad,
                                                self.start_path_loader, self.register_selection,
                                                widget_name=self.get_free_id("!dir_node_{}".format(hash(dir_path)))))
                        for index, dir_path in enumerate(dirs, start=1)
                    ]
                self.pending_nodes.task_done()
        except queue.Empty:  # The queue has been exhausted
            return None

    def schd_add_w(self, node_obj: t.Union["DirNode", "TextNode"]) -> t.Union["DirNode", "TextNode"]:
        """Schedules a node to be added the next time the 'update' method is called."""
        self.schded_widgets.append(node_obj)
        return node_obj

    def add_widget(self, widget_obj: t.Union[BaseWidget, RadioGroup]) -> t.Optional[t.Union["DirNode", "TextNode"]]:
        """After adding widget, will return the widget object if it's a DirNode or TextNode."""
        super().add_widget(widget_obj)
        if isinstance(widget_obj, DirNode) or isinstance(widget_obj, TextNode):
            return widget_obj
        else:
            return None

    def schd_del_w(self, widget_id: str) -> None:
        print("Widget registered to be deleted")
        self.schded_del_widgets.append(widget_id)

    def run_schded_tasks(self) -> None:
        while self.schded_widgets:
            self.add_widget(self.schded_widgets.pop(0))  # Adds scheduled widgets in the same order they were scheduled
        while self.schded_del_widgets:
            with suppress(WidgetIDError):
                self.delete_widget(self.schded_del_widgets.pop(0))
        if self.clean_thread is None or not self.clean_thread.is_alive():  # clean_thread is not running
            threading.Thread(target=self.run_del_nodes).start()

    def run_del_nodes(self) -> None:
        self.safety_lock.acquire()
        self.nodes[:] = [n for n in self.nodes if not n.del_node]
        self.safety_lock.release()

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        self.run_schded_tasks()
        self.add_pending_nodes()
        super().update(mouse_obj, keyboard_events)

    def reload_dirs(self) -> None:
        dir_stack: t.List[t.List[str]] = [self.scan_dir_no_errs(self.fs_root)]
        stack_idx: t.List[int] = [0]
        flat_idx = 1
        if not dir_stack[0]:  # Failed to read root directory
            return None
        while True:
            if not dir_stack or flat_idx >= len(self.nodes):
                break
            if not stack_idx[-1] < len(dir_stack[-1]):
                nest_lvl = len(stack_idx)
                pop_count = 0
                while flat_idx < len(self.nodes) and self.nodes[flat_idx].get_nested_level() == nest_lvl:
                    print("scheduling widget deletion")
                    self.schd_del_w(self.nodes.pop(flat_idx).get_widget_name())
                    pop_count += 1
                if pop_count > 0:
                    shift_amount = -self.entry_height * pop_count
                    for idx in range(flat_idx, len(self.nodes)):
                        self.nodes[idx].shift_y_pos(shift_amount)
                dir_stack.pop()
                stack_idx.pop()
                continue
            if isinstance(self.nodes[flat_idx], TextNode):
                pass  # Skip to the next node.
            elif self.nodes[flat_idx].get_abs_path() == dir_stack[-1][stack_idx[-1]]:  # The correct node exists
                if self.nodes[flat_idx].is_expanded():
                    stack_idx[-1] += 1
                    flat_idx += 1
                    dir_stack.append(self.scan_dir_no_errs(self.nodes[flat_idx - 1].get_abs_path()))
                    stack_idx.append(0)
                    continue
            else:
                abs_path = dir_stack[-1][stack_idx[-1]]
                self.nodes.insert(flat_idx, DirNode(len(stack_idx) * self.indent_x, self.nodes[flat_idx].y,
                                                    len(stack_idx), abs_path, self.font,
                                                    self.entry_height, self.entry_text_pad, self.entry_btn_pad,
                                                    self.start_path_loader, self.register_selection,
                                                    widget_name=self.get_free_id("!dir_node_{}"
                                                                                 .format(hash(abs_path)))))
                self.schd_add_w(self.nodes[flat_idx])
                for idx in range(flat_idx + 1, len(self.nodes)):
                    self.nodes[idx].shift_y_pos(self.entry_height)
            stack_idx[-1] += 1
            flat_idx += 1

    def get_free_id(self, name: str) -> str:
        """Ensures that the given ID can be successfully used as a widget ID without collisions by adding a numeric
        suffix to it."""
        new_name = name
        suffix = 1
        while True:
            if new_name not in self.child_widgets:
                return new_name
            new_name = "{}_{}".format(name, suffix)
            suffix += 1

    def refresh(self) -> None:
        """This method is run when the user clicks the "Refresh" button."""
        if self.clean_thread is not None and self.clean_thread.is_alive():
            return None
        self.clean_thread = threading.Thread(target=self.clean_cache, args=(True,))
        self.clean_thread.start()

    def clean_cache(self, user_initiated: bool = False) -> None:
        """Clears cache and updates the TreeView. The latter does not happen if the interpreter is exiting."""
        print("Refresh thread waiting to start...")
        for thread in self.thread_objs.values():
            # Wait until every thread has finished, since attempting to removing the cache directory while running
            # threads are still reading or writing to it would cause an exception.
            thread.join()
        self.clean_threads()
        self.pending_nodes.join()  # Wait for queue to empty.
        self.safety_lock.acquire()
        print("Refresh thread running.")
        sleep(5)
        if user_initiated:
            for file in os.scandir(self.cache_path):  # Empties cache directory.
                with suppress(OSError):
                    os.remove(file.path)
            self.reload_dirs()  # Re-generates cache for all currently expanded nodes.
        else:
            with suppress(OSError):
                rmtree(self.cache_path)
        self.safety_lock.release()
        for delayed_thread in self.spawn_wait_list:
            delayed_thread.start()  # Start all threads whose starting was delayed due to this thread running.
            self.thread_objs[str(hash(delayed_thread.abs_path))] = delayed_thread
        self.spawn_wait_list.clear()
        print("Refresh thread done.")


class TextNode(BaseWidget):
    def __init__(self, x: int, y: int, nest_level: int, text: str, font: pygame.font.Font, height: int, padding: int,
                 widget_name: str = "!loading_node"):
        super().__init__(widget_name)
        self.x = x
        self.y = y
        self.nest_level = nest_level
        self.font = font
        self.padding = padding
        self.text_height = height - 2 * self.padding
        self.width = 0
        self.height = height
        self.image: t.Optional[pygame.Surface] = None
        self.rect: t.Optional[pygame.Rect] = None
        self.del_node = False
        self.change_text(text)

    def calc_opt_width(self, opt_text: str) -> float:
        text_size = self.font.size(opt_text)
        return self.text_height * (text_size[0] / text_size[1])

    def change_text(self, new_text: str) -> None:
        text_size = (self.calc_opt_width(new_text), self.text_height)
        text_surf = pygame.transform.scale(self.font.render(new_text, False, COLORS["BLACK"]), text_size)
        self.width = text_surf.get_width() + 2 * self.padding
        self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.image.fill(COLORS["WHITE"])
        self.image.blit(text_surf, (self.padding, self.padding))

    def shift_y_pos(self, rel_y: int) -> None:
        self.y += rel_y
        self.rect.y = self.y

    def get_nested_level(self) -> int:
        return self.nest_level


class DirNode(BaseWidget):
    def __init__(self, x: int, y: int, nest_level: int, abs_path: str, font: pygame.font.Font, height: int,
                 text_pad: int, btn_pad: int, toggle_expand: t.Callable[[t.Literal["expand", "collapse"], str], bool],
                 click_func: t.Callable[[str], None], auto_select: bool = False,
                 widget_name: str = "!dir_node"):
        super().__init__(widget_name)
        self.x, self.y = x, y
        self.nest_level = nest_level
        self.font = font
        self.text_pad = text_pad
        self.btn_pad = btn_pad
        self.text_height = height - 2 * self.text_pad
        self.abs_path = abs_path  # Stores the full path to the directory this node represents.
        self.toggle_expand = toggle_expand
        self.click_func = click_func
        if self.abs_path == "\\\\?\\":  # Windows filesystem root
            self.text = "This PC"
        elif self.abs_path == path.sep:  # Linux filesystem root
            self.text = path.sep
        elif path.basename(self.abs_path) == "":  # Windows drive letter, e.g. "C:\"
            self.text = self.abs_path  # Display as is.
        else:  # Normal path to a folder, e.g. "C:\Users\Administrator\Documents"
            self.text = path.basename(self.abs_path)  # Display last component of path
        self.text_surf = pygame.transform.scale(self.font.render(self.text, False, COLORS["BLACK"]),
                                                (self.calc_opt_width(self.text), self.text_height))
        self.arrow_padding = 5
        self.arrow_obj = NodeButton(0, self.arrow_padding, height - 2 * self.arrow_padding)
        self.width = self.arrow_obj.rect.width + self.btn_pad + 2 * self.text_pad + self.text_surf.get_width()
        self.height = height
        self.node_rect = pygame.Rect(self.arrow_obj.rect.width + self.btn_pad, 0,
                                     self.width - self.arrow_obj.rect.width, self.height)
        self.selected = auto_select  # Will be 'False' unless caller explicitly says otherwise.
        self.lock = True
        self.mouse_down = False
        self.normal_color = COLORS["WHITE"]
        self.active_color = (205, 232, 255)
        self.del_node = False
        self.image = pygame.Surface((self.width, self.height))
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def render_surface(self) -> None:
        self.image.fill(COLORS["WHITE"])
        self.image.blit(self.arrow_obj.image, self.arrow_obj.rect)
        pygame.draw.rect(self.image, self.active_color if self.selected else self.normal_color, self.node_rect)
        self.image.blit(self.text_surf, (self.arrow_obj.rect.width + self.btn_pad + self.text_pad, self.text_pad))

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: t.List[pygame.event.Event]) -> None:
        rel_mouse = mouse_obj.copy()
        abs_x, abs_y = mouse_obj.get_pos()
        rel_mouse.set_pos(abs_x - self.x, abs_y - self.y)
        clicked, direction = self.arrow_obj.update(rel_mouse)
        if clicked:
            # noinspection PyTypeChecker
            # Calls the callback in TreeView to start a new thread for loading. The result will be stored in a queue
            # in TreeView, and it will create the new child nodes at the next widget update.
            if not self.toggle_expand("collapse" if direction == "right" else "expand", self.abs_path):
                self.arrow_obj.direction = "down" if direction == "right" else "right"
        else:
            collide = self.node_rect.collidepoint(*rel_mouse.get_pos())
            if not collide:
                if not mouse_obj.get_button_state(1):
                    self.mouse_down = False
                self.lock = True
            else:
                if mouse_obj.get_button_state(1) and (not self.lock):
                    self.mouse_down = True
                elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                    self.mouse_down = False
                    self.selected = True
                    self.click_func(self.abs_path)
                    if pygame.key.get_mods() & pygame.KMOD_CTRL:
                        launch_file_mgr(self.abs_path)
                if not mouse_obj.get_button_state(1):
                    self.lock = False
            self.render_surface()

    def mod_selection_state(self, new_state: bool) -> None:
        self.selected = new_state  # The TreeView uses this method to clear the selection state.

    def shift_y_pos(self, rel_y: int) -> None:
        self.y += rel_y
        self.rect.y = self.y

    def get_abs_path(self) -> str:
        return self.abs_path

    def get_nested_level(self) -> int:
        return self.nest_level

    def is_expanded(self) -> bool:
        return self.arrow_obj.direction == "down"

    def calc_opt_width(self, opt_text: str) -> float:
        text_size = self.font.size(opt_text)
        return self.text_height * (text_size[0] / text_size[1])


class NodeButton(pygame.sprite.Sprite):
    def __init__(self, x: t.Union[int, float], y: t.Union[int, float], length: int):
        super().__init__()
        self.x, self.y = x, y
        self.length = length
        self.normal_color = COLORS["GREY5"]
        self.active_color = (85, 211, 249)
        self.current_color = self.normal_color
        self.direction: t.Literal["right", "down"] = "right"
        self.arrow_size_r = (length - 10, length - 2)
        self.arrow_size_d = (length - 2, length - 10)
        self.lock = True
        self.mouse_down = False
        self.image = pygame.Surface((self.length, self.length))
        self.rect = pygame.Rect(self.x, self.y, self.length, self.length)

    def render_surface(self) -> None:
        self.image.fill(COLORS["WHITE"])
        if self.direction == "right":
            pos = (self.length / 2 - self.arrow_size_r[0] / 2, self.length / 2 - self.arrow_size_r[1] / 2)
        else:
            pos = (self.length / 2 - self.arrow_size_d[0] / 2, self.length / 2 - self.arrow_size_d[1] / 2)
        draw_arrow(self.image, self.current_color, pos,
                   self.arrow_size_r if self.direction == "right" else self.arrow_size_d, self.direction, 3)

    def update(self, mouse_obj: Mouse.Cursor) -> t.Tuple[bool, t.Literal["right", "down"]]:
        collide = self.rect.collidepoint(*mouse_obj.get_pos())
        clicked = False
        self.direction: t.Literal["right", "down"]
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
                clicked = True
                if self.direction == "right":
                    self.direction = "down"
                else:
                    self.direction = "right"
            if not mouse_obj.get_button_state(1):
                self.lock = False
            self.current_color = self.active_color
        self.render_surface()
        return clicked, self.direction


class Window(pygame.sprite.Sprite):
    def __init__(self,
                 x: t.Union[int, float],
                 start_y: t.Union[int, float],
                 final_y: t.Union[int, float],
                 bg: t.Tuple[int, int, int],
                 overlay_max_alpha: int,
                 active_color: t.Tuple[int, int, int],
                 dormant_color: t.Tuple[int, int, int],
                 border_radius: int,
                 button_length: int,
                 button_padding: int,
                 button_thickness: int,
                 speed_factor: float,
                 content_frame: Frame,
                 destination_surf: pygame.Surface,
                 z_index: int):
        """A popup-window widget that takes a frame instance to be used as its content. The window has a nice entry and
        exit animation, and contains a close button in its title bar."""
        super().__init__()
        self.x = x
        self.y = start_y
        self.start_y = start_y
        self.final_y = final_y
        self.content_frame = content_frame
        self.content_pos = (border_radius, border_radius + button_length + button_padding)
        self.width = border_radius * 2 + self.content_frame.width
        self.height = border_radius * 2 + button_length + button_padding + self.content_frame.height
        self.distance = self.start_y - self.final_y
        self.direction: t.Literal["u", "d", "i", "r"] = "u"
        self.bg = bg
        self.destination_surf = destination_surf
        self.z_index = z_index
        self.close_button = WindowButton(self.width - border_radius - button_length,
                                         border_radius,
                                         button_length,
                                         button_thickness,
                                         active_color,
                                         dormant_color)
        self.overlay = WindowOverlay(self.destination_surf.get_width(),
                                     self.destination_surf.get_height(),
                                     overlay_max_alpha,
                                     self.distance)
        self.border_radius = border_radius
        self.speed_factor = speed_factor
        self.timer = Time.Time()
        self.timer.reset_timer()
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def render_surface(self) -> None:
        self.image.fill((0, 0, 0, 0))
        draw_rounded_rect(self.image, (0, 0), (self.width, self.height), self.border_radius, self.bg)
        self.image.blit(self.content_frame.image, self.content_pos)
        self.image.blit(self.close_button.image, self.close_button.rect)

    def update(self, mouse_obj: Mouse.Cursor, keyboard_events: list[pygame.event.Event]) -> bool:
        updated_mouse = mouse_obj.copy()
        rel_mouse = mouse_obj.copy()
        rel_mouse.set_pos(mouse_obj.get_pos()[0] - self.x, mouse_obj.get_pos()[1] - self.y)
        if self.z_index != mouse_obj.get_z_index():
            updated_mouse.mouse_leave()
            rel_mouse.mouse_leave()
            keyboard_events = []
        if self.direction in ("u", "d"):
            delta_time = self.timer.get_time()
            self.timer.reset_timer()
            self.distance *= pow(self.speed_factor, delta_time)
            if round(self.distance) > 0:
                self.y = self.final_y + self.distance if self.direction == "u" else self.start_y - self.distance
            else:
                self.y = self.final_y if self.direction == "u" else self.start_y
                self.direction = "i" if self.direction == "u" else "r"
            self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
            self.content_frame.update_position(self.x + self.content_pos[0], self.y + self.content_pos[1])
            dummy_mouse = mouse_obj.copy()
            dummy_mouse.mouse_leave()
            self.close_button.update(dummy_mouse)
            self.overlay.update(self.start_y - self.y)
        elif self.direction == "i":
            if self.close_button.update(rel_mouse):
                self.close_window()
        self.content_frame.update(updated_mouse, keyboard_events)
        self.render_surface()
        return self.direction == "r"

    def draw(self) -> None:
        self.destination_surf.blit(self.overlay.image, self.overlay.rect)
        self.destination_surf.blit(self.image, self.rect)

    def close_window(self, bypass_idle_check: bool = False) -> None:
        if self.direction == "i" or bypass_idle_check:
            self.distance = self.start_y - self.final_y
            self.direction = "d"
            self.timer.reset_timer()


class WindowButton(pygame.sprite.Sprite):
    def __init__(self,
                 x: t.Union[int, float],
                 y: t.Union[int, float],
                 length: int,
                 thickness: int,
                 active_color: t.Tuple[int, int, int],
                 dormant_color: t.Tuple[int, int, int]):
        super().__init__()
        self.x = x
        self.y = y
        self.width = length
        self.height = length
        self.thickness = thickness
        self.active_color = active_color
        self.dormant_color = dormant_color
        self.current_color = self.dormant_color
        self.lock = True
        self.mouse_down = False
        self.image = pygame.Surface((self.width, self.height))
        self.image.set_colorkey(COLORS["TRANSPARENT"])
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def render_surface(self) -> None:
        self.image.fill(COLORS["TRANSPARENT"])
        draw_cross(self.image, (0, 0), (self.width, self.height), self.thickness, self.current_color)

    def update(self, mouse_obj: Mouse.Cursor) -> bool:
        collision = pygame.sprite.collide_rect(self, mouse_obj)
        clicked = False
        if collision:
            if mouse_obj.get_button_state(1) and not self.mouse_down and not self.lock:
                self.mouse_down = True
            elif not mouse_obj.get_button_state(1):
                if self.mouse_down:
                    self.mouse_down = False
                    clicked = True
                self.lock = False
            self.current_color = self.active_color
        else:
            if not mouse_obj.get_button_state(1) and self.mouse_down:
                self.mouse_down = False
            self.lock = True
            self.current_color = self.dormant_color
        self.render_surface()
        return clicked


class BaseOverlay:
    def __init__(self, width: int, height: int):
        """Base class for all effects that places a partially transparent overlay over the screen."""
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.image = pygame.Surface((self.width, self.height))
        self.image.fill(COLORS["BLACK"])
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def resize(self, new_size: t.Tuple[int, int]) -> None:
        old_alpha = self.image.get_alpha()
        self.image = pygame.Surface(new_size)
        self.image.set_alpha(old_alpha)
        self.rect.width, self.rect.height = new_size


class SceneTransition(BaseOverlay):
    def __init__(self, width: int, height: int, speed: int, callback: t.Callable[[], None]):
        """A simple transition effect. The screen will steadily darken until fully black, then the same animation is
        played in reverse until fully transparent. This transition is useful for making scene-changes less abrupt."""
        super().__init__(width, height)
        self.alpha = 0
        self.speed = speed
        self.max_alpha = 255
        self.callback = callback
        self.timer = Time.Time()
        self.timer.reset_timer()

    def update(self) -> int:
        """Returns 1 on the frame the animation enters the second stage, and returns 2 when the animation is done, else
        returns 0."""
        return_code = 0
        delta_time = self.timer.get_time()
        self.timer.reset_timer()
        self.alpha += self.speed * delta_time
        if self.alpha >= self.max_alpha:
            self.speed = -self.speed
            self.alpha = self.max_alpha - self.alpha % self.max_alpha
            self.callback()
            return_code = 1
        elif self.alpha < 0:
            self.alpha = 0
            return_code = 2
        self.image.set_alpha(round(self.alpha))
        return return_code


class WindowOverlay(BaseOverlay):
    def __init__(self, width: int, height: int, max_alpha: int, total_distance: t.Union[int, float]):
        """Darkens the screen by an amount proportionate to the distance the window has moved from the edge of the
        screen as it plays its entry animation. The same animation is played in reverse when the window plays its exit
        animation. This effect is useful for directing the user's attention to the active window."""
        super().__init__(width, height)
        self.alpha = 0
        self.max_alpha = max_alpha
        self.total_distance = total_distance

    def update(self, moved_distance: t.Union[int, float]) -> None:
        self.alpha = self.max_alpha * (moved_distance / self.total_distance)
        self.image.set_alpha(round(self.alpha))


class WidgetIDError(Exception):
    def __init__(self, widget_id: str):
        """This exception is raised if a non-existent widget identifier is passed to a frame method."""
        super().__init__("A widget with the ID '{}' doesn't exist in this frame".format(widget_id))
        self.widget_id = widget_id

    def get_failed_id(self) -> str:
        return self.widget_id


class FrameError(Exception):
    def __init__(self, widget: BaseWidget, error_type: int):
        """A simple exception class for handling frame-related errors."""
        if error_type == 1:
            message = "The frame already contains a widget with the ID '{}'"\
                .format(widget.get_widget_name())
        elif error_type == 2:
            message = "The widget with the ID '{}' has already been added to a parent frame"\
                .format(widget.get_widget_name())
        else:
            message = "Unknown error"
        super().__init__(message)
        self.failed_widget = widget

    def get_failed_widget(self) -> BaseWidget:
        return self.failed_widget
