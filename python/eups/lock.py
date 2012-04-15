import errno, glob, os, shutil, sys, time
import re
import hooks
import utils

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
            print >> utils.stdinfo, "Locking is disabled"
        nolocks = True

    if lockType is not None and not nolocks:
        if lockType == LOCK_EX:
            lockTypeName = "exclusive"
        else:
            lockTypeName = "shared"

        if verbose > 1:
            print >> utils.stdinfo, "Acquiring %s locks for command \"%s\"" % (lockTypeName, cmdName)

        dt = 1.0                        # number of seconds to wait
        for d in path:
            makeLock = True             # we can make the lock
            for i in range(1, ntry + 1):
                try:
                    lockDir = os.path.join(getLockPath(d), _lockDir)
                    getLockPath(d, create=True)

                    os.mkdir(lockDir)
                except OSError, e:
                    if lockType == LOCK_EX:
                        lockPids = listLockers(lockDir, getPids=True)
                        if len(lockPids) == 1 and lockPids[0] == os.environ.get("EUPS_LOCK_PID", "-1"):
                            pass        # OK, there's a lock but we know about it
                            if verbose:
                                print >> utils.stdinfo, "Lock is held by a parent, PID %d" % lockPids[0]
                        else:
                            if e.errno == errno.EEXIST:
                                reason = "locks are held by %s" % " ".join(listLockers(lockDir))
                            else:
                                reason = str(e)

                            msg = "Unable to take exclusive lock on %s" % (d)
                            if e.errno == errno.EACCES:
                                if verbose >= 0:
                                    print >> utils.stdinfo, "%s; your command may fail" % (msg)
                                    utils.stdinfo.flush()
                                makeLock = False
                                break
                                
                            msg += ": %s" % (reason)
                            if i == ntry:
                                raise RuntimeError(msg)
                            else:
                                print >> utils.stdinfo, "%s; retrying" % msg
                                utils.stdinfo.flush()

                                time.sleep(dt)
                                continue
                    else:
                        if not os.path.exists(lockDir):
                            if verbose:
                                print >> utils.stdwarn, "Unable to lock %s; proceeding with trepidation" % d
                            return []

                if not makeLock:
                    continue

                if verbose > 2:
                    print >> utils.stdinfo, "Creating lock directory %s" % (lockDir)
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
            
            if not os.environ.has_key("EUPS_LOCK_PID"): # remember the PID of the process taking the lock
                os.environ["EUPS_LOCK_PID"] = "%d" % os.getpid()
                os.putenv("EUPS_LOCK_PID", os.environ["EUPS_LOCK_PID"])
            #
            #
            # Create a file in it
            #
            import pwd
            who = pwd.getpwuid(os.geteuid())[0]
            pid = os.getpid()

            lockFile = "%s-%s.%d" % (lockTypeName, who, pid)

            try:
                fd = os.open(os.path.join(lockDir, lockFile), os.O_EXCL | os.O_RDWR | os.O_CREAT)
                os.close(fd)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    # should not occur
                    raise

            locks.append((lockDir, lockFile))

            if verbose > 3:
                print >> utils.stdinfo, "Creating lockfile %s" % (os.path.join(lockDir, lockFile))
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
                print >> utils.stdinfo, "Removing lockfile %s" % (f)

            os.remove(f)

        nlockFiles = len(os.walk(d).next()[2])
        if nlockFiles == 0:
            os.rmdir(d)

def clearLocks(path, verbose=0, noaction=False):
    """Remove all locks found in the directories listed in path"""
    
    for d in path:
        lockDir = os.path.join(getLockPath(d), _lockDir)

        if not os.path.isdir(lockDir):
            continue

        if noaction:
            print >> sys.stderr, "rm -rf %s" % lockDir
        else:
            if verbose:
                print >> utils.stdinfo, "Removing %s" % lockDir

            try:
                shutil.rmtree(lockDir)
            except OSError, e:
                print >> utils.stderr, "Unable to remove %s: %s" % (lockDir, e)                    

def listLocks(path, verbose=0, noaction=False):
    """List all locks found in the directories listed in path"""

    for d in path:
        lockDir = os.path.join(getLockPath(d), _lockDir)

        if not os.path.isdir(lockDir):
            continue

        print "%-30s %s" % (d + ":", " ".join(listLockers(lockDir)))

def listLockers(lockDir, globPattern="*", getPids=False):
    """List all the owners of locks in a lockDir"""
    lockers = []
    for f in [os.path.split(f)[1] for f in glob.glob(os.path.join(lockDir, globPattern))]:
        who, pid = re.split(r"[-.]", f)[1:]
        if getPids:
            lockers.append(pid)
        else:
            lockers.append("[user=%s, pid=%s]" % (who, pid))

    return lockers
