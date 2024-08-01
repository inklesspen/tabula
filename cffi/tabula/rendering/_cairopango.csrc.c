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

struct _MarkdownState
{
    PangoAttrList *attr_list;
    PangoAttribute *bold;
    PangoAttribute *italic;
    glong pos;
    gchar *cached_start;
    gchar *pos_p;
    gchar *prev_pos_p;
};

typedef struct _MarkdownState MarkdownState;

const gunichar ASTERISK = 42;
const gunichar UNDERSCORE = 95;

gchar *test_quick_next(gchar *p)
{
    return g_utf8_next_char(p);
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
    // undefined behavior if state->pos is ever greater than string->len
    if (state->pos_p == NULL)
    {
        // initialise
        state->attr_list = pango_attr_list_new();
        state->bold = NULL;
        state->italic = NULL;
        state->cached_start = string->str;
        state->pos_p = string->str;
        state->prev_pos_p = NULL;
    }
    else if (state->cached_start != string->str)
    {
        // the underlying str has been reallocated; we cannot trust the previous pointer.
        // in theory we can pass negative offsets to gain some efficiency but i don't understand the trick used, so…
        // https://gitlab.gnome.org/GNOME/glib/-/commit/1ee0917984152f9fe09b33a3660ba96cec0b55b1
        state->pos_p = g_utf8_offset_to_pointer(string->str, state->pos);
        state->prev_pos_p = g_utf8_find_prev_char(string->str, state->pos_p);
        state->cached_start = string->str;
    }
}

void markdown_attrs(MarkdownState *state, GString *string)
{
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
    guint *last_p = (guint *)user_data;
    guint last = *last_p;
    if (attribute->klass->type == PANGO_ATTR_WEIGHT)
    {
        // bold ones start one character before. luckily the asterisk is always a single byte.
        last--;
    }
    if (attribute->end_index >= last)
    {
        attribute->end_index = PANGO_ATTR_INDEX_TO_TEXT_END;
    }
    if (attribute->start_index >= last)
    {
        return TRUE;
    }
    return FALSE;
}

void markdown_attrs_backspace(MarkdownState *state, GString *string)
{
    markdown_state_housekeeping(state, string);
    if (state->prev_pos_p == NULL)
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
    guint last = (state->pos_p - string->str);
    PangoAttrList *out;
    out = pango_attr_list_filter(state->attr_list, backspace_filter, (gpointer)&last);
    pango_attr_list_unref(out);
}
