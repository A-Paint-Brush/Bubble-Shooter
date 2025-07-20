#!/usr/bin/env python3
"""
Radial gradient equation without accounting for shape conversions:

trans_color + (cent_color + color_dist * np.clip(dist_fraction, None, 1.0) - trans_color) * \
    (circular_dist(plane) <= radius)

Both arrays have to be converted to an identical shape. Example:

>>> diameter = 3
>>> color = np.array([1, 2, 3], dtype=np.uint8)
>>> dist = np.array([[1, 2, 3],
...                  [4, 5, 6],
...                  [7, 8, 9]], dtype=np.uint8)
>>> color = np.repeat(np.repeat(color[np.newaxis, :], diameter, axis=0)[np.newaxis, :], diameter, axis=0)
>>> output_3d_array(color)
[[  1   2   3] [  1   2   3] [  1   2   3]
 [  1   2   3] [  1   2   3] [  1   2   3]
 [  1   2   3] [  1   2   3] [  1   2   3]]
>>> dist = np.repeat(dist[:, :, np.newaxis], 3, axis=2)
>>> output_3d_array(dist)
[[  1   1   1] [  2   2   2] [  3   3   3]
 [  4   4   4] [  5   5   5] [  6   6   6]
 [  7   7   7] [  8   8   8] [  9   9   9]]
>>> output_3d_array(np.add(color, dist))  # now they are the same shape and can be added together.
[[  2   3   4] [  3   4   5] [  4   5   6]
 [  5   6   7] [  6   7   8] [  7   8   9]
 [  8   9  10] [  9  10  11] [ 10  11  12]]
>>>
"""
import numpy as np
import pygame as pg
import typing as tp
import sys
import os


def get_parent_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.normpath(__file__)), ".."))


def vert_gradient_column(size: tp.Tuple[int, int], top_color: tp.Tuple[int, int, int],
                         bottom_color: tp.Tuple[int, int, int]) -> pg.Surface:
    """Not written by me, credits to 'pygame.examples.vgrade'. Slightly modified. Generates a vertical linear
    gradient"""
    top_color = np.array(top_color, copy=False)
    bottom_color = np.array(bottom_color, copy=False)
    diff = bottom_color - top_color
    height = size[1]
    # create array from 0.0 to 1.0 triplets
    column = np.arange(height, dtype=np.float64) / height
    column = np.repeat(column[:, np.newaxis], [3], 1)
    # create a single column of gradient
    column = top_color + (diff * column).astype(np.int32)
    # make the column a 3d image column by adding X
    column = column.astype(np.uint8)[np.newaxis, :, :]
    surf = pg.Surface(size)
    # 3d array into 2d array, and blit to surface
    pg.surfarray.blit_array(surf, pg.surfarray.map_array(surf, column))
    return surf


def circular_dist(coord_plane: np.ndarray,
                  cent_point: tp.Optional[tp.Tuple[tp.Union[int, float], tp.Union[int, float]]] = None) -> np.ndarray:
    """Returns an array representing each element's distance from a certain point. This point is `cent_point`, and
    defaults to the center of the array if not given."""
    if cent_point is None:
        plane_size = coord_plane.shape[1::-1]
        cent_point = ((plane_size[0] - 1) / 2, (plane_size[1] - 1) / 2)  # Is minus one correct?
    else:
        cent_point = tuple(float(i) for i in cent_point)
    return np.hypot(np.subtract(coord_plane[:, :, 0], cent_point[0]), np.subtract(coord_plane[:, :, 1], cent_point[1]))


def gen_coord_plane(size: tp.Tuple[int, int]) -> np.ndarray:
    """Returns a 3d array representing a coordinate plane, of shape (size[1], size[0], 2)."""
    return np.concatenate((np.repeat(np.arange(size[0], dtype=np.uint32)[np.newaxis, :],
                                     size[1], axis=0)[:, :, np.newaxis],
                           np.repeat(np.arange(size[1], dtype=np.uint32)[:, np.newaxis],
                                     size[0], axis=1)[:, :, np.newaxis]), axis=2)


def color_to_3d(color: np.ndarray, diameter: int) -> np.ndarray:
    """Converts an RGB array of shape `(3, )` to shape `(d, d, 3)`"""
    return np.repeat(np.repeat(color[np.newaxis, :], diameter, axis=0)[np.newaxis, :], diameter, axis=0)


def dist_to_3d(dist: np.ndarray) -> np.ndarray:
    """Converts an array of shape `(n, n)` to shape `(n, n, 3)`"""
    return np.repeat(dist[:, :, np.newaxis], 3, axis=2)


def radial_grad_array(radius: int, cent_color: tp.Tuple[int, int, int],
                      edge_color: tp.Tuple[int, int, int], transparent: tp.Tuple[int, int, int],
                      blend_radius: tp.Union[int, float],
                      blend_center: tp.Optional[tp.Tuple[tp.Union[int, float],
                                                         tp.Union[int, float]]] = None) -> np.ndarray:
    """Returns a 3D array representing the pixels of an image containing a circle with a radial gradient effect. This
    array can then be converted to a Pygame surface and rendered to the screen."""
    diameter = 2 * radius
    cent_color = np.array(cent_color, dtype=np.uint8)
    edge_color = np.array(edge_color, dtype=np.uint8)
    transparent = np.array(transparent, dtype=np.uint8)
    # Generates a 3D array with shape `(size[1], size[0], 2)` representing a coordinate plane.
    plane = gen_coord_plane((diameter,) * 2)
    color_dist = edge_color - cent_color
    dist_fraction = circular_dist(plane, cent_point=blend_center) / float(blend_radius)
    # FIXME: Why does 'blend_center' become inverted???
    trans_color = color_to_3d(transparent, diameter)
    # Should replace all operators with in-place versions in production for improved performance.
    """
    color_grid = trans_color + \
        (color_to_3d(cent_color, diameter) + color_to_3d(color_dist, diameter)
         * dist_to_3d(np.clip(dist_fraction, None, 1.0)) - trans_color) * (dist_to_3d(circular_dist(plane)) <= radius)
    return color_grid.astype(np.uint8)
    """
    # region Debug
    cent_color_3d = color_to_3d(cent_color, diameter)
    color_dist_3d = color_to_3d(color_dist, diameter)
    dist_fraction_clipped = np.clip(dist_fraction, None, 1.0)
    dist_fraction_clipped_3d = dist_to_3d(dist_fraction_clipped)
    reduced_color_dist = color_dist_3d * dist_fraction_clipped_3d
    interpolated_color = cent_color_3d + reduced_color_dist
    print(interpolated_color.dtype)  # should be float64
    remove_extra_trans_color = interpolated_color - trans_color
    outer_cir_dist = circular_dist(plane)
    outer_cir_dist_3d = dist_to_3d(outer_cir_dist)
    outer_cir_bool_mask = outer_cir_dist_3d <= radius
    masked_added_color = remove_extra_trans_color * outer_cir_bool_mask
    color_grid = trans_color + masked_added_color
    casted = color_grid.astype(np.uint8)
    return casted
    # endregion


def radial_gradient(radius: int, cent_color: tp.Tuple[int, int, int],
                    edge_color: tp.Tuple[int, int, int], transparent: tp.Tuple[int, int, int],
                    blend_radius: tp.Union[int, float],
                    blend_center: tp.Optional[tp.Tuple[tp.Union[int, float],
                                                       tp.Union[int, float]]] = None) -> pg.Surface:
    """Renders a circle with a radial gradient effect."""
    surf = pg.Surface((2 * radius,) * 2)
    surf.set_colorkey(transparent, pg.RLEACCEL)
    """
    pg.surfarray.blit_array(surf, pg.surfarray.map_array(surf,
                                                         radial_grad_array(radius, cent_color, edge_color, transparent,
                                                                           blend_radius, blend_center)))
    return surf
    """
    # region Debug
    mapped = pg.surfarray.map_array(surf, radial_grad_array(radius, cent_color, edge_color, transparent, blend_radius,
                                                            blend_center))
    # Use function from 'Util' in SciView to convert 'mapped' to human-readable RGB values again.
    pg.surfarray.blit_array(surf, mapped)
    return surf
    # endregion


def main() -> None:
    pg.display.init()
    pg.event.set_blocked(None)
    pg.event.set_allowed((pg.QUIT,))
    pg.display.set_caption("transparency test")
    resolution = (800, 600)
    radius = 100
    sin_wave = SinWave.sin_between_two_pts(200, 10, freq=4)  # noqa
    display = pg.display.set_mode(resolution)
    circle_surf = radial_gradient(radius, hex_to_rgb("020202"), hex_to_rgb("ffffff"), COLORS["TRANSPARENT"],
                                  radius / 2, blend_center=(40, 140))
    middle_man = pg.Surface(circle_surf.get_size())
    grad_surf = vert_gradient_column(resolution, hex_to_rgb("13698D"), hex_to_rgb("469850"))
    game_run = True
    clock = pg.time.Clock()
    while game_run:
        clock.tick(60)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                game_run = False
        circle_surf.set_alpha(int(sin_wave.get_value()))
        coords = (resolution[0] / 2 - radius, resolution[1] / 2 - radius)
        # Blit the same part of the background that is about to be painted over in 'middle_man'.
        middle_man.blit(grad_surf, (0, 0), area=pg.Rect(*coords, *middle_man.get_size()))
        # Now there is no noticeable difference :D
        middle_man.blit(circle_surf, (0, 0))
        display.blit(grad_surf, (0, 0))
        display.blit(middle_man, coords)
        pg.display.flip()
    pg.display.quit()


if __name__ == "__main__":
    # Run `python3 -m doctest -v alpha_test.py` to test.
    sys.path.extend((get_parent_dir(),))  # Fixes import path
    from Util import configure_dpi, hex_to_rgb, output_3d_array, SinWave, COLORS
    configure_dpi()
    main()
