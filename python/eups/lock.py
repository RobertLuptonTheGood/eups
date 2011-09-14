import errno, glob, os, shutil, sys
import re

#
# Types of locks
#
LOCK_SH = 1                             # acquire a shared lock
LOCK_EX = 2                             # acquire an exclusive lock

_lockDir = ".lockDir"                   # name of lock directory

def takeLocks(cmdName, path, lockType, nolocks=False, verbose=0):
    locks = []

    if lockType is not None and not nolocks:
        if lockType == LOCK_EX:
            lockTypeName = "exclusive"
        else:
            lockTypeName = "shared"

        if verbose > 1:
            print >> sys.stderr, "Acquiring %s locks for command \"%s\"" % (lockTypeName, cmdName)

        for d in path:
            lockDir = os.path.join(d, _lockDir)

            try:
                os.mkdir(lockDir)
            except OSError:
                if lockType == LOCK_EX:
                    raise RuntimeError("Unable to take exclusive lock on %s: locks are held by  %s" %
                                       (d, " ".join(listLockers(lockDir))))
                else:
                    if not os.path.exists(lockDir):
                        if verbose:
                            print >> sys.stderr, "Unable to lock %s; proceeding with trepidation" % d
                        return []
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
                   os.environ.get("LOCK_PID", "-1") == listLockers(lockDir, "exclusive*", getPids=True)[0]:
                    pass
                else:
                    raise RuntimeError("Unable to take shared lock on %s: an exclusive lock is held by %s" %
                                       (d, " ".join(lockers)))

            if not os.environ.has_key("LOCK_PID"): # remember the PID of the process taking the lock
                os.environ["LOCK_PID"] = "%d" % os.getpid()                         
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
                print >> sys.stderr, "Removing lockfile %s" % (f)

            os.remove(f)

        nlockFiles = len(os.walk(d).next()[2])
        if nlockFiles == 0:
            os.rmdir(d)

def clearLocks(path, verbose=0, noaction=False):
    """Remove all locks found in the directories listed in path"""
    
    for d in path:
        lockDir = os.path.join(d, _lockDir)

        if not os.path.isdir(lockDir):
            continue

        if noaction:
            print >> sys.stderr, "rm -rf %s" % lockDir
        else:
            if verbose:
                print >> sys.stderr, "Removing %s" % lockDir

            try:
                shutil.rmtree(lockDir)
            except OSError, e:
                print >> sys.stderr, "Unable to remove %s: %s" % (lockDir, e)                    

def listLocks(path, verbose=0, noaction=False):
    """List all locks found in the directories listed in path"""

    for d in path:
        lockDir = os.path.join(d, _lockDir)

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
