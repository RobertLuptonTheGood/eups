#  An example EUPS startup file -- a file containing executable python code
#  meant to customize the behavior of EUPS.  
#
#  This file can contain arbitrary python code, including import statements;
#  however, a few things have been imported for you already:
#  
#     eups  --  the eups module which contains access to the main application
#                 level interface
#     hooks --  a special EUPS module containing items specifically of 
#                 interest in customizing EUPS behavior which is described 
#                 below.
#     VersionCompare -- a parent function class used for defining your own
#                 version compare function (or tweaking the default one).  
#
#  This sample file shows 3 basic types of customizations:
#    1. Configuration Properties
#    2. Version Comparison
#    3. Fallback Flavors
#

#  1.  Configuration Properties
#
#  Configuration properties can be manipulated here (and override any values 
#  set in a properties file; see etc/config.properties).  Here's how you do 
#  simple property setting:

# Eups.userTags:  the list of user-defined tags as a space-delimited list
#
hooks.config.Eups.userTags = "mine exp"

# Eups.preferredTags:  the ordered list of preferred tags.  When eups setup
# needs to choose between several versions of a package, it will choose the 
# first version tagged with name taken from this list.  
hooks.config.Eups.preferredTags = "stable beta current newest"

# Eups.setupTypes:  the list of setup types supported by table files.  
#
# By default, EUPS recognizes one setup type, "build".  This allows table
# files to say, "if (setup == build) {".  
#
# hooks.config.Eups.setupTypes = "build"

# Eups.verbose:  the minimum verbosity level given as an integer
#
hooks.config.Eups.verbose = 0 

# Eups.asAdmin:  assume user is an administrator of the writable directories
# in the EUPS path; allowing those databases to cached, directly.  If False,
# this will not override this on the command-line
hooks.config.Eups.asAdmin = None

# A few other sets of configuration properties are defined that the top level:
#
#    Eups      -- properties that configure the main EUPS operations
#    distrib   -- properties that configure particular distrib types
#    site      -- site-level properties
#    user      -- user-level properties
#
# The distrib property (i.e. hooks.config.distrib) has a python dictionary 
# as a value.  The keys should be the names of Distrib handlers.  The site
# and user properties start off empty.  To define properties for one of these
# top levels, use the hooks.defineProperties() method:
#
#    hooks.config.site = hooks.defineProperties("foo bar", "site")
#
# This defined hooks.config.site.foo and hooks.config.site.foo.  Once defined,
# these parameters can be accessed or updated by any other configuration 
# properties file or start-up file loaded after this; however, once defined
# it cannot be redefined or others added on.  To enforce a particular typed
# value for a property, use the setType() method on the parameter's parent 
# property:
#
#    hooks.config.site.setType("foo", int)
#
# This enforces an integer type.  If this property is set with a string 
# value, it will be converted to the configured top.

# 2. Version Comparison
# 
# Version comparisons.  A new or modified version comparison function can 
# be plugged in by setting hooks.version_cmp to a compare function that 
# expects 2 version strings to be compared.  When tweakng, it is usually 
# easier to create a subclass of the VersionCompare function class and set
# hooks.version_cmp to an instance of that subclass.  See VersionCompare 
# help for more info.  
#
# For example:
#
#   class MyVersionCompare(VersionCompare):
#       def compare(self, v1, v2):
#           ...
#
#   hooks.version_cmp = MyVersionCompare()
# 

# 3. Fallback Flavors
#
# You can set "fallback" flavors with hooks.setFallbackFlavors().  "Fallback"
# flavors are flavors of products you can use if a product of the actual
# native platform flavor cannot be found.  Each flavor, can have its own 
# set of backups.  By default, all flavors have "generic" as a backup.  
#
# hooks.setFallbackFlavors("Darwin", ["DarwinX86", "generic"])

