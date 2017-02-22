from __future__ import absolute_import, print_function
import errno
import glob
import os
import shutil
import sys
import time
import re
from . import hooks
from . import utils

#
# Types of locks
#
LOCK_SH = 1                             # acquire a shared lock
LOCK_EX = 2                             # acquire an exclusive lock

_lockDir = ".lockDir"                   # name of lock directory

def getLockPath(dirName, create=False):
    """Get the directory path that should prefix the """
    if hooks.config.site.lockDirectoryBase == hooks._defaultLockDirectoryBase:
        # Put the locks into the ups_db directory directly
        return dirName
    else:
        base = hooks.config.site.lockDirectoryBase

        if base is None: # no locking
            return None

        if not os.path.isabs(base):
            raise RuntimeError("hooks.config.site.lockDirectoryBase must be an absolute path, not \"%s\"" %
                               hooks.config.site.lockDirectoryBase)

        if os.path.isabs(dirName):
            dirName = dirName[1:]

        dirName = os.path.join(base, dirName)

        if create:
            if not os.path.exists(dirName):
                os.makedirs(dirName)

        return dirName

def takeLocks(cmdName, path, lockType, nolocks=False, ntry=10, verbose=0):
    locks = []

    if hooks.config.site.lockDirectoryBase is None:
        if verbose > 2:
            print("Locking is disabled", file=utils.stdinfo)
        nolocks = True

    if lockType is not None and not nolocks:
        if lockType == LOCK_EX:
            lockTypeName = "exclusive"
        else:
            lockTypeName = "shared"

        if verbose > 1:
            print("Acquiring %s locks for command \"%s\"" % (lockTypeName, cmdName), file=utils.stdinfo)

        dt = 1.0                        # number of seconds to wait
        for d in path:
            makeLock = True             # we can make the lock
            for i in range(1, ntry + 1):
                try:
                    lockDir = os.path.join(getLockPath(d), _lockDir)
                    getLockPath(d, create=True)

                    os.mkdir(lockDir)
                except OSError as e:
                    if lockType == LOCK_EX:
                        lockPids = listLockers(lockDir, getPids=True)
                        if len(lockPids) == 1 and lockPids[0] == os.environ.get("EUPS_LOCK_PID", "-1"):
                            pass        # OK, there's a lock but we know about it
                            if verbose:
                                print("Lock is held by a parent, PID %d" % lockPids[0], file=utils.stdinfo)
                        else:
                            if e.errno == errno.EEXIST:
                                reason = "locks are held by %s" % " ".join(listLockers(lockDir))
                            else:
                                reason = str(e)

                            msg = "Unable to take exclusive lock on %s" % (d)
                            if e.errno == errno.EACCES:
                                if verbose >= 0:
                                    print("%s; your command may fail" % (msg), file=utils.stdinfo)
                                    utils.stdinfo.flush()
                                makeLock = False
                                break

                            msg += ": %s" % (reason)
                            if i == ntry:
                                raise RuntimeError(msg)
                            else:
                                print("%s; retrying" % msg, file=utils.stdinfo)
                                utils.stdinfo.flush()

                                time.sleep(dt)
                                continue
                    else:
                        if not os.path.exists(lockDir):
                            if verbose:
                                print("Unable to lock %s; proceeding with trepidation" % d, file=utils.stdwarn)
                            return []

                if not makeLock:
                    continue

                if verbose > 2:
                    print("Creating lock directory %s" % (lockDir), file=utils.stdinfo)
                #
                # OK, the lock directory exists.
                #
                # If we're a shared lock, we need to check that no-one holds an exclusive lock (or, if someone
                # does hold the lock, that we're the holder's child)
                #
                # N.b. the check isn't atomic, but that's conservative (we don't care if the exclusive lock's
                # dropped while we're pondering its existence)
                #
                lockers = listLockers(lockDir, "exclusive*")
                if len(lockers) > 0:
                    if len(lockers) == 1 and \
                       os.environ.get("EUPS_LOCK_PID", "-1") == \
                       listLockers(lockDir, "exclusive*", getPids=True)[0]:
                        pass
                    else:
                        raise RuntimeError(("Unable to take shared lock on %s: " +
                                            "an exclusive lock is held by %s") % (d, " ".join(lockers)))

                break                   # got the lock

            if not makeLock:
                continue

            if "EUPS_LOCK_PID" not in os.environ: # remember the PID of the process taking the lock
                os.environ["EUPS_LOCK_PID"] = "%d" % os.getpid()
                os.putenv("EUPS_LOCK_PID", os.environ["EUPS_LOCK_PID"])
            #
            #
            # Create a file in it
            #
            who = utils.getUserName()
            pid = os.getpid()

            lockFile = "%s-%s.%d" % (lockTypeName, who, pid)

            try:
                fd = os.open(os.path.join(lockDir, lockFile), os.O_EXCL | os.O_RDWR | os.O_CREAT)
                os.close(fd)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    # should not occur
                    raise

            locks.append((lockDir, lockFile))

            if verbose > 3:
                print("Creating lockfile %s" % (os.path.join(lockDir, lockFile)), file=utils.stdinfo)
    #
    # Cleanup, even in the event of the user being rude enough to use kill
    #
    def cleanup(*args):
        giveLocks(locks, verbose)

    import atexit
    atexit.register(cleanup)            # regular exit

    import signal
    signal.signal(signal.SIGINT, cleanup) # user killed us
    signal.signal(signal.SIGTERM, cleanup)

    return locks

def giveLocks(locks, verbose=0):
    """Give up all locks in the provided list of (directory, file)

    If the directory ends up empty, it is removed
    """
    for d, f in locks:
        if not os.path.isdir(d):
            continue

        f = os.path.join(d, f)

        if os.path.exists(f):
            if verbose > 2:
                print("Removing lockfile %s" % (f), file=utils.stdinfo)

            os.remove(f)

        nlockFiles = len(next(os.walk(d))[2])
        if nlockFiles == 0:
            os.rmdir(d)

def clearLocks(path, verbose=0, noaction=False):
    """Remove all locks found in the directories listed in path"""

    for d in path:
        lockDir = getLockPath(d)
        if not lockDir:
            continue

        lockDir = os.path.join(lockDir, _lockDir)
        if not os.path.isdir(lockDir):
            continue

        if noaction:
            print("rm -rf %s" % lockDir, file=sys.stderr)
        else:
            if verbose:
                print("Removing %s" % lockDir, file=utils.stdinfo)

            try:
                shutil.rmtree(lockDir)
            except OSError as e:
                print("Unable to remove %s: %s" % (lockDir, e), file=utils.stderr)

def listLocks(path, verbose=0, noaction=False):
    """List all locks found in the directories listed in path"""

    for d in path:
        lockPath = getLockPath(d)
        if not lockPath:                # no locking
            continue

        lockDir = os.path.join(lockPath, _lockDir)

        if not os.path.isdir(lockDir):
            continue

        print("%-30s %s" % (d + ":", " ".join(listLockers(lockDir))))

def listLockers(lockDir, globPattern="*", getPids=False):
    """List all the owners of locks in a lockDir"""
    lockers = []
    for f in [os.path.split(f)[1] for f in glob.glob(os.path.join(lockDir, globPattern))]:
        mat = re.search(r"^(exclusive|shared)-(.+)\.(\d+)$", f)
        if not mat:
            print("Unable to parse lockfile name %s" % f, file=utils.stdwarn)
            continue

        lockType, who, pid = mat.groups()
        if getPids:
            lockers.append(pid)
        else:
            lockers.append("[user=%s, pid=%s]" % (who, pid))

    return lockers
