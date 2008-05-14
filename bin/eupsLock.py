import errno, os, stat, sys, time
import re

def lock(lockfile, myIdentity, max_wait=10, unlock=False, force=False):
    """Get a lockfile, identifying yourself as myIdentity;  wait a maximum of max_wait seconds"""

    myPid = os.getpid()
    count = 0                           # count of number of times the lock is held
    while True:
        try:
            fd = os.open(lockfile, os.O_EXCL | os.O_RDWR | os.O_CREAT)
            f = os.fdopen(fd, "w")
            
            # we created the lockfile, so we're the owner
            break
        except OSError, e:
            if e.errno != errno.EEXIST:
                # should not occur
                raise

        try:
            # the lock file exists, try to stat it to get its age
            # and read its contents to report the owner and PID
            f = os.fdopen(os.open(lockfile, os.O_EXCL | os.O_RDWR), "rw")
            s = os.stat(lockfile)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise RuntimeError ("%s exists but stat() failed: %s" % (lockfile, e.strerror))
            # we didn't create the lockfile, so it did exist, but it's gone now. Just try again
            continue

        # we didn't create the lockfile and it's still there, check its age
        pid = -1
        fileOwner = "(unknown)"
        try:
            pid = int(f.readline())
            fileOwner = re.sub(r"\n$", "", f.readline())
            count = int(f.readline())
            f.close()
        except:
            pass

        if pid == myPid:                # OK, we own it
            f = open(lockfile, "w")
            break

        now = int(time.time())
        if now - s[stat.ST_MTIME] > max_wait:
            raise RuntimeError, ("%s has been locked for more than %d seconds (User %s, PID %s)" %
                                 (lockfile, max_wait, fileOwner, pid))

        # it's not been locked too long, wait a while and retry
        #fd.close()
        print >> sys.stderr, "Waiting for %s (User %s, PID %s)" % (lockfile, fileOwner, pid)
        time.sleep(2)

    # if we get here. we have the lockfile. Convert the os.open file
    # descriptor into a Python file object and record our PID, identity, and the usage count in it
    if unlock:
        count -= 1

        if count <= 0:
            try:
                os.unlink(lockfile)
            except OSError, e:
                if e.errno != errno.ENOENT:
                    print >> sys.stderr, "Clearing lockfile %s: %s" % (lockfile, e)

            return
    else:
        count += 1

    f.write("%d\n" % myPid)
    f.write("%s\n" % myIdentity)
    f.write("%d\n" % count)
    f.close()

def unlock(lockfile, force=False):
    if force:
        try:
            os.unlink(lockfile)
        except OSError, e:
            if e.errno != errno.ENOENT:
                print >> sys.stderr, "Clearing lockfile %s: %s" % (lockfile, e)
    else:
        lock(lockfile, "", unlock=True)
