#!@EUPS_PYTHON@
#
# The EUPS setup programme
#
import sys, os, re
import eups.utils as utils

sys.argv[0] = "eups"

# try to recover from an incomplete PYTHONPATH
try:
    import eups.setupcmd
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
    import eups.setupcmd

from eups.utils import Color
    
# parse the command line
setup = eups.setupcmd.EupsSetup()

# set debugging features

import eups.debug
eups.debug.parseDebugOption(setup.opts.debug)

# load any local customizations
verbosity = setup.opts.verbose
if setup.opts.quiet:
    verbosity = -1
eups.hooks.loadCustomization(verbosity, path=eups.Eups.setEupsPath(dbz=setup.opts.dbz))

# run the command
try:
    # N.b. calling sys.exit here raises SystemExit which is caught...
    if eups.Eups.profile:
        try:
            import cProfile as profile
        except ImportError:
            import profile
        profile.run("status = setup.run()", eups.Eups.profile)
        if verbosity > 0:
            print >> utils.stdinfo, \
                "You can use \"python -m pstats %s\" to examine this profile" % eups.Eups.profile
    else:
        status = setup.run()
except Exception, e:
    if eups.Eups.allowRaise:
        raise

    setup.err(Color(e, Color.classes["ERROR"]))
    if hasattr(e, "status"):
        status = e.status
    else:
        status = 9
    print("false")

sys.exit(status)
