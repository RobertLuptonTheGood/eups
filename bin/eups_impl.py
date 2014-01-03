#!@SYSTEM_PYTHON@
#
# The main eups programme
#
import sys, os, re

sys.argv[0] = "eups"

# try to recover from an incomplete PYTHONPATH
try:
    import eups.cmd
except ImportError:
    eupsdir = None
    if os.environ.has_key("EUPS_DIR"):
        eupsdir = os.environ["EUPS_DIR"]
    else:
        # the first item on sys.path is the script directory (bin)
        eupsdir = os.path.dirname(sys.path[0])
        if not os.path.isabs(eupsdir):
            eupsdir = os.path.join(os.environ['PWD'], eupsdir)
    if eupsdir:
        sys.path[0] = os.path.join(eupsdir, "python")
    else:
        raise

import eups.cmd
import eups.hooks
import eups.utils as utils

# parse the command line
cmd = eups.cmd.EupsCmd()

# set debugging features

import eups.debug
eups.debug.parseDebugOption(cmd.opts.debug)

# load any local customizations
verbosity = cmd.opts.verbose
if cmd.opts.quiet:
    verbosity = -1
eups.hooks.loadCustomization(verbosity, path=eups.Eups.setEupsPath(path=cmd.opts.path, dbz=cmd.opts.dbz))

# run the command
try:
    # N.b. calling sys.exit here raises SystemExit which is caught...
    if eups.Eups.profile:
        try:
            import cProfile as profile
        except ImportError:
            import profile
        profile.run("status = cmd.run()", eups.Eups.profile)
        if verbosity > 0:
            print >> utils.stdinfo, \
                "You can use \"python -m pstats %s\" to examine this profile" % eups.Eups.profile
    else:
        status = cmd.run() 
except Exception, e:
    if eups.Eups.allowRaise:
        raise

    cmd.err(str(e))
    if hasattr(e, "status"):
        status = e.status
    else:
        status = 9

sys.exit(status)
