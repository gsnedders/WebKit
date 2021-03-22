# Required for Python to search this directory for module files

# Keep this file free of any code or import statements that could
# cause either an error to occur or a log message to be logged.
# This ensures that calling code can import initialization code from
# webkitpy before any errors or log messages due to code in this file.
# Initialization code can include things like version-checking code and
# logging configuration code.
#
# We do not execute any version-checking code or logging configuration
# code in this file so that callers can opt-in as they want.  This also
# allows different callers to choose different initialization code,
# as necessary.

import os
import sys

# We always want the real system version
os.environ['SYSTEM_VERSION_COMPAT'] = '0'

libraries = os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'libraries')
sys.path.insert(0, os.path.join(libraries, 'webkitcorepy'))

if sys.platform == 'darwin':
    is_root = not os.getuid()
    does_own_libraries = os.stat(libraries).st_uid == os.getuid()
    if (is_root or not does_own_libraries):
        libraries = os.path.expanduser('~/Library/webkitpy')

from webkitcorepy import AutoInstall, Package, Version
AutoInstall.set_directory(os.path.join(libraries, 'autoinstalled', 'python-{}'.format(sys.version_info[0])))

if sys.version_info > (3, 4):
    # Python >=3.5.*
    AutoInstall.register(Package('astroid', Version(2, 5, 1)))
    AutoInstall.register(Package('isort', Version(5, 8, 0)))
    AutoInstall.register(Package('pylint', Version(2, 6, 2)))
else:
    AutoInstall.register(Package('astroid', Version(1, 6, 6)))
    AutoInstall.register(Package('backports.functools-lru-cache', Version(1, 6, 1)))
    AutoInstall.register(Package('enum34', Version(1, 1, 10)))
    AutoInstall.register(Package('futures', Version(3, 3, 0)))
    AutoInstall.register(Package('isort', Version(4, 3, 21)))
    AutoInstall.register(Package('logilab.astng', Version(0, 24, 3), pypi_name='logilab-astng', aliases=['logilab']))
    AutoInstall.register(Package('logilab.common', Version(1, 4, 4), pypi_name='logilab-common', aliases=['logilab']))
    AutoInstall.register(Package('pathlib', Version(2, 3, 5), pypi_name='pathlib2'))
    AutoInstall.register(Package('pylint', Version(1, 9, 5)))
    AutoInstall.register(Package('singledispatch', Version(3, 6, 1)))

AutoInstall.register(Package('atomicwrites', Version(1, 4, 0)))
AutoInstall.register(Package('attr', Version(20, 3, 0), pypi_name='attrs'))
AutoInstall.register(Package('bs4', Version(4, 9, 3), pypi_name='beautifulsoup4'))
AutoInstall.register(Package('blessings', Version(1, 7)))
AutoInstall.register(Package('configparser', Version(4, 0, 2)))
AutoInstall.register(Package('contextlib2', Version(0, 6, 0)))
AutoInstall.register(Package('coverage', Version(5, 5)))
AutoInstall.register(Package('distro', Version(1, 5, 0)))
AutoInstall.register(Package('funcsigs', Version(1, 0, 2)))
AutoInstall.register(Package('genshi', Version(0, 7, 5), pypi_name='Genshi'))
AutoInstall.register(Package('html5lib', Version(1, 1)))
AutoInstall.register(Package('importlib-metadata', Version(2, 1, 1)))
AutoInstall.register(Package('lazy-object-proxy', Version(1, 5, 2)))
AutoInstall.register(Package('mccabe', Version(0, 6, 1)))
AutoInstall.register(Package('mechanize', Version(0, 4, 5)))
AutoInstall.register(Package('more_itertools', Version(5, 0, 0), pypi_name='more-itertools'))
AutoInstall.register(Package('mozfile', Version(2, 1, 0)))
AutoInstall.register(Package('mozinfo', Version(1, 2, 2)))
AutoInstall.register(Package('mozlog', Version(7, 0, 1)))
AutoInstall.register(Package('mozprocess', Version(1, 2, 1)))
AutoInstall.register(Package('mozterm', Version(1, 0, 0)))
AutoInstall.register(Package('packaging', Version(20, 9)))
AutoInstall.register(Package('pathlib2', Version(2, 3, 5)))
AutoInstall.register(Package('pluggy', Version(0, 6, 0)))
AutoInstall.register(Package('py', Version(1, 10, 0)))
AutoInstall.register(Package('pycodestyle', Version(2, 7, 0)))
AutoInstall.register(Package('pyparsing', Version(2, 4, 7)))
# pytest should match the version in LayoutTests/imported/w3c/web-platform-tests/tools/third_party/pytest
AutoInstall.register(Package('pytest', Version(3, 6, 2), implicit_deps=['pytest_timeout']))
AutoInstall.register(Package('pytest_timeout', Version(1, 4, 2), pypi_name='pytest-timeout'))
AutoInstall.register(Package('scandir', Version(1, 10, 0)))
AutoInstall.register(Package('selenium', Version(3, 141, 0)))
AutoInstall.register(Package('six', Version(1, 15, 0)))
AutoInstall.register(Package('soupsieve', Version(1, 9, 6)))
AutoInstall.register(Package('toml', Version(0, 10, 2)))
AutoInstall.register(Package('urllib3', Version(1, 26, 4)))
AutoInstall.register(Package('wcwidth', Version(0, 2, 5)))
AutoInstall.register(Package('webencodings', Version(0, 5, 1)))
AutoInstall.register(Package('wrapt', Version(1, 12, 1)))
AutoInstall.register(Package('zipp', Version(1, 2, 0)))
AutoInstall.register(Package('zope.interface', Version(5, 3, 0), aliases=['zope'], pypi_name='zope-interface'))

AutoInstall.register(Package('webkitscmpy', Version(0, 12, 5)), local=True)

import webkitscmpy
