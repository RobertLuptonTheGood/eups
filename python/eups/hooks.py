"""
Module that enables user configuration and hooks.  
"""
import os, sys, re
import utils
import eups
import eups.exceptions
from VersionCompare import VersionCompare

# the function to use to compare two version.  The user may reset this 
# to provide a different algorithm.
version_cmp = VersionCompare()

# a function for setting fallback flavors.  This function is callable by 
# the user.  
setFallbackFlavors = utils.Flavor().setFallbackFlavors

# See after this function for the default definitions of properties

def defineProperties(names, parentName=None):
    """
    return a ConfigProperties instance defined with the given names.
    @param  names       the names of the properties to define, given as a 
                          space-delimited string or as a list of strings.  
    @param  parentName  the fully-qualified name of the parent property.  
                          Provide this if this is defining a non-top-level
                          property.  
    """
    if isinstance(names, str):
        names = names.split()
    return utils.ConfigProperty(names, parentName)

# various configuration properties settable by the user
config = defineProperties("Eups distrib site user")
config.Eups = defineProperties("userTags preferredTags verbose asAdmin setupTypes setupCmdName", "Eups")
config.Eups.setType("verbose", int)

config.Eups.userTags = ""
config.Eups.preferredTags = "current stable newest"
config.Eups.verbose = 0
config.Eups.asAdmin = None
config.Eups.setupTypes = "build"
config.Eups.setupCmdName = "setup"

# it is expected that different Distrib classes will have different set-able
# properties.  The key for looking up Distrib-specific data could the Distrib
# name.  
config.distrib = {}

    
startupFileName = "startup.py"
configFileName = "config.properties"

def loadCustomizationFromDir(customDir, verbose=0, log=sys.stderr, execute=False):
    cfile = os.path.join(customDir, configFileName)
    if os.path.exists(cfile):
        if verbose > 0:
            print >> log, "loading properties from", cfile
        loadConfigProperties(cfile, verbose, log)

    startup = os.path.join(customDir, startupFileName) 
    if os.path.exists(startup):
        if execute:
            execute_file(startup)

        return startup

    return None

def loadCustomization(verbose=0, log=sys.stderr, execute=True, quiet=True):
    """
    load all site and/or user customizations.  Customizations can come in two
    forms: a configuration properties file and/or a startup script file.  
    Any customizations that appears in a startup script file will override
    those found in the properties file.

    This function looks for customizations first in a site directory.  By 
    default this is $EUPS_DIR/site; however, it can be overridden with the 
    $EUPS_SITEDATA.  Next it looks for customizations in a user directory
    with is $HOME/.eups by default but can be overridden with $EUPS_USERDATA.
    In each of these directories, a properties file, called "config.properties"
    is searched for and loaded, then a startup script, called, "startup.py"
    is searched for and loaded (possibly over-ridding properties).  

    Finally, additional startup scripts can be run if $EUPS_STARTUP.  This 
    environment variable contains a colon-delimited list of script file.  Each
    is executed in order.  

    @param verbose    the verbosity level
    @param log        where to write log messages
    @param execute    process files?
    """
    customDirs = []

    # a site-leve directory can have configuration stuff in it
    if os.environ.has_key("EUPS_SITEDATA"):
        customDirs.append(os.environ["EUPS_SITEDATA"])
    elif os.environ.has_key("EUPS_DIR"):
        customDirs.append(os.path.join(os.environ["EUPS_DIR"], "site"))

    # $HOME/.eups can have user configuration stuff in it
    if os.environ.has_key("EUPS_USERDATA"):
        customDirs.append(os.environ["EUPS_USERDATA"])
    elif os.environ.has_key("HOME"):
        customDirs.append(os.path.join(os.environ["HOME"], ".eups"))

    # load the configuration by directories; later ones override prior ones
    customisationFiles = []             # files that we'd load

    for dir in customDirs:
        cfile = loadCustomizationFromDir(dir, verbose, log, execute=execute)
        if cfile:
            customisationFiles.append(cfile)

    # load any custom startup scripts via EUPS_STARTUP; this overrides
    # everything
    if os.environ.has_key("EUPS_STARTUP"):
        for startupFile in os.environ["EUPS_STARTUP"].split(':'):
            if not os.path.exists(startupFile):
                if not quiet:
                    print "Startup file %s doesn't exist" % (startupFile)
            else:
                try:
                    if execute: 
                        execute_file(startupFile)

                    customisationFiles.append(startupFile)
                except Exception, e:
                    msg = "Processing %s: %s" % (startupFile, e)
                    if False:           # we have no recourse if we break this file; so proceed
                        raise eups.exceptions.CustomizationError(msg)
                    else:
                        print >> log, msg

    return customisationFiles

def execute_file(file):
    import eups
    from eups import hooks
    from VersionCompare import VersionCompare    

    _globals = {}
    for key in filter(lambda k: k.startswith('__'), globals().keys()):
        _globals[key] = globals()[key]
    del key
        
    execfile(file, _globals, locals())



commre = re.compile(r'#.*$')
namevalre = re.compile(r'[:=]')
def loadConfigProperties(configFile, verbose=0, log=sys.stderr):
    maxerr = 5
    if not os.path.exists(configFile):
        return

    fd = open(configFile)
    lineno = 0
    try: 
        for line in fd:
            lineno += 1
            line = commre.sub('', line).strip()
            if not line:
                continue
            parts = namevalre.split(line, 1)
            if len(parts) != 2:
                if verbose >= 0 and maxerr > 0:
                    print >> log, "Bad property syntax (ignoring):", line
                    maxerr -= 1
                continue
            name, val = parts

            # turn property name into an attribute of hooks.config
            parts = name.split('.')
            attr = config
            while len(parts) > 1:
                nxt = parts.pop(0)
                if not hasattr(attr, nxt):
                    if verbose >= 0:
                      print >> log, "Ignoring unrecognized property:", name
                    break
                attr = getattr(attr, nxt)

            try:
                setattr(attr, parts[0], val)
            except AttributeError, e:
                if verbose >= 0:
                   print >> log, "Skipping bad property assignment:", str(e)

    finally:
        fd.close()
