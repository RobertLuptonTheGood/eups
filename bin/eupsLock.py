import errno, os, stat, sys, time
import re

def lock(lockfile, who, max_wait=10):
    """Get a lockfile, identifying yourself as who;  wait a maximum of max_wait seconds"""
    while True:
        try:
            fd = os.open(lockfile, os.O_EXCL | os.O_RDWR | os.O_CREAT)
            # we created the lockfile, so we're the owner
            break
        except OSError, e:
            if e.errno != errno.EEXIST:
                # should not occur
                raise

        try:
            # the lock file exists, try to stat it to get its age
            # and read it's contents to report the owner PID
            f = open(lockfile, "r")
            s = os.stat(lockfile)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise RuntimeError ("%s exists but stat() failed: %s" % (lockfile, e.strerror))
            # we didn't create the lockfile, so it did exist, but it's gone now. Just try again
            continue

        # we didn't create the lockfile and it's still there, check its age
        pid = re.sub(r"\n$", "", f.readline())
        who = re.sub(r"\n$", "", f.readline())

        now = int(time.time())
        if now - s[stat.ST_MTIME] > max_wait:
            raise RuntimeError, ("%s has been locked for more than %d seconds (User %s, PID %s)" %
                                 (lockfile, max_wait, who, pid))

        # it's not been locked too long, wait a while and retry
        f.close()
        print >> sys.stderr, "Waiting for %s (User %s, PID %s)" % (lockfile, who, pid)
        time.sleep(2)

    # if we get here. we have the lockfile. Convert the os.open file
    # descriptor into a Python file object and record our PID in it

    f = os.fdopen(fd, "w")
    f.write("%d\n" % os.getpid())
    f.write("%s\n" % who)
    f.close()

def unlock(lockfile):
    try:
        os.unlink(lockfile)
    except OSError, e:
        if e.errno != errno.ENOENT:
            print >> sys.stderr, "Clearing lockfile %s: %s" % (lockfile, e)
