# SPDX-FileCopyrightText: 2021 Rose Davidson <rose@metaclassical.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from cffi import FFI

ffibuilder = FFI()

ffibuilder.cdef(
    """
/* glib+gobject */
typedef ... GType;
typedef unsigned int guint8;
typedef unsigned int guint16;
typedef unsigned int guint32;
typedef unsigned int guint;
typedef int gint;
typedef int gint32;
typedef gint gboolean;
typedef char gchar;
typedef unsigned char guchar;
typedef ... gunichar;
typedef void *gpointer;
typedef ... gconstpointer;
typedef ... GObject;
typedef ... GObjectClass;
typedef ... GString;
typedef ... GDestroyNotify;
typedef ... GList;
typedef ... GSList;
typedef ... GError;
typedef ... GMarkupParseContext;
typedef ... GTypeModule;
typedef signed long gssize;

void g_object_unref(gpointer object);
void g_free(gpointer mem);

gchar *
g_markup_escape_text(const gchar *text,
                     gssize length);

/* cairo */
typedef struct _cairo_font_options cairo_font_options_t;
typedef struct _cairo_surface cairo_surface_t;
typedef struct _cairo cairo_t;

typedef enum _cairo_status
{
    CAIRO_STATUS_SUCCESS = 0,

    CAIRO_STATUS_NO_MEMORY,
    CAIRO_STATUS_INVALID_RESTORE,
    CAIRO_STATUS_INVALID_POP_GROUP,
    CAIRO_STATUS_NO_CURRENT_POINT,
    CAIRO_STATUS_INVALID_MATRIX,
    CAIRO_STATUS_INVALID_STATUS,
    CAIRO_STATUS_NULL_POINTER,
    CAIRO_STATUS_INVALID_STRING,
    CAIRO_STATUS_INVALID_PATH_DATA,
    CAIRO_STATUS_READ_ERROR,
    CAIRO_STATUS_WRITE_ERROR,
    CAIRO_STATUS_SURFACE_FINISHED,
    CAIRO_STATUS_SURFACE_TYPE_MISMATCH,
    CAIRO_STATUS_PATTERN_TYPE_MISMATCH,
    CAIRO_STATUS_INVALID_CONTENT,
    CAIRO_STATUS_INVALID_FORMAT,
    CAIRO_STATUS_INVALID_VISUAL,
    CAIRO_STATUS_FILE_NOT_FOUND,
    CAIRO_STATUS_INVALID_DASH,
    CAIRO_STATUS_INVALID_DSC_COMMENT,
    CAIRO_STATUS_INVALID_INDEX,
    CAIRO_STATUS_CLIP_NOT_REPRESENTABLE,
    CAIRO_STATUS_TEMP_FILE_ERROR,
    CAIRO_STATUS_INVALID_STRIDE,
    CAIRO_STATUS_FONT_TYPE_MISMATCH,
    CAIRO_STATUS_USER_FONT_IMMUTABLE,
    CAIRO_STATUS_USER_FONT_ERROR,
    CAIRO_STATUS_NEGATIVE_COUNT,
    CAIRO_STATUS_INVALID_CLUSTERS,
    CAIRO_STATUS_INVALID_SLANT,
    CAIRO_STATUS_INVALID_WEIGHT,
    CAIRO_STATUS_INVALID_SIZE,
    CAIRO_STATUS_USER_FONT_NOT_IMPLEMENTED,
    CAIRO_STATUS_DEVICE_TYPE_MISMATCH,
    CAIRO_STATUS_DEVICE_ERROR,
    CAIRO_STATUS_INVALID_MESH_CONSTRUCTION,
    CAIRO_STATUS_DEVICE_FINISHED,
    CAIRO_STATUS_JBIG2_GLOBAL_MISSING,
    CAIRO_STATUS_PNG_ERROR,
    CAIRO_STATUS_FREETYPE_ERROR,
    CAIRO_STATUS_WIN32_GDI_ERROR,
    CAIRO_STATUS_TAG_ERROR,

    CAIRO_STATUS_LAST_STATUS
} cairo_status_t;

typedef struct _cairo_matrix
{
    double xx;
    double yx;
    double xy;
    double yy;
    double x0;
    double y0;
} cairo_matrix_t;

typedef enum _cairo_format
{
    CAIRO_FORMAT_INVALID = -1,
    CAIRO_FORMAT_ARGB32 = 0,
    CAIRO_FORMAT_RGB24 = 1,
    CAIRO_FORMAT_A8 = 2,
    CAIRO_FORMAT_A1 = 3,
    CAIRO_FORMAT_RGB16_565 = 4,
    CAIRO_FORMAT_RGB30 = 5
} cairo_format_t;

typedef enum _cairo_operator
{
    CAIRO_OPERATOR_CLEAR,

    CAIRO_OPERATOR_SOURCE,
    CAIRO_OPERATOR_OVER,
    CAIRO_OPERATOR_IN,
    CAIRO_OPERATOR_OUT,
    CAIRO_OPERATOR_ATOP,

    CAIRO_OPERATOR_DEST,
    CAIRO_OPERATOR_DEST_OVER,
    CAIRO_OPERATOR_DEST_IN,
    CAIRO_OPERATOR_DEST_OUT,
    CAIRO_OPERATOR_DEST_ATOP,

    CAIRO_OPERATOR_XOR,
    CAIRO_OPERATOR_ADD,
    CAIRO_OPERATOR_SATURATE,

    CAIRO_OPERATOR_MULTIPLY,
    CAIRO_OPERATOR_SCREEN,
    CAIRO_OPERATOR_OVERLAY,
    CAIRO_OPERATOR_DARKEN,
    CAIRO_OPERATOR_LIGHTEN,
    CAIRO_OPERATOR_COLOR_DODGE,
    CAIRO_OPERATOR_COLOR_BURN,
    CAIRO_OPERATOR_HARD_LIGHT,
    CAIRO_OPERATOR_SOFT_LIGHT,
    CAIRO_OPERATOR_DIFFERENCE,
    CAIRO_OPERATOR_EXCLUSION,
    CAIRO_OPERATOR_HSL_HUE,
    CAIRO_OPERATOR_HSL_SATURATION,
    CAIRO_OPERATOR_HSL_COLOR,
    CAIRO_OPERATOR_HSL_LUMINOSITY
} cairo_operator_t;

typedef enum _cairo_antialias
{
    CAIRO_ANTIALIAS_DEFAULT,

    /* method */
    CAIRO_ANTIALIAS_NONE,
    CAIRO_ANTIALIAS_GRAY,
    CAIRO_ANTIALIAS_SUBPIXEL,

    /* hints */
    CAIRO_ANTIALIAS_FAST,
    CAIRO_ANTIALIAS_GOOD,
    CAIRO_ANTIALIAS_BEST
} cairo_antialias_t;

typedef enum _cairo_subpixel_order
{
    CAIRO_SUBPIXEL_ORDER_DEFAULT,
    CAIRO_SUBPIXEL_ORDER_RGB,
    CAIRO_SUBPIXEL_ORDER_BGR,
    CAIRO_SUBPIXEL_ORDER_VRGB,
    CAIRO_SUBPIXEL_ORDER_VBGR
} cairo_subpixel_order_t;

typedef enum _cairo_hint_style
{
    CAIRO_HINT_STYLE_DEFAULT,
    CAIRO_HINT_STYLE_NONE,
    CAIRO_HINT_STYLE_SLIGHT,
    CAIRO_HINT_STYLE_MEDIUM,
    CAIRO_HINT_STYLE_FULL
} cairo_hint_style_t;

typedef enum _cairo_hint_metrics
{
    CAIRO_HINT_METRICS_DEFAULT,
    CAIRO_HINT_METRICS_OFF,
    CAIRO_HINT_METRICS_ON
} cairo_hint_metrics_t;

typedef cairo_status_t (*cairo_write_func_t)(void *closure,
                                             const unsigned char *data,
                                             unsigned int length);

int cairo_format_stride_for_width(cairo_format_t format,
                                  int width);

cairo_surface_t *
cairo_image_surface_create(cairo_format_t format,
                           int width,
                           int height);

unsigned char *
cairo_image_surface_get_data(cairo_surface_t *surface);

int cairo_image_surface_get_width(cairo_surface_t *surface);

int cairo_image_surface_get_height(cairo_surface_t *surface);

int cairo_image_surface_get_stride(cairo_surface_t *surface);

cairo_t *
cairo_create(cairo_surface_t *target);

void cairo_destroy(cairo_t *cr);

void cairo_set_operator(cairo_t *cr, cairo_operator_t op);

void cairo_set_source_rgba(cairo_t *cr,
                           double red, double green, double blue,
                           double alpha);

void cairo_paint(cairo_t *cr);

void cairo_surface_destroy(cairo_surface_t *surface);

cairo_font_options_t *
cairo_font_options_create(void);

void cairo_font_options_destroy(cairo_font_options_t *options);

void cairo_font_options_set_antialias(cairo_font_options_t *options,
                                      cairo_antialias_t antialias);

void cairo_font_options_set_subpixel_order(cairo_font_options_t *options,
                                           cairo_subpixel_order_t subpixel_order);

void cairo_font_options_set_hint_style(cairo_font_options_t *options,
                                       cairo_hint_style_t hint_style);

void cairo_font_options_set_hint_metrics(cairo_font_options_t *options,
                                         cairo_hint_metrics_t hint_metrics);

void cairo_matrix_init(cairo_matrix_t *matrix,
                       double xx, double yx,
                       double xy, double yy,
                       double x0, double y0);

void cairo_matrix_init_identity(cairo_matrix_t *matrix);

void cairo_set_matrix(cairo_t *cr,
                      const cairo_matrix_t *matrix);

void cairo_identity_matrix(cairo_t *cr);

void cairo_save(cairo_t *cr);

void cairo_restore(cairo_t *cr);

void cairo_translate(cairo_t *cr, double tx, double ty);

void cairo_move_to(cairo_t *cr, double x, double y);

void cairo_rectangle(cairo_t *cr,
                     double x,
                     double y,
                     double width,
                     double height);

void cairo_path_extents(cairo_t *cr,
                        double *x1,
                        double *y1,
                        double *x2,
                        double *y2);

void cairo_set_line_width(cairo_t *cr, double width);

void cairo_stroke(cairo_t *cr);

void cairo_surface_flush(cairo_surface_t *surface);

void cairo_surface_mark_dirty(cairo_surface_t *surface);

cairo_surface_t *
cairo_get_target(cairo_t *cr);

/* pango */
typedef struct _PangoMatrix PangoMatrix;
struct _PangoMatrix
{
    double xx;
    double xy;
    double yx;
    double yy;
    double x0;
    double y0;
};

typedef ... PangoContext;
typedef ... PangoLanguage;

typedef enum
{
    PANGO_DIRECTION_LTR,
    PANGO_DIRECTION_RTL,
    PANGO_DIRECTION_TTB_LTR,
    PANGO_DIRECTION_TTB_RTL,
    PANGO_DIRECTION_WEAK_LTR,
    PANGO_DIRECTION_WEAK_RTL,
    PANGO_DIRECTION_NEUTRAL
} PangoDirection;

typedef enum
{
    PANGO_GRAVITY_SOUTH,
    PANGO_GRAVITY_EAST,
    PANGO_GRAVITY_NORTH,
    PANGO_GRAVITY_WEST,
    PANGO_GRAVITY_AUTO
} PangoGravity;

typedef enum
{
    PANGO_GRAVITY_HINT_NATURAL,
    PANGO_GRAVITY_HINT_STRONG,
    PANGO_GRAVITY_HINT_LINE
} PangoGravityHint;

typedef ... PangoFontMap;

struct _PangoRectangle
{
    int x;
    int y;
    int width;
    int height;
};

typedef struct _PangoRectangle PangoRectangle;

typedef struct _PangoFontDescription PangoFontDescription;
typedef ... PangoFont;
typedef ... PangoFontMetrics;

typedef struct _PangoLayout PangoLayout;

typedef enum
{
    PANGO_ALIGN_LEFT,
    PANGO_ALIGN_CENTER,
    PANGO_ALIGN_RIGHT
} PangoAlignment;

typedef enum
{
    PANGO_WRAP_WORD,
    PANGO_WRAP_CHAR,
    PANGO_WRAP_WORD_CHAR
} PangoWrapMode;

typedef enum
{
    PANGO_ELLIPSIZE_NONE,
    PANGO_ELLIPSIZE_START,
    PANGO_ELLIPSIZE_MIDDLE,
    PANGO_ELLIPSIZE_END
} PangoEllipsizeMode;

const PangoMatrix *pango_context_get_matrix(PangoContext *context);
void pango_context_set_language(PangoContext *context,
                                PangoLanguage *language);
void pango_context_set_base_dir(PangoContext *context,
                                PangoDirection direction);
void pango_context_set_base_gravity(PangoContext *context,
                                    PangoGravity gravity);
void pango_context_set_gravity_hint(PangoContext *context,
                                    PangoGravityHint hint);
void pango_context_set_matrix(PangoContext *context,
                              const PangoMatrix *matrix);

PangoContext *pango_font_map_create_context(PangoFontMap *fontmap);

PangoFont *
pango_font_map_load_font(
    PangoFontMap *fontmap,
    PangoContext *context,
    const PangoFontDescription *desc);

PangoFontMetrics *
pango_font_get_metrics(
    PangoFont *font,
    PangoLanguage *language);

void pango_font_metrics_unref(
    PangoFontMetrics *metrics);

int pango_font_metrics_get_height(
    PangoFontMetrics *metrics);

int pango_font_metrics_get_ascent(
    PangoFontMetrics *metrics);

int pango_font_metrics_get_descent(
    PangoFontMetrics *metrics);

PangoMatrix *pango_matrix_copy(const PangoMatrix *matrix);
void pango_matrix_free(PangoMatrix *matrix);
void pango_matrix_transform_pixel_rectangle(const PangoMatrix *matrix,
                                            PangoRectangle *rect);

PangoLanguage *pango_language_from_string(const char *language);

PangoFontDescription *pango_font_description_from_string(const char *str);
void pango_font_description_set_size(PangoFontDescription *desc,
                                     gint size);
void pango_font_description_free(PangoFontDescription *desc);

PangoFontDescription *pango_font_describe(PangoFont *font);

char *pango_font_description_to_string(PangoFontDescription *desc);

PangoLayout *pango_layout_new(PangoContext *context);
void pango_layout_set_markup(PangoLayout *layout,
                             const char *markup,
                             int length);
void pango_layout_set_text(PangoLayout *layout,
                           const char *text,
                           int length);
void pango_layout_set_auto_dir(PangoLayout *layout,
                               gboolean auto_dir);
void pango_layout_set_ellipsize(PangoLayout *layout,
                                PangoEllipsizeMode ellipsize);
void pango_layout_set_justify(PangoLayout *layout,
                              gboolean justify);
void pango_layout_set_spacing(PangoLayout *layout,
                              int spacing);
void pango_layout_set_single_paragraph_mode(PangoLayout *layout,
                                            gboolean setting);
void pango_layout_set_wrap(PangoLayout *layout,
                           PangoWrapMode wrap);
void pango_layout_set_width(PangoLayout *layout,
                            int width);
void pango_layout_set_height(PangoLayout *layout,
                             int height);
void pango_layout_set_alignment(PangoLayout *layout,
                                PangoAlignment alignment);
void pango_layout_set_font_description(PangoLayout *layout,
                                       const PangoFontDescription *desc);
PangoContext *pango_layout_get_context(PangoLayout *layout);
void pango_layout_context_changed(PangoLayout *layout);
void pango_layout_get_pixel_extents(PangoLayout *layout,
                                    PangoRectangle *ink_rect,
                                    PangoRectangle *logical_rect);
int pango_layout_get_width(PangoLayout *layout);
int pango_layout_get_height(PangoLayout *layout);

/* pangocairo */
typedef struct _PangoCairoFontMap PangoCairoFontMap;

PangoFontMap *pango_cairo_font_map_new(void);

PangoFontMap *pango_cairo_font_map_get_default(void);

void pango_cairo_font_map_set_resolution(PangoCairoFontMap *fontmap,
                                         double dpi);

void pango_cairo_context_set_font_options(PangoContext *context,
                                          const cairo_font_options_t *options);
const cairo_font_options_t *pango_cairo_context_get_font_options(PangoContext *context);
void pango_cairo_update_context(cairo_t *cr,
                                PangoContext *context);
void pango_cairo_show_layout(cairo_t *cr,
                             PangoLayout *layout);

/* quirky bits */

/**
 * PANGO_SCALE:
 *
 * The scale between dimensions used for Pango distances and device units.
 *
 * The definition of device units is dependent on the output device; it will
 * typically be pixels for a screen, and points for a printer. %PANGO_SCALE is
 * currently 1024, but this may be changed in the future.
 *
 * When setting font sizes, device units are always considered to be
 * points (as in "12 point font"), rather than pixels.
 */
/**
 * PANGO_PIXELS:
 * @d: a dimension in Pango units.
 *
 * Converts a dimension to device units by rounding.
 *
 * Return value: rounded dimension in device units.
 */
/**
 * PANGO_PIXELS_FLOOR:
 * @d: a dimension in Pango units.
 *
 * Converts a dimension to device units by flooring.
 *
 * Return value: floored dimension in device units.
 * Since: 1.14
 */
/**
 * PANGO_PIXELS_CEIL:
 * @d: a dimension in Pango units.
 *
 * Converts a dimension to device units by ceiling.
 *
 * Return value: ceiled dimension in device units.
 * Since: 1.14
 */
#define PANGO_SCALE 1024
/*
#define PANGO_PIXELS(d) (((int)(d) + 512) >> 10)
#define PANGO_PIXELS_FLOOR(d) (((int)(d)) >> 10)
#define PANGO_PIXELS_CEIL(d) (((int)(d) + 1023) >> 10)
*/
/* The above expressions are just slightly wrong for floating point d;
 * For example we'd expect PANGO_PIXELS(-512.5) => -1 but instead we get 0.
 * That's unlikely to matter for practical use and the expression is much
 * more compact and faster than alternatives that work exactly for both
 * integers and floating point.
 *
 * PANGO_PIXELS also behaves differently for +512 and -512.
 */
int pango_pixels(int d);

void invert_a8_surface(cairo_surface_t *surface);
"""
)

ffibuilder.set_source_pkgconfig(
    "tabula.rendering._cffi",
    ["glib-2.0", "gobject-2.0", "cairo", "pango", "pangocairo"],
    """
#include <glib.h>
#include <glib-object.h>
#include <cairo.h>
#include <pango/pango.h>
#include <pango/pangocairo.h>

static int pango_pixels(int d) {
    return PANGO_PIXELS(d);
}

static void invert_a8_surface(cairo_surface_t* surface) {
  unsigned char* surface_data = cairo_image_surface_get_data(surface);
	unsigned int width = cairo_image_surface_get_width(surface);
	unsigned int height = cairo_image_surface_get_height(surface);
	unsigned int i;

	if (cairo_image_surface_get_format(surface) != CAIRO_FORMAT_A8) return;

	for (i = 0; i < width * height; i++) {
    surface_data[i] = 255 - surface_data[i];
  }
}
""",
)
