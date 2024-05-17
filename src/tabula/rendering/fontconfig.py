from ._pangocairo import lib, ffi  # type: ignore


def match_pattern(some: str, private=None):
    # derived loosely from https://www.camconn.cc/post/how-to-fontconfig-lib-c/
    conf = ffi.NULL
    charset = ffi.NULL
    if private:
        conf = ffi.gc(lib.FcConfigCreate(), lib.FcConfigDestroy)
        for privatefile in private:
            lib.FcConfigAppFontAddFile(conf, privatefile.encode())

    pat = lib.FcNameParse(some.encode())
    if pat == ffi.NULL:
        raise Exception("something happened")
    pat = ffi.gc(pat, lib.FcPatternDestroy)

    lib.FcConfigSubstitute(conf, pat, lib.FcMatchPattern)
    lib.FcDefaultSubstitute(pat)

    fs = ffi.gc(lib.FcFontSetCreate(), lib.FcFontSetDestroy)
    os = lib.FcObjectSetBuild(lib.FC_FAMILY, lib.FC_STYLE, lib.FC_FILE, ffi.NULL)

    result = ffi.new("FcResult *")
    font_patterns = lib.FcFontSort(conf, pat, True, charset, result)
    if font_patterns == ffi.NULL:
        # result might contain a hint here…
        raise Exception("something else happened")
    font_patterns = ffi.gc(font_patterns, lib.FcFontSetDestroy)
    if font_patterns.nfont == 0:
        raise Exception("no fonts found")
    font_pattern = lib.FcFontRenderPrepare(conf, pat, font_patterns.fonts[0])
    if font_pattern == ffi.NULL:
        raise Exception("patternfault")
    lib.FcFontSetAdd(fs, font_pattern)

    del font_patterns
    del pat

    fsfonts = ffi.unpack(fs.fonts, fs.nfont)
    fontfiles = []
    for fsfont in fsfonts:
        fontpat = ffi.gc(lib.FcPatternFilter(fsfont, os), lib.FcPatternDestroy)
        buf = ffi.new("FcChar8 **")
        lib.FcPatternGetString(fontpat, lib.FC_FILE, 0, buf)
        fontfiles.append(ffi.string(buf[0]).decode())

    return fontfiles
