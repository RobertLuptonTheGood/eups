""" Configure eups for LSST """

import os, re, sys
import pdb
import eups
import eupsDistribBuilder
try:
    import lsst.svn
except ImportError:
    print >> sys.stderr, "Unable to import lsst.svn --- maybe scons isn't setup?"

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
#
# Allow "eups fetch" as an alias for "eups distrib install"
#
def eupsCmdHook(cmd, argv):
    """Called by eups to allow users to customize behaviour by defining it in EUPS_STARTUP

    The arguments are the command (e.g. "admin" if you type "eups admin")
    and sys.argv, which you may modify;  cmd == argv[1] if len(argv) > 1 else None
    """

    if cmd == "fetch":
        argv[1:2] = ["distrib", "install"]

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

def rewriteTicketVersion(line):
    """A callback that knows about the LSST concention that a tagname such as
       ticket_374
   means the top of ticket 374, and
      ticket_374+svn6021
   means revision 6021 on ticket 374"""
    #
    # Look for a tagname that we recognise as having special significance
    #
    try:
        mat = re.search(r"^\s*svn\s+(?:co|checkout)\s+([^\s]+)", line)
        if mat:
            URL = mat.group(1)

            if re.search(r"^([^\s]+)/trunk$", URL): # already processed
                return line

            try:
                type, which, revision = lsst.svn.parseVersionName(URL)

                rewrite = None
                if type == "branch":
                    rewrite = "/branches/%s" % which
                elif type == "ticket":
                    rewrite = "/tickets/%s" % which

                if rewrite is None:
                    raise RuntimeError, ""

                if revision:
                    rewrite += " -r %s" % revision

                line = re.sub(r"/tags/([^/\s]+)", rewrite, line)
            except RuntimeError, e:
                raise RuntimeError, ("rewriteTicketVersion: invalid version specification \"%s\" in %s: %s" % \
                                     (URL, line[:-1], e))

    except AttributeError, e:
        print >> sys.stderr, "Your version of sconsUtils is too old to support parsing version names"
    
    return line

if __name__ == "__main__":

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
    #
    # Define a distribution type "preferred"
    #
    eups.defineValidTags("preferred")

    if False:
        eups.defineValidSetupTypes("build") # this one's defined already
    #
    # Rewrite ticket names into proper svn urls
    #
    eupsDistribBuilder.buildfilePatchCallbacks.add(rewriteTicketVersion)

#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-

import eups
import eupsServer

class ExtendibleConfigurableDistribServer(eupsServer.ConfigurableDistribServer):
    """A version of ConfigurableDistribServer that we could augment
    """

    def __init__(self, *args):
        super(eupsServer.ConfigurableDistribServer, self).__init__(*args)
