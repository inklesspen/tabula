#include <math.h>
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

typedef enum _draw_color
{
    DRAW_COLOR_NONE = 0,
    DRAW_COLOR_BLACK = 1,
    DRAW_COLOR_WHITE = 2
} draw_color_t;

#define radians(degrees) ((degrees) * M_PI / 180.0)

void draw_roundrect(cairo_t *cr, const cairo_rectangle_t *rect, double radius, double line_width, draw_color_t fill_color, draw_color_t stroke_color)
{
    // This basically just draws the corners, and relies on cairo_arc to draw line segments connecting them.
    // Angles are given in radians; see https://www.cairographics.org/manual/cairo-Paths.html#cairo-arc for more info.
    // Not really worrying about type limits here tbh; doubles can hold very large numbers relative to the sizes we're throwing around.
    cairo_new_sub_path(cr);
    // upper left
    cairo_arc(cr, rect->x + radius, rect->y + radius, radius, radians(180), radians(270));
    // upper right
    cairo_arc(cr, rect->x + rect->width - radius, rect->y + radius, radius, radians(270), radians(0));
    // lower right
    cairo_arc(cr, rect->x + rect->width - radius, rect->y + rect->height - radius, radius, radians(0), radians(90));
    // lower left
    cairo_arc(cr, rect->x + radius, rect->y + rect->height - radius, radius, radians(90), radians(180));
    cairo_close_path(cr);
    cairo_set_line_width(cr, line_width);
    if (fill_color)
    {
        cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
        cairo_set_source_rgba(cr, 0, 0, 0, fill_color - 1);
        cairo_fill_preserve(cr);
    }
    if (G_LIKELY(stroke_color))
    {
        cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
        cairo_set_source_rgba(cr, 0, 0, 0, stroke_color - 1);
        cairo_stroke(cr);
    }
}

struct _MarkdownState
{
    gulong pos;
    PangoAttrList *attr_list;
    PangoAttribute *bold;
    PangoAttribute *italic;
    PangoAttribute *cursor_alpha;
    PangoAttribute *compose_underline;
    gchar *cached_start;
    gchar *pos_p;
    gchar *prev_pos_p;
};

typedef struct _MarkdownState MarkdownState;

const gunichar ASTERISK = 42;
const gunichar UNDERSCORE = 95;

void fully_free_g_string(GString *string)
{
    g_string_free(string, TRUE);
}

static gboolean simplify_list_filter(PangoAttribute *attribute, G_GNUC_UNUSED gpointer user_data)
{
    if (attribute->start_index == attribute->end_index)
    {
        return TRUE;
    }
    else
    {
        return FALSE;
    }
}

void simplify_attr_list(PangoAttrList *list)
{
    PangoAttrList *out;
    out = pango_attr_list_filter(list, simplify_list_filter, NULL);
    pango_attr_list_unref(out);
}

static void markdown_state_housekeeping(MarkdownState *state, GString *string)
{
    if (G_UNLIKELY(state->cached_start != string->str))
    {
        // the underlying str has been reallocated; we cannot trust the previous pointer.
        // in theory we can pass negative offsets to gain some efficiency but i don't understand the trick used, so…
        // https://gitlab.gnome.org/GNOME/glib/-/commit/1ee0917984152f9fe09b33a3660ba96cec0b55b1
        state->pos_p = g_utf8_offset_to_pointer(string->str, state->pos);
        state->prev_pos_p = g_utf8_find_prev_char(string->str, state->pos_p);
        state->cached_start = string->str;
    }
}
MarkdownState *markdown_state_new(GString *string)
{
    MarkdownState *state = g_new(MarkdownState, 1);
    state->pos = 0;
    state->attr_list = pango_attr_list_new();
    state->bold = NULL;
    state->italic = NULL;
    state->cursor_alpha = pango_attr_foreground_alpha_new(0x7FFF);
    state->cursor_alpha->start_index = 0;
    state->cursor_alpha->end_index = 0;
    state->compose_underline = pango_attr_underline_new(PANGO_UNDERLINE_SINGLE);
    state->compose_underline->start_index = 0;
    state->compose_underline->end_index = 0;
    state->cached_start = string->str;
    state->pos_p = string->str;
    state->prev_pos_p = NULL;
    pango_attr_list_insert(state->attr_list, state->compose_underline);
    pango_attr_list_insert(state->attr_list, state->cursor_alpha);
    return state;
}

void markdown_state_free(MarkdownState *state)
{
    pango_attr_list_unref(state->attr_list);
    g_free(state);
}

void markdown_attrs(MarkdownState *state, GString *string)
{
    // undefined behavior if state->pos is ever greater than string->len
    g_return_if_fail(state->pos <= string->len);
    markdown_state_housekeeping(state, string);
    if (string->len == 0)
    {
        return;
    }
    // Remember! string->len is BYTES, not Unicode characters.
    while (g_utf8_get_char(state->pos_p) != 0)
    {
        gunichar prev;
        gunichar current = g_utf8_get_char(state->pos_p);
        if (current == UNDERSCORE)
        {
            if (state->italic == NULL)
            {
                state->italic = pango_attr_style_new(PANGO_STYLE_ITALIC);
                state->italic->start_index = (state->pos_p - string->str);
                pango_attr_list_insert(state->attr_list, state->italic);
            }
            else
            {
                // exclusive range end
                state->italic->end_index = (state->pos_p - string->str) + 1;
                state->italic = NULL;
            }
        }
        if (current == ASTERISK)
        {
            prev = 0;
            if (state->prev_pos_p != NULL)
            {
                prev = g_utf8_get_char(state->prev_pos_p);
            }
            if (prev == current)
            {
                if (state->bold == NULL)
                {
                    state->bold = pango_attr_weight_new(PANGO_WEIGHT_SEMIBOLD);
                    // start it from the previous position!
                    state->bold->start_index = (state->prev_pos_p - string->str);
                    pango_attr_list_insert(state->attr_list, state->bold);
                }
                else
                {
                    // exclusive range end
                    state->bold->end_index = (state->pos_p - string->str) + 1;
                    state->bold = NULL;
                }
            }
        }

        state->pos++;
        state->prev_pos_p = state->pos_p;
        state->pos_p = g_utf8_next_char(state->pos_p);
    }
}

static gboolean backspace_filter(PangoAttribute *attribute, gpointer user_data)
{
    MarkdownState *state = (MarkdownState *)user_data;
    guint last = (state->pos_p - state->cached_start);

    if (!(attribute->klass->type == PANGO_ATTR_STYLE || attribute->klass->type == PANGO_ATTR_WEIGHT))
    {
        // never remove the cursor or compose attributes
        return FALSE;
    }
    if (attribute->klass->type == PANGO_ATTR_WEIGHT)
    {
        // bold ones start one character before. luckily the asterisk is always a single byte.
        last--;
    }
    if (attribute->end_index >= last)
    {
        attribute->end_index = PANGO_ATTR_INDEX_TO_TEXT_END;
        if (attribute->klass->type == PANGO_ATTR_WEIGHT)
        {
            state->bold = attribute;
        }
        else if (attribute->klass->type == PANGO_ATTR_STYLE)
        {
            state->italic = attribute;
        }
    }
    if (attribute->start_index >= last)
    {
        // we are removing this, but first we might have to clear state->bold or state->italic
        if (attribute == state->bold)
        {
            state->bold = NULL;
        }
        if (attribute == state->italic)
        {
            state->italic = NULL;
        }
        return TRUE;
    }
    return FALSE;
}

void markdown_attrs_backspace(MarkdownState *state, GString *string)
{
    markdown_state_housekeeping(state, string);
    if (G_UNLIKELY(state->prev_pos_p == NULL))
    {
        // nothing to do
        return;
    }
    // fix up the positioning
    state->pos = g_utf8_pointer_to_offset(string->str, state->prev_pos_p);
    state->pos_p = g_utf8_offset_to_pointer(string->str, state->pos);
    state->prev_pos_p = g_utf8_find_prev_char(string->str, state->pos_p);
    // truncate the string
    g_string_truncate(string, (state->pos_p - string->str));
    // fix the attrlist
    PangoAttrList *out;
    out = pango_attr_list_filter(state->attr_list, backspace_filter, (gpointer)state);
    pango_attr_list_unref(out);
}

void setup_cursor(MarkdownState *state, GString *string)
{
    // cursor is a 50% alpha underscore
    state->cursor_alpha->start_index = string->len;
    state->cursor_alpha->end_index = string->len + 1;
    g_string_append_unichar(string, UNDERSCORE);
}
void cleanup_cursor(MarkdownState *state, GString *string)
{
    // WARNING! assumes no changes have been made since setting up cursor
    g_string_truncate(string, string->len - 1);
    state->cursor_alpha->start_index = 0;
    state->cursor_alpha->end_index = 0;
}

void setup_compose(MarkdownState *state, guint start, guint end)
{
    state->compose_underline->start_index = start;
    state->compose_underline->end_index = end;
}
void cleanup_compose(MarkdownState *state)
{
    state->compose_underline->start_index = 0;
    state->compose_underline->end_index = 0;
}

struct _CursorPara
{
    gchar *para;
    PangoAttrList *attr_list;
};

typedef struct _CursorPara CursorPara;

CursorPara *cursor_para_new(void)
{
    CursorPara *para = g_new(CursorPara, 1);
    GString *string = g_string_sized_new(2);
    g_string_append_unichar(string, UNDERSCORE);
    para->para = g_string_free_and_steal(string);
    PangoAttribute *cursor_alpha = pango_attr_foreground_alpha_new(0x7FFF);
    cursor_alpha->start_index = 0;
    cursor_alpha->end_index = PANGO_ATTR_INDEX_TO_TEXT_END;
    para->attr_list = pango_attr_list_new();
    pango_attr_list_insert(para->attr_list, cursor_alpha);
    return para;
}
void cursor_para_free(CursorPara *para)
{
    pango_attr_list_unref(para->attr_list);
    g_free(para->para);
    g_free(para);
}
