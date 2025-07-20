from Util import *
import Time
import pygame
if tp.TYPE_CHECKING:
    import Mouse


class ToastNotifier(pygame.sprite.Sprite):
    def __init__(self, resolution: tp.Tuple[int, int], icon: pygame.Surface, y_pos: int, message_title: str,
                 message_text: str, toast_id: int):
        super().__init__()
        self.id = toast_id
        self.title_font = pygame.font.SysFont("arial", 25)
        self.body_font = pygame.font.SysFont("arial", 23)
        self.icon_img = icon
        self.image_padding = 15
        self.resolution = resolution
        self.x = self.resolution[0]
        self.y = y_pos
        self.width = 400
        self.corner_radius = 19
        # Close button costumes: (Not hovered, hovered, hidden)
        self.close_btn_thickness = 4
        self.close_btn_size = (19, 19)
        self.close_btn_costumes = (pygame.Surface(self.close_btn_size), pygame.Surface(self.close_btn_size), None)
        self.close_btn_colors = (COLORS["GREY6"], COLORS["RED"])
        for index, surf in enumerate(self.close_btn_costumes[:-1]):
            surf.set_colorkey(COLORS["TRANSPARENT"])
            surf.fill(COLORS["TRANSPARENT"])
            draw_cross(surf, (0, 0), self.close_btn_size, self.close_btn_thickness, self.close_btn_colors[index])
        self.close_btn_img = self.close_btn_costumes[0]
        self.close_btn_x = self.width - self.corner_radius - self.close_btn_img.get_size()[0]
        self.close_btn_y = self.corner_radius
        self.close_rect = pygame.Rect(self.close_btn_x, self.close_btn_y, *self.close_btn_img.get_size())
        self.title_text = word_wrap_text(message_title,
                                         self.width - self.corner_radius * 2 - self.icon_img.get_size()[0] -
                                         self.image_padding - self.close_btn_img.get_size()[0],
                                         self.title_font)
        self.body_text = word_wrap_text(message_text,
                                        self.width - self.corner_radius * 2 - self.icon_img.get_size()[0] -
                                        self.image_padding - self.close_btn_img.get_size()[0],
                                        self.body_font)
        self.height = (self.title_font.size("█")[1] * (len(self.title_text) + 1)
                       + self.body_font.size("█")[1] * len(self.body_text)
                       + self.corner_radius * 2)
        self.image = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        self.current_color = COLORS["GREY3"]
        self.lock = True
        self.mouse_down = False
        self.render_surface(self.current_color)
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.mask = pygame.mask.from_surface(self.image)
        # region Physics Variables
        self.direction = "left"
        self.border_padding = 20
        self.dest_x = self.resolution[0] - self.width - self.border_padding
        self.remaining_distance = self.resolution[0] - self.dest_x  # Damp this variable every frame.
        self.damping = 0.05  # Damping constant
        self.delta_time = Time.Time()
        self.delta_time.reset_timer()
        self.notification_timer = Time.Time()
        self.dismiss_timer = 10
        self.physics = None
        self.acceleration = 550
        # endregion

    def render_text(self, font: pygame.font.Font, text: tp.List[str], line_height: int, calc_y: int = 0) -> None:
        for line_number, line_text in enumerate(text):
            text_surf = font.render(line_text, True, COLORS["BLACK"])
            self.image.blit(text_surf, (self.corner_radius + self.icon_img.get_size()[0] + self.image_padding,
                                        self.corner_radius + calc_y + line_height * line_number))

    def render_surface(self, color: tp.Tuple[int, int, int]) -> None:
        self.image.fill((0, 0, 0, 0))
        draw_rounded_rect(self.image, (0, 0), (self.width, self.height), self.corner_radius, color)
        self.image.blit(self.icon_img, (self.corner_radius, self.corner_radius))
        if self.close_btn_img is not None:
            self.image.blit(self.close_btn_img, (self.close_btn_x, self.close_btn_y))
        self.render_text(self.title_font, self.title_text, self.title_font.size("█")[1])
        self.render_text(self.body_font, self.body_text, self.body_font.size("█")[1],
                         self.title_font.size("█")[1] * (len(self.title_text) + 1))

    def calc_damp(self, delta_time: float) -> None:
        self.remaining_distance *= pow(self.damping, delta_time)

    def update_size(self, new_res: tp.Tuple[int, int]) -> None:
        self.dest_x = new_res[0] - self.width - self.border_padding
        self.resolution = new_res

    def update(self, new_res: tp.Optional[tp.Tuple[int, int]] = None) -> bool:
        """Only returns true when this toast notification has completed its exiting animation."""
        if new_res is not None:
            self.update_size(new_res)
        if self.direction == "left":
            time = self.delta_time.get_time()
            self.delta_time.reset_timer()
            self.calc_damp(time)  # Updates remaining distance in-place.
            if round(self.remaining_distance) > 0:
                self.x = self.dest_x + self.remaining_distance
            else:
                self.x = self.dest_x
                self.direction = "idle"
                self.notification_timer.reset_timer()
        elif self.direction == "right":
            time = self.delta_time.get_time()
            self.delta_time.reset_timer()
            self.calc_damp(time)
            if round(self.remaining_distance) > 0:
                self.x = self.resolution[0] - self.remaining_distance
            else:
                self.kill()
                return True
        elif self.direction == "idle":
            if new_res is not None:
                self.x = self.dest_x
            if self.y + self.height + self.border_padding > self.resolution[1]:
                # Do not start dismiss countdown if the toast is partially/completely out of view due to too many toasts
                # being on the screen at the same time.
                self.notification_timer.reset_timer()
            elif self.notification_timer.get_time() > self.dismiss_timer:
                self.dismiss()
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        return False

    def change_y(self, y: int) -> None:
        self.y -= y
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def reset_hover_state(self) -> None:
        self.current_color = COLORS["GREY3"]
        self.render_surface(self.current_color)

    def hover_event(self, mouse_obj: "Mouse.Cursor") -> None:
        # By the time this function starts, this toast is already being touched by the mouse cursor.
        if self.direction == "idle":  # Only process hover events on the close button when the toast is not moving.
            if self.close_rect.collidepoint((mouse_obj.get_pos()[0] - self.x, mouse_obj.get_pos()[1] - self.y)):
                self.close_btn_img = self.close_btn_costumes[1]  # Set button costume to 'hovered'
                if mouse_obj.get_button_state(1) and (not self.lock):
                    self.mouse_down = True
                elif (not mouse_obj.get_button_state(1)) and self.mouse_down:
                    self.dismiss()
                if not mouse_obj.get_button_state(1):
                    self.lock = False
            else:
                if not mouse_obj.get_button_state(1):
                    # The user can cancel the click action by dragging the mouse off the close button and releasing.
                    self.mouse_down = False
                self.lock = True
                self.close_btn_img = self.close_btn_costumes[0]
            if self.close_btn_img is not None:
                # Re-draw close button with the updated costume.
                self.image.blit(self.close_btn_img, (self.close_btn_x, self.close_btn_y))
        # Only re-render if current toast color is incorrect.
        if self.current_color != COLORS["YELLOW"]:
            self.current_color = COLORS["YELLOW"]
            self.render_surface(self.current_color)

    def dismiss(self) -> None:
        self.close_btn_img = self.close_btn_costumes[2]  # No close button.
        self.direction = "right"
        self.render_surface(self.current_color)  # Re-render the toast without the close button.
        self.remaining_distance = self.resolution[0] - self.dest_x
        self.delta_time.reset_timer()

    def get_size(self) -> tp.Tuple[int, int]:
        return self.width, self.height

    def get_id(self) -> int:
        return self.id


class ToastGroup(pygame.sprite.Group):
    def __init__(self, resolution: tp.Tuple[int, int], toast_icons: tp.Dict[str, pygame.Surface], z_index: int):
        super().__init__()
        self.z_index = z_index
        self.resolution = resolution
        self.toast_icons = toast_icons
        self.toasts = []
        self.padding = 10
        self.assign_id = 0  # The ID to assign to the next new toast notifier
        self.last_interacted_obj = None  # Stores the toast that was most recently interacted with by the mouse

    def create_toast(self, icon_name: str, toast_title: str, toast_text: str) -> None:
        if icon_name not in self.toast_icons:
            return None
        new_toast = ToastNotifier(self.resolution, self.toast_icons[icon_name],
                                  (self.padding * (len(self.toasts) + 1)
                                   + sum(toast.get_size()[1] for toast in self.toasts)), toast_title, toast_text,
                                  self.assign_id)
        self.toasts.append(new_toast)
        self.add(new_toast)
        self.assign_id += 1

    def update(self, new_res: tp.Optional[tp.Tuple[int, int]] = None) -> None:
        if new_res is not None:
            self.resolution = new_res
        for index, toast in enumerate(self.toasts):
            value = toast.update(new_res)
            if value:
                self.move_up(index)
                self.toasts[index] = None
        self.toasts[:] = [toast for toast in self.toasts if toast is not None]

    def move_up(self, index: int) -> None:
        height = self.toasts[index].get_size()[1] + self.padding
        for i in range(index + 1, len(self.toasts)):
            if self.toasts[i] is not None:
                self.toasts[i].change_y(height)

    def send_mouse_pos(self, mouse_object: "Mouse.Cursor") -> None:
        updated_mouse = mouse_object.copy()
        dummy_mouse = False
        if self.z_index != mouse_object.get_z_index():
            updated_mouse.mouse_leave()
            dummy_mouse = True
        colliding_toast = pygame.sprite.spritecollideany(updated_mouse, self, collided=collide_function)
        if colliding_toast is None:
            # Only pass mouse event to the widget below if the mouse cursor failed to touch a toast notifier.
            if not dummy_mouse:
                mouse_object.increment_z_index()
        else:
            colliding_toast.hover_event(updated_mouse)
        if self.last_interacted_obj is None:
            self.last_interacted_obj = colliding_toast
        else:
            if (colliding_toast is None) or self.last_interacted_obj.get_id() != colliding_toast.get_id():
                self.last_interacted_obj.reset_hover_state()
                self.last_interacted_obj = colliding_toast

    def get_toast_num(self) -> int:
        return len(self.toasts)
