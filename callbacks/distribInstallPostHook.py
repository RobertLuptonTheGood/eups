"""
This file is imported and distribInstallPostHook() is run after each product is installed

Not generally needed if you're building from source, but with binary installations it may
be critical (e.g. to patch up os/x's SIP protection)
"""

from distutils.spawn import find_executable
import io
import locale
import mmap
import re
import os
import subprocess
import sys

import eups.utils as utils

__names__ = ['distribInstallPostHook']

# lifted from conda-build/conda_build/os_utils/elf.py

ELF_MAGIC = b'\x7fELF'
# extensions which are assumed to belong to non-ELF files
ELF_NO_EXT = (
    '.py', '.pyc', '.pyo', '.h', '.a', '.c', '.txt', '.html',
    '.xml', '.png', '.jpg', '.gif',
    '.o'  # ELF but not what we are looking for
)
SHEBANG_REGEX = re.compile(br'^#!.+$', re.M)

def is_elf(path):
    if path.endswith(ELF_NO_EXT) or os.path.islink(path) or not os.path.isfile(path):
        return False
    with open(path, 'rb') as fi:
        head = fi.read(4)
    return bool(head == ELF_MAGIC)


# /elf.py


# lifted from conda-build/conda_build/os_utils/macho.py

MACHO_NO_EXT = (
    '.py', '.pyc', '.pyo', '.h', '.a', '.c', '.txt', '.html',
    '.xml', '.png', '.jpg', '.gif', '.class',
)

MACHO_MAGIC = {
    b'\xca\xfe\xba\xbe': 'MachO-universal',
    b'\xce\xfa\xed\xfe': 'MachO-i386',
    b'\xcf\xfa\xed\xfe': 'MachO-x86_64',
    b'\xfe\xed\xfa\xce': 'MachO-ppc',
    b'\xfe\xed\xfa\xcf': 'MachO-ppc64',
}

def is_macho(path):

    if path.endswith(MACHO_NO_EXT) or os.path.islink(path) or not os.path.isfile(path):
        return False
    with open(path, 'rb') as fi:
        head = fi.read(4)
    return bool(head in MACHO_MAGIC)


# /macho.py

# lifted from conda-build/conda_build/post.py

def is_obj(path):
    assert sys.platform != 'win32'
    return bool((sys.platform.startswith('linux') and is_elf(path)) or
                (sys.platform == 'darwin' and is_macho(path)))


def fix_shebang(path, build_python, verbose=0):
    """Fix #! lines ("shebangs")
    @param path:  full path to file; all installed files are passed (individually) to this function
    @param build_python: full path to the python we're using
    @param verbose:  be chatty?
    """
    # the mmap-fu will fail if a file is not opened for writing -- we can't fix
    # unwritable files so they should be completely skipped.
    if not os.access(path, os.R_OK | os.W_OK):
        return

    if is_obj(path):
        return
    elif os.path.islink(path):
        return
    elif not os.path.isfile(path):
        return

    if os.stat(path).st_size == 0:
        return

    prefenc = locale.getpreferredencoding()
    with io.open(path, encoding=prefenc, mode='r+') as fi:
        try:
            data = fi.read(100)
            fi.seek(0)
        except UnicodeDecodeError:  # file is binary
            return

        # regexp on the memory mapped file so we only read it into
        # memory if the regexp matches.
        try:
            mm = mmap.mmap(fi.fileno(), 0)
        except OSError:
            mm = fi
        m = SHEBANG_REGEX.match(mm)
        if not m:
            return

        # skip scripts that use #!/usr/bin/env
        if b'/usr/bin/env' in m.group():
            return

        if not b'python' in m.group():
            return

        data = mm[:]

    # encoding = sys.stdout.encoding or 'utf8'
    encoding = 'utf8'

    # remove the conda prefix logic and set the path to the python interp
    # explicity
    py_exec = (build_python)
    new_data = SHEBANG_REGEX.sub(b'#!' + py_exec.encode(encoding), data, count=1)
    if new_data == data:
        return

    if verbose > 0:
        print("updating shebang for %s" % path, file=utils.stdinfo)

    # save original file mode
    mode = os.stat(path).st_mode
    with io.open(path, 'w', encoding=encoding) as fo:
        fo.write(new_data.decode(encoding))
    # restore file mode
    os.chmod(path, mode)

# /post.py
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Patch up bad symbolic link files
#   e.g. libFoo.so -> libFoo_1_5.so
# (also .dylib files on os/x)
#
SO_REGEX = re.compile(r".*\.(dylib|so)$")

def fix_soLinks(path, verbose=False):
    """Fix .dylib and .so links that point outside the installation tree
    
    @param path:  full path to file; all installed files are passed (individually) to this function
    @param verbose:  be chatty?
    """

    if not SO_REGEX.match(path) or not os.path.islink(path):
        return

    if verbose > 0:
        print("Converting symbolic link for %s to be relative" % (path), file=utils.stdinfo)
    #
    # I could create a link using os.symlink(), but I want to create a relative link and
    # I don't want to have to cd into the directory.  Using Popen(..., cwd=XXX) is cleaner
    #
    libDir, libName = os.path.split(path)
    targetName = os.path.split(os.readlink(path))[1]

    subprocess.Popen(["ln", "-fs", targetName, libName], cwd=libDir)
    
#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def distribInstallPostHook(prod_install_path, verbose=0):
    if not os.path.isdir(prod_install_path):
        raise RuntimeError('EUPS product install path is missing')

    py = find_executable('python')

    for root, dirs, files in os.walk(prod_install_path):
        for f in files:
            path = os.path.join(root, f)
            fix_shebang(path, py, verbose=verbose)
            fix_soLinks(path, verbose=verbose)
