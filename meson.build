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

meson_cffi_buildtool = find_program('meson_cffi_buildtool.py')

meson_cffi_gen = generator(
    meson_cffi_buildtool,
    output: '@BASENAME@',
    arguments: ['@INPUT@', '@OUTPUT@'],
)

fontconfig = dependency('fontconfig')
glib = dependency('glib-2.0')
gobject = dependency('gobject-2.0')
cairo = dependency('cairo')
pango = dependency('pango')
pangocairo = dependency('pangocairo')
py.extension_module(
    '_cairopango',
    meson_cffi_gen.process('cffi/tabula/rendering/_cairopango.c.py'),
    subdir: 'tabula/rendering',
    install: true,
    dependencies: [glib, gobject, cairo, pango, pangocairo, fontconfig, py.dependency()],
)

fbink = dependency('fbink', required: host_machine.system() == 'linux')
if fbink.found()
    py.extension_module(
        '_fbink',
        meson_cffi_gen.process('cffi/tabula/device/_fbink.c.py'),
        subdir: 'tabula/device',
        install: true,
        dependencies: [fbink, py.dependency()],
    )
endif