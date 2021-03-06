"""
Utility functions for bind modules.
"""
from __future__ import absolute_import
from rez.vendor.version.version import Version
from rez.exceptions import RezBindError
from rez.config import config
from rez.system import system
from rez.util import which
from rez.utils.execution import Popen
from rez.utils.logging_ import print_debug
from rez.vendor.six import six
from pipes import quote
import subprocess
import os.path
import os
import platform
import sys


basestring = six.string_types[0]


def log(msg):
    if config.debug("bind_modules"):
        print_debug(msg)


def make_dirs(*dirs):
    path = os.path.join(*dirs)
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def run_python_command(commands, exe=None):
    py_cmd = "; ".join(commands)
    args = [exe or sys.executable, "-c", py_cmd]
    stdout, stderr, returncode = _run_command(args)
    return (returncode == 0), stdout.strip(), stderr.strip()


def get_version_in_python(name, commands):
    success, out, err = run_python_command(commands)
    if not success or not out:
        raise RezBindError("Couldn't determine version of module %s: %s"
                           % (name, err))
    version = out
    return version


def check_version(version, range_=None):
    """Check that the found software version is within supplied range.

    Args:
        version: Version of the package as a Version object.
        range_: Allowable version range as a VersionRange object.
    """
    if range_ and version not in range_:
        raise RezBindError("found version %s is not within range %s"
                           % (str(version), str(range_)))


def find_exe(name, filepath=None):
    """Find an executable.

    Args:
        name: Name of the program, eg 'python'.
        filepath: Path to executable, a search is performed if None.

    Returns:
        Path to the executable if found, otherwise an error is raised.
    """
    if filepath:
        if not os.path.exists(filepath):
            with open(filepath):
                pass  # raise IOError
        elif not os.path.isfile(filepath):
            raise RezBindError("not a file: %s" % filepath)
    else:
        filepath = which(name)
        if not filepath:
            raise RezBindError("could not find executable: %s" % name)

    return filepath


def extract_version(exepath, version_arg, line_index=0, word_index=-1, version_rank=3):
    """Run an executable and get the program version.

    Args:
        exepath: Filepath to executable.
        version_arg: Arg to pass to program, eg "-V". Can also be a list.
        line_index: Expect the Nth line of output to contain the version.
        word_index: Expect the Nth word of output to be the version.
        version_rank: Cap the version to this many tokens.

    Returns:
        `Version` object.
    """
    if isinstance(version_arg, basestring):
        version_arg = [version_arg]
    args = [exepath] + version_arg

    stdout, stderr, returncode = _run_command(args)
    if returncode:
        raise RezBindError("Failed to execute %s: %s\n(error code %d)"
                           % (exepath, stderr, returncode))

    stdout = stdout.strip().split('\n')[line_index].strip()
    log("Extracting version from output: '%s'" % stdout)

    try:
        strver = stdout.split()[word_index]
        toks = strver.replace('.', ' ').replace('-', ' ').split()
        strver = '.'.join(toks[:version_rank])
        version = Version(strver)
    except Exception as e:
        raise RezBindError("Failed to parse version from output '%s': %s"
                           % (stdout, str(e)))

    log("Extracted version: '%s'" % str(version))
    return version


def _run_command(args):
    cmd_str = ' '.join(quote(x) for x in args)
    log("running: %s" % cmd_str)

    # https://github.com/nerdvegas/rez/pull/659
    use_shell = ("Windows" in platform.system())

    p = Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=use_shell,
        text=True
    )

    stdout, stderr = p.communicate()
    return stdout, stderr, p.returncode


def get_implicit_system_variant():
    """
    Filter system variant using implicit packages from config.
    This allows to use implicit packages to control the granularity of the system variant.
    Rather than having something like [['platform-windows', 'arch-AMD64', 'os-windows-10.0.18362.SP0']]
    Convert it into somethign like: variants = [['platform-windows']]

    It's all controlled by the implicit packages setting, by default in rezconfig.py it is set to:
    implicit_packages = [
    "~platform=={system.platform}",
     "~arch=={system.arch}",
     "~os=={system.os}",
    ]
    So to reduce it we just need to set it to:
    implicit_packages = [
    "~platform=={system.platform}"
    ]
    In general it is enough for windows systems, in Linux probably os is also needed, but for instance arch can be dropped since in general
    nowdays everybody works on amd64 .

    An implicit package looks like: ~platform==windows
    The system variant string usually looks like: ['platform-windows', 'arch-AMD64', 'os-windows-10.0.18362.SP0']
    """
    implicit_packages = [var.split('==')[0][1:] for var in config.implicit_packages]
    variants = [var for var in system.variant if var.split('-')[0] in implicit_packages]

    return variants
    pass


def get_app_folders_vers(appname, install_root='/opt', test_folder=None):
    """
    This is the basis for folders versions bindin mechanism.
    This assume the next:
    App versions are installed under the root folder, install_root, inside a folder
    with  the same name as the app, and then with subfolders for versions.
    For instance:
    /opt/houdini/hfs17.5.626
    /opt/houdini/hfs18.0.312

    /opt/python/python27
    /opt/python/python37

    And so on ...
    Or the tool is directly installed in the root folder and the are not subfolders with versions. In this case somethiing like: /opt/cmder
    will just return the app folder. This is only checked if test_folder is passed.

    The folders version names doesnt matter, they are assume to be diferent versions.
    Is the responsability of the bind modules to provide fuinctions to test the folder and to work out
    what version is installed in the folder.
    test_folder is doing that, is a function that has one parameter, the path, and can check whether or not the folder is a valid folder for the
    tools.
    Is provided in the bind module.
    For instance for a pytthon install, it can check the the folder has a python.exe or python executable.
    This function just return a list of folders with version of the appname installed on them.

    Args:
        appname: name of the app to bind
        install_root: base install location, under it there must be a folder with  the same name as the app and inside the different verions folder.
        test_folder: function implemented by the user in the bind module for the app. 
            Just do some test to check whether or not the folder is an install of the tool. Return Tru or False

    Returns:
        List of folders with versions of the tool.
    """
    baseappinstall = os.path.normpath(os.path.join(install_root, appname))
    if not os.path.exists(baseappinstall) or not os.path.isdir(baseappinstall):
        raise RezBindError(
            "%s base install path doesn't exists or is not a directory: %s" % (appname, baseappinstall))
    # Check if the passed path is already the app folder, so there are not folders with version, this is the actual folder for the app
    if test_folder is not None and test_folder(baseappinstall):
        return [baseappinstall]
    versdirs = [os.path.normpath(os.path.join(baseappinstall, lsfile)) for lsfile in os.listdir(
        baseappinstall) if os.path.isdir(os.path.join(baseappinstall, lsfile))]
    # versdirs = os.listdir(baseappinstall)
    if test_folder is not None:
        # Call to filter function
        return [validdir for validdir in versdirs if test_folder(validdir)]
    else:
        return versdirs

    pass


def use_folders_vers(arg):
    """
    Work out wheter or not folders versions package mode should be used.
    It checks arguments and config settigns.
    If --use-folders-vers is passed to the bind command or use_folders_vers is set in rez config then this
    method will be used.

    Arguments:
        arg: result of opt.use_folders_vers in the bind module. Option passed as an argument.

    Returns:
        True if use folders versions should be used.
    """
    return arg is not None or (hasattr( config, 'bind_use_folders_vers') and config.bind_use_folders_vers)

def get_use_folders_vers_root(arg):
    """
    Guess root install forlder for user folders versions mode.
    arg is the argument passed in the bind command as --use-folders-vers. If passed this will be used, otherwise it will check if
    there is a default set in rezconfig.py using the option bind_use_folders_vers_root .

    Arguments:
        arg: result of opt.use_folders_vers in the bind module. Option passed as an argument.
    """
    root_install = arg
    if ( root_install is None or not root_install ) and (hasattr(config, 'bind_use_folders_vers') and config.bind_use_folders_vers):
        if( hasattr(config, 'bind_use_folders_vers_root') and config.bind_use_folders_vers_root and config.bind_use_folders_vers_root.strip() ):
            # root folder specified in rezconfig
            root_install = config.bind_use_folders_vers_root
        else:
            # If there neither the path has been passednor it has been spcified in rezconfig then fallback to the defaul /opt .
            root_install = '/opt'

    return root_install
    pass

def get_install_path(install_path, pkgtype=None):
    """
    Based on command line options, detect when a local or release (--release) path is needed.
    This is called from the bind module so it can pass the package type and hence use release_package_root
    if possible.
    In other words, allows the bind module to work out the release path based on package type, if provided.

    Arguments:
        opts: command line options passed  to the bind command. Used to detect if --release is used.
        pkgtype: package type, used to automatically release into designated folder.

    Returns:
        install path
    """
    if install_path == config.release_packages_path:
        if pkgtype is not None:
            if hasattr(config, 'release_packages_root') and config.release_packages_root:
                if hasattr(config, 'release_packages_types') and len(config.release_packages_types) > 0:
                    if pkgtype in config.release_packages_types:
                        install_path = os.path.normpath(os.path.join(config.release_packages_root, pkgtype))

    return install_path

# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
