#include <glib.h>
#include <glib-object.h>
#include <cairo.h>
#include <pango/pango.h>
#include <pango/pangocairo.h>
#include <pango/pangofc-font.h>
#include <fontconfig/fontconfig.h>

static int pango_pixels(int d)
{
    return PANGO_PIXELS(d);
}

static void invert_a8_surface(cairo_surface_t *surface)
{
    unsigned char *surface_data = cairo_image_surface_get_data(surface);
    unsigned int width = cairo_image_surface_get_width(surface);
    unsigned int height = cairo_image_surface_get_height(surface);
    unsigned int i;

    if (cairo_image_surface_get_format(surface) != CAIRO_FORMAT_A8)
        return;

    for (i = 0; i < width * height; i++)
    {
        surface_data[i] = 255 - surface_data[i];
    }
}
