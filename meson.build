project(
    'tabula',
    'c',
    version: '0.1',
    default_options: ['warning_level=3'],
)
# TODO: add license and license_files; https://mesonbuild.com/Reference-manual_functions.html#project_license

py = import('python').find_installation(pure: false)

# TODO: exclude some directories based on platform
install_subdir('src/tabula', install_dir: py.get_install_dir())

gen_cffi_src = find_program('gen-cffi-src')

cairopango_c = custom_target(
    command: [
        gen_cffi_src,
        'read-sources',
        'tabula.rendering._cairopango',
        '@INPUT0@',
        '@INPUT1@',
        '@OUTPUT@',
    ],
    output: '_cairopango.c',
    input: [
        'cffi/tabula/rendering/_cairopango.cdef.txt',
        'cffi/tabula/rendering/_cairopango.csrc.c',
    ],
)

fontconfig = dependency('fontconfig')
glib = dependency('glib-2.0')
gobject = dependency('gobject-2.0')
cairo = dependency('cairo')
pango = dependency('pango')
pangocairo = dependency('pangocairo')
py.extension_module(
    '_cairopango',
    cairopango_c,
    subdir: 'tabula/rendering',
    install: true,
    dependencies: [glib, gobject, cairo, pango, pangocairo, fontconfig, py.dependency()],
)

fbink = dependency('fbink', required: host_machine.system() == 'linux')
if fbink.found()
    fbink_c = custom_target(
        command: [
            gen_cffi_src,
            'read-sources',
            'tabula.device._fbink',
            '@INPUT0@',
            '@INPUT1@',
            '@OUTPUT@',
        ],
        output: '_fbink.c',
        input: [
            'cffi/tabula/device/_fbink.cdef.txt',
            'cffi/tabula/device/_fbink.csrc.c',
        ],
    )
    py.extension_module(
        '_fbink',
        fbink_c,
        subdir: 'tabula/device',
        install: true,
        dependencies: [fbink, py.dependency()],
    )
endif