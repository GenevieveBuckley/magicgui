"""Example showing how to accomplish a napari parameter sweep with magicgui.

It demonstrates:
1. overriding the default widget type with a custom class
2. the `auto_call` option, which calls the function whenever a parameter changes

"""
import napari
import skimage.data
import skimage.filters
from napari.layers import Image

from magicgui import magicgui
from magicgui.widgets import Slider

with napari.gui_qt():
    # create a viewer and add some images
    viewer = napari.Viewer()
    viewer.add_image(skimage.data.astronaut().mean(-1), name="astronaut")
    viewer.add_image(skimage.data.grass().astype("float"), name="grass")

    # turn the gaussian blur function into a magicgui
    # - `auto_call` tells magicgui to call the function whenever a parameter changes
    # - we use `widget_type` to override the default "float" widget on sigma
    # - we provide some Qt-specific parameters
    # - we contstrain the possible choices for `mode`
    @magicgui(
        auto_call=True,
        sigma={"widget_type": Slider, "maximum": 6},
        mode={"choices": ["reflect", "constant", "nearest", "mirror", "wrap"]},
    )
    def gaussian_blur(layer: Image, sigma: float = 1.0, mode="nearest") -> Image:
        """Apply a gaussian blur to ``layer``."""
        if layer:
            return skimage.filters.gaussian(layer.data, sigma=sigma, mode=mode)

    # Add it to the napari viewer
    viewer.window.add_dock_widget(gaussian_blur)
    # update the layer dropdown menu when the layer list changes
    viewer.layers.events.changed.connect(gaussian_blur.reset_choices)
