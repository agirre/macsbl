# configuration file reference is available at:
# http://developer.gnome.org/jhbuild/unstable/config-reference.html.en

# default root directory for directories below
_topdir = os.getcwd()

# cross-compilation is started by: TARGET=i686-pc-mingw32 ./cj ...
_target = os.getenv('TARGET')

# directory where source code is downloaded from repositories...
checkoutroot = os.path.join(_topdir, 'checkout')
# ...and from ftp
tarballdir = checkoutroot

# build directory, set to None to use in-source build
buildroot = os.path.join(_topdir, 'builddir')

# installation prefix
prefix = os.path.join(_topdir, 'install')

# when set to True, building of some libraries is skipped if up-to-date
# version is installed system-wise (which is verified using pkg-config)
partial_build = False

# for cross-compilation, add compiler prefix to directory names
if _target:
    buildroot += "-%s" % _target
    prefix += "-%s" % _target

_for_windows = (sys.platform == 'win32' or (_target and 'mingw' in _target))

# directory where Tcl/Tk is installed (set to '' if Tcl is in the system path)
_tcldir = _topdir + '/TclTk84'
# Tcl library name (no need to change it, for Windows the dot is removed)
_tcllib = 'tcl8.4'

# compilers (can be set differently from command line or from cj.rc)
# If compilers are not set, they are guessed by build scripts of individual
# modules. It usually works fine, but sometimes, when the user has multiple
# compilers installed cmake and autotools scripts pick different ones,
# what may lead to puzzling linking errors. So we rather set them explicitely
# (unless cross-compiling)
if not _target:
    os.environ.setdefault('CC', "gcc")
    os.environ.setdefault('CXX', "g++")
    os.environ.setdefault('FC', "gfortran")

# Note: cctbx/phaser ignores compiler settings above. It supports only
# a few hardcoded (in libtbx/SConscript) choices of compilers, that may
# be selected by adding "--compiler=name" in _cctbx_configure_args

# set STATIC=1 to build and link with static libraries (default: shared)
_static = os.getenv('STATIC') in ("1", "Y", "y")
# BUILD_STATIC=1 to just build static libraries
_build_static = _static or (os.getenv('BUILD_STATIC') in ("1", "Y", "y"))

# compiler flags (respect flags set explicitely)
# note: cmake ignores CPPFLAGS http://www.cmake.org/Bug/view.php?id=12928
if _for_windows:
  _common_flags = '-O3 -fno-strict-aliasing -pipe'
else:
  _common_flags = os.getenv('FLAGS') or '-O2' # -march=i686 -Wall -W
os.environ.setdefault('CFLAGS', _common_flags)
os.environ.setdefault('FFLAGS', _common_flags)
os.environ.setdefault('CXXFLAGS', _common_flags)
os.environ.setdefault('LDFLAGS', '')

# cctbx has a different build system, but it understands some env. vars.
_cctbx_configure_args = [ '--build=release',
                          #'--build-boost-python-extensions=False',
                          '--enable_openmp_if_possible=True',
                          '--use_system_libs=boost',
                          '--use_environment_flags']

_cctbx_modules = "mmtbx cctbx scitbx tntbx dxtbx rstbx phaser dials xia2"

# arguments passed to configure scripts (for autotools-based packages)
if not _for_windows:
  autogenargs = '--enable-silent-rules'

# number of parallel jobs (usually translates to "make -j N")
jobs = 2

# no need to build libraries that already installed
#skip += ["zlib", "libxml2"]
#skip += ["lapack", "fftw2", "libjpeg"]

_x11dir = None
if sys.platform == 'darwin':
    _x11dir = os.getenv('SDKROOT', '') + '/usr/X11'

################## end of user-friendly configuration #####################

# choose between shared and static libraries
if _build_static:
    autogenargs += ' --disable-shared --enable-static'
    if not _for_windows:
        cmakeargs += ' -DBUILD_SHARED_LIBS=OFF'
    _cctbx_configure_args += ['--static-libraries']
else:
    autogenargs += ' --enable-shared --disable-static'
    if not _for_windows:
        cmakeargs += ' -DBUILD_SHARED_LIBS=ON'
    module_cmakeargs['lapack'] = cmakeargs + " -DBUILD_STATIC_LIBS=OFF"

if _static:
    for _m in ['zlib', 'cctbx-phaser']:
        module_extra_env.setdefault(_m, {}).setdefault('LDFLAGS',
                                                    os.environ['LDFLAGS'])
    # '-static' flag is eaten by libtool, but -Wl,-static may not work at all
    os.environ['LDFLAGS'] += ' -static'
    cmakeargs += ' -D USE_STATIC=1'
    _cctbx_configure_args += ['--static-exe']
    os.environ['PKG_CONFIG'] = "pkg-config --static"

if sys.platform.startswith('linux') and not _for_windows:
    # '$' in -Wl,-rpath,$ORIGIN/... needs to be escaped differently
    # in different build scripts. It's easier to use $LD_RUN_PATH + patchelf.
    # (patchelf or chrpath is needed because libtool inserts own rpath)
    os.environ['LD_RUN_PATH'] = '$ORIGIN/../lib'
    cmakeargs += ' -D CMAKE_SKIP_RPATH=1' # prevent rpath removal on install
    module_autogenargs['qt4'] = '-no-rpath' # not sure if that's needed
    if os.getenv('CC') == 'icc':
        module_autogenargs['qt4'] = module_autogenargs.get('qt4','') + ' -platform linux-icc'

# handle cross-compilation
if _target:
    autogenargs += ' --host=' + _target
    # FFTW2 configure script fails to set correct CC automatically
    module_autogenargs['fftw2'] = autogenargs + (' CC=%s-gcc' % _target)
    # cross-compilation of cctbx python extensions is currently not supported
    if 'build-boost-python-extensions' not in "".join(_cctbx_configure_args):
        _cctbx_configure_args += ['--build-boost-python-extensions=False']
    # prepare Toolchain file for cmake
    import crosscmake as _cs
    cmakeargs += ' ' + _cs.write_toolchain(_target, prefix, buildroot)
    # if Wine is used during build, it must know where DLLs are
    # (this trick may not work with all wine configurations)
    os.environ['Path'] = ";".join(r"Z:\%s\bin" % p for p in
                                      (prefix, _cs.find_root_path(_target)))

# If $RELEASE is set, it confuses openssl config script. Unset it just in case.
module_extra_env['openssl'] = {'RELEASE': ''}

if _for_windows:
    module_autogenargs['ccif'] = autogenargs + ' --with-regex=regex'
#kjs I had to comment this out to get compiler to work on Win7-64. Originally enabled to allow
# large mem. exes on Win-32 systems.
#    if not _target or "x86_64" not in _target:
#        os.environ['LDFLAGS'] += ' -Wl,--large-address-aware'

if sys.platform == 'darwin':
    if sys.maxsize > 2**32:
        # openssl on OSX builds 32-bit version by default, it needs this hint
        module_extra_env['openssl'] = {'KERNEL_BITS': '64'}
    module_autogenargs['qt4'] = '-no-framework'
    if 'SDKROOT' in os.environ:
        module_autogenargs['qt4'] += ' -sdk ' + os.environ['SDKROOT']
        module_autogenargs['sip'] = '--universal --arch x86_64 --sdk ' + os.environ['SDKROOT']
    module_autogenargs['python'] = autogenargs.replace("--enable-shared"," ") + ( " -enable-framework=%s/Frameworks" % prefix)
    # On OSX skip libs included in 10.6+ SDK
    skip += ['zlib', 'libxml2', 'libxslt', 'lapack', 'sqlite3', 'curl']
    # and those included in XQuartz and used only by X11 programs
    skip += ['pixman', 'cairo']
    skip += ['bzr']
    os.environ['LIBXML2_LIBS']='-lxml2'
    os.environ['LIBXML2_CFLAGS']='-I/usr/include/libxml2'
    # on Mac Qt can be compiled only with Apple compiler
    _qt4_env = module_extra_env.setdefault('qt4', {})
    _qt4_env['CC'] = '/usr/bin/gcc'
    _qt4_env['CXX'] = '/usr/bin/g++'
    # XQuartz pc files are needed to build gtk
    os.environ.setdefault('PKG_CONFIG_PATH',
                          '/usr/lib/pkgconfig:%s/lib/pkgconfig' % _x11dir)
    module_extra_env.setdefault('coot', {}).setdefault('CPPFLAGS',
                                                       '-I%s/include' % _x11dir)

if _target or sys.maxsize <= 2**32: # probably building for 32-bit system
    # for pre Pentium4
    module_autogenargs['qt4'] = module_autogenargs.get('qt4','') + ' -no-sse2'

# with-python=false is a workaround for bjam bug.
# Python path is not written to project-config.jam, but is detected
# correctly later on.
#module_autogenargs['boost'] = '--with-python=false'

check_sysdeps = False # we don't have system modules

# this is needed to use file ccp4.xml
use_local_modulesets = True
modulesets_dir = os.path.dirname(os.path.abspath(__file__))
moduleset = 'ccp4.xml'
modules = ['default']
help_website=None

# read local settings from ~/.cjrc or $(pwd)/cj.rc if these files exist
for _local_config in (os.path.expanduser("~/.cjrc"), "cj.rc"):
    if os.path.exists(_local_config):
        execfile(_local_config)

if 'FC' in os.environ:
    os.environ.setdefault('F77', os.environ['FC'])
    os.environ.setdefault('F90', os.environ['FC'])

if '--compiler' not in " ".join(_cctbx_configure_args):
    if os.getenv('CC') == 'icc':
        _cctbx_configure_args += ['--compiler=icc']
    elif _for_windows:
        _cctbx_configure_args += ['--compiler=mingw']

# matplotlib uses CC for C++ compilation
if os.getenv('CC').endswith('icc'):
    if os.getenv('CXX').endswith('icpc'):
        module_extra_env.setdefault('matplotlib',{}).setdefault('CC','icpc')

# Tcl extension in diff-image and ccp4mapwish can be only built as shared.
if _build_static:
     skip += ["ccp4mapwish"]
else:
    if _for_windows:
        _tcldir = _tcldir.replace("\\", "/") # \->/ is needed for MinGW
        _tcllib = _tcllib.replace('.', '') # on Windows it's tcl84 not tcl8.4
    # set Tcl paths for diff-image and ccp4mapwish
    module_autogenargs.setdefault('diff-image', autogenargs+" --enable-tcl")
    if _tcldir:
        _tc = "%s -I%s/include" % (os.environ.get('CPPFLAGS',''), _tcldir)
        for _m in ['diff-image', 'ccp4mapwish']:
            module_extra_env.setdefault(_m, {}).setdefault("CPPFLAGS", _tc)
        os.environ['TCL_LIB_SPEC'] = '-L%s/lib -l%s' % (_tcldir, _tcllib)
    else:
        os.environ['TCL_LIB_SPEC'] = '-l' + _tcllib

for _m in ['numpy', 'scipy', 'scikit-learn']:
    _me = module_extra_env.setdefault(_m, {})
    _me.setdefault('FFLAGS', '-fPIC')
    _me.setdefault('BLAS', '%s/lib' % prefix)
    _me.setdefault('LAPACK', '%s/lib' % prefix)
    # note https://github.com/numpy/numpy/issues/1171
    _numpy_ldflags = os.getenv('LDFLAGS') + (' -L%s/lib ' % prefix)
    if sys.platform == "darwin":
      _numpy_ldflags += '-bundle -lpython2.7'
    else:
      _numpy_ldflags += '-shared'
    _me.setdefault('LDFLAGS', _numpy_ldflags)

if sys.platform == "darwin":
  module_extra_env.setdefault('pixie',{}).setdefault('LIBS','-lz')
else:
  module_extra_env.setdefault('pixie',{}).setdefault('LIBS','-ljpeg -lz')

if sys.platform == "darwin":
    # autoconf AC_PATH_XTRA macro is silly
    for _m in ['gtkglext', 'freeglut']:
        _env = module_extra_env.setdefault(_m, {})
        _env.setdefault("LDFLAGS", os.getenv('LDFLAGS','') +
                                   ' -L%s/lib -L%s/lib' % (_x11dir, prefix))
        _env.setdefault('CPPFLAGS', os.getenv('CPPFLAGS','') +
                                    ' -I%s/include' % _x11dir)
    # coot neads bigger headerpad
    module_extra_env['coot'].setdefault('LDFLAGS', os.getenv('LDFLAGS') +
      ' -L%s/lib -L%s/lib -Wl,-headerpad_max_install_names' % (_x11dir, prefix))

_me = module_extra_env.setdefault('gemmi', {})
_me.setdefault('PYTHON', '%s/libexec/python2.7' %prefix)
_me.setdefault('CPPFLAGS', '-I%s/include/python2.7' %prefix)

_me = module_extra_env.setdefault('mpi4py', {})
_me.setdefault('MPICC', '%s/libexec/openmpi/mpicc' % prefix)

# this is used internally to pass the arguments set above to cctbx
os.environ['SCONS_ARGS'] = "-j %d --ccp4 " % jobs
os.environ['CCTBX_FLAGS'] = " ".join(_cctbx_configure_args + [_cctbx_modules])
if os.getenv('PYTHONPATH'):
    module_extra_env.setdefault('cctbx-phaser',{}).setdefault('PYTHONPATH',"%s/checkout/cctbx-phaser/cctbx_project:%s/checkout/cctbx-phaser:%s/checkout/cctbx-phaser/phaser:%s/checkout/cctbx-phaser/tntbx:%s/checkout/cctbx-phaser/cctbx_project/boost_adaptbx:%s/checkout/cctbx-phaser/cctbx_project/libtbx/pythonpath:%s/lib/site-python:%s/install/lib/python2.7/site-packages:" % (_topdir,_topdir,_topdir,_topdir,_topdir,_topdir,prefix,_topdir) + os.getenv('PYTHONPATH') )
else:
    module_extra_env.setdefault('cctbx-phaser',{}).setdefault('PYTHONPATH',"%s/checkout/cctbx-phaser/cctbx_project:%s/checkout/cctbx-phaser:%s/checkout/cctbx-phaser/phaser:%s/checkout/cctbx-phaser/tntbx:%s/checkout/cctbx-phaser/cctbx_project/boost_adaptbx:%s/checkout/cctbx-phaser/cctbx_project/libtbx/pythonpath:%s/lib/site-python:%s/install/lib/python2.7/site-packages" % (_topdir,_topdir,_topdir,_topdir,_topdir,_topdir,prefix,_topdir) )

# hack: avoid adding /usr/* paths to PKG_CONFIG_PATH in jhbuild/config.py
if _target:
    os.environ.setdefault('PKG_CONFIG_PATH', '')

if os.path.exists(os.path.join(modulesets_dir, 'install-check')):
    installprog = os.path.join(modulesets_dir, 'install-check')
