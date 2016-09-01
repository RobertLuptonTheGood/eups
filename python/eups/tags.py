from __future__ import absolute_import, print_function
import fnmatch
import os
import re
from . import hooks, utils
from .exceptions import EupsException

who = utils.getUserName()

tagListFileExt = "tags"
tagListFileTmpl = "%s." + tagListFileExt
tagListFileRe = re.compile(r"^(\w\S*).%s$" % tagListFileExt)
commRe = re.compile(r"\s*#.*$")

class Tags(object):
    """
    a manager of a set of known tag names.  Tags are organized into 
    groups; however, the same name may not be allowed in more than one 
    group.  Three groups are handled by default: global, pseudo, and user.  
    """

    # the group string name indicating the global tag group
    global_ = "_"

    # the group string name indicating the user tag group
    user = "_u"

    # pseudo-tags used by the VRO
    pseudo = "_p"

    def __init__(self, globals=None, groups=[]):

        # a lookup of recognized tag names.  These are separated into groups 
        # of which three are generally used:
        #   "_"    global tags
        #   "_p"   pseudo tags used by the VRO
        #   "_u"   user tags
        self.bygrp = { self.global_: [], self.pseudo: [], self.user: [] }

        self.owners = {}                # owners of the tags (e.g. rhl probably defined the "rhl" tags)

        for group in groups:
            if group not in self.bygrp:
                self.bygrp[group] = []

        if utils.is_string(globals):
            globals = globals.split()
        if globals:
            for tag in globals:
                self.registerTag(tag)

    def __str__(self):
        return "(Tags [%s])" % (" ".join(self.getTagNames()))

    def isRecognized(self, tag):
        """
        return true if given item is recognized as a tag.  It either may 
        be a string or of type Tag.  In either case, the tag must be 
        registered with this Tags instance.

        @param tag :   the item to check.  This can be a string or of 
                         type Tag
        @return bool 
        """
        if utils.is_string(tag) and tag.find(':') >= 0:
            # parse a qualified name
            tag = Tag.parse(tag)
        return (self.groupFor(tag) is not None)

    def groupFor(self, tag):
        """
        return the group that this tag is registered under or None if it 
        is not recognized.  If the input tag is a string, it should be 
        an unqualified tag name.  
        """
        if isinstance(tag, Tag):
            try:
                if tag.name in self.bygrp[tag.group]:
                    return tag.group
            except KeyError:
                pass
        else: 
            for k in self.bygrp.keys():
                if tag in self.bygrp[k]:  
                    return k
        return None

    def getTagNames(self, omitPseudo=False):
        """
        return the qualified names of all registered tags
        """
        out = []
        for t in self.getTags():
            if t.isPseudo() and omitPseudo:
                continue
            out.append(str(t))

        out.sort()
        return out

    def getTags(self):
        """
        return Tag instances for all registered tags
        """
        out = []
        for group in self.bygrp.keys():
            out.extend(self.getTag(x) for x in self.bygrp[group])
        return out

    def getTag(self, tag):
        """
        return a Tag instance for a given tag name or Tag instance.  
        TagNotRecognized is thrown if the name is not registered.

        @param tag :    the name as a string or a Tag instance
        @return Tag : a representation of the tag
        """
        if tag is None:
            return None

        if utils.is_string(tag) and tag != ":" and tag.find(':') >= 0:
            # parse a qualified name
            tag = Tag.parse(tag)
        group = self.groupFor(tag)
        if group is None:
            raise TagNotRecognized(str(tag))

        if isinstance(tag, Tag):
            return tag
        return Tag(tag, group)

    def registerTag(self, name, group=None, force=False):
        """
        register a tag so that it is recognized.  

        @param name :  the name of the tag, or a tuple (tag, user) where user declared tag
        @param group : the class of tag to register it as.  If null, it 
                       will be registered as a global tag.
        @param force : Allows the tag to be redefined, maybe in a different group

        @throws TagNameConflict  if the name has already been registered.
        """
        if isinstance(name, Tag):
            t = name
            group = t.group
            name = t.name

        if group is None:
            group = self.global_

        if utils.is_string(name):
            owner = None
        else:
            name, owner = name
            if owner == who:
                owner = None

        if isinstance(name, list) or isinstance(name, tuple):
            for n in name:
                if owner:
                    n = (n, owner)
                self.registerTag(n, group, force)
            return
        else:
            if set(name).intersection(["*", "?", "[", "]"]):         # a glob
                globPattern = name
                if not owner:
                    raise RuntimeError(\
                        "You can only specify a glob as a tag when reading other user's user tags: %s" % name)

                for n in getUserDefinedTags(owner):
                    if fnmatch.fnmatch(n, globPattern):
                        self.registerTag((n, owner), group, force)
                return

        if re.search(r"^\d+$", name):
            raise RuntimeError("An integer is not a valid tagname")

        if owner and os.path.expanduser("~%s" % owner)[0] == "~":
            raise RuntimeError("User %s is invalid" % owner)

        found = self.groupFor(name)
        if found:
            if found != group and not force:
                raise TagNameConflict(name, found)

            self.bygrp[found].remove(name)
            found = False               # it aint there now

        if not found:
            self.bygrp[group].append(name)
            if owner:
                self.owners[name] = owner
            
    def registerUserTag(self, name, force=False):
        """
        register a user tag.  This is equivalent to 
        registerTag(name, Tags.user).  

        @param string name : the name of the tag
        @throws TagNameConflict  if the name has already been registered.
        """
        return self.registerTag(name, self.user, force)

    # @staticmethod   # requires python 2.4
    def persistFilename(group):
        if group in (Tags.global_, Tags.pseudo):  group = "global"
        if group == Tags.user:     group = "user"
        return tagListFileTmpl % group
    persistFilename = staticmethod(persistFilename) #should work as'f python 2.2

    def load(self, group, file):
        """
        load registered tag names in from a file.

        @param group : the group to load the tags into
        @param file :  the file to load the tags from.  If null, load them 
                          from configured location.
        """

        try:
            fd = open(file)
            if group not in self.bygrp: 
                self.bygrp[group] = []
            for line in fd:
                line.strip()
                line = commRe.sub('', line)
                line = [t for t in line.split() if t not in self.bygrp[group]]
                self.bygrp[group].extend(line)
        finally:
            fd.close()

        return [self.getTag(t) for t in self.bygrp[group]]

    def save(self, group, file):
        """
        save the registered tag names to a cache file.

        @param group : the group to save
        @param file :  the file to save tags to.  If null, use the 
                          configured location. 
        """
        if group not in self.bygrp.keys():
            raise RuntimeError("Group not supported: " + group)

        if not file:
            file = self._persistPath(group)
        try:
            fd = open(file, "w")
            print(" ".join(self.bygrp[group]), file=fd)
        finally:
            try:
                fd.close()
            except:
                pass

    def loadFromEupsPath(self, eupsPath, verbosity=0):
        """
        load tag names of all groups cached in the given eups product 
        stacks.  Return True if tags were found to be loaded.  
        @param eupsPath   the list product root directories (product 
                            stacks) given either as a list of strings 
                            or a single colon-separated string.
        """
        if utils.is_string(eupsPath):
            eupsPath = eupsPath.split(':')
        if not isinstance(eupsPath, list):
            raise TypeError("Tags.loadFromEupsPath(): eupsPath not a str/list:"
                            + str(eupsPath))

        loaded = []
        for dir in eupsPath:
            if not os.path.exists(dir):
                if verbosity > 1:
                    print("%s: EUPS root directory does not exist; skipping..." \
                        % dir, file=utils.stdinfo)
                continue
            if not os.path.isdir(dir):
                if verbosity > 0:
                     "%s: EUPS root directory is not a directory; skipping..." \
                     % dir
                continue

            dbdir = os.path.join(dir, "ups_db")
            if not os.path.exists(dbdir):  dbdir = dir
            for file in os.listdir(dbdir):
                mat = tagListFileRe.match(file)
                if not mat:  continue

                group = mat.group(1)
                file = os.path.join(dbdir, file)
                if group == "user":
                    if verbosity > 0:
                        print("Skipping apparent user tags in EUPS_PATH:", \
                            file, file=utils.stdwarn)
                    continue
                if group == "global":
                    group = self.global_

                if verbosity > 1:
                    print("Reading tags from", file, file=utils.stdinfo)
                try:
                    loaded = self.load(group, file)
                except IOError as e:
                    if verbosity >= 0:
                        print("Skipping troublesome tag file (%s): %s" % \
                            (str(e), file), file=utils.stdwarn)

        return loaded

    def loadUserTags(self, userPersistDir):
        """
        load the user tags whose names are persisted in a given directory.  
        That is, find the user tag file in the given directory and load its 
        contents.
        @param userPersistDir   the directory containing the standard file 
                                   (as given by persistFilename()) 
                                   containing the user tags.
        """
        if not os.path.isdir(userPersistDir):
            raise IOError("Tag cache not an existing directory: " + 
                          userPersistDir)
        fileName = os.path.join(userPersistDir, self.persistFilename("user"))
        if not os.path.exists(fileName):
            # that's okay: no user tags cached
            return False

        self.load(self.user, fileName)
        return True

    def saveGroup(self, group, dir):
        """
        save the user tags cached to a given directory.
        The tag names are assumed to be persisted in 
        Tags.persistFilename(group).
        """
        if group in (self.global_, self.pseudo) :  group = "group"
        if group == self.user:     group = "user"

        if not os.path.isdir(dir):
            raise IOError("Tag cache not an existing directory: " + dir)
        file = os.path.join(dir, self.persistFilename(group))

        if group == "global":
            group = self.global_
        if group == "user":
            group = self.user
        self.save(group, file)

    def saveUserTags(self, userPersistDir):
        """
        save the user tags cached to a given directory.
        The tag names are assumed to be persisted in 
        Tags.persistFilename("user").
        """
        self.saveGroup("user", userPersistDir)
        
    def saveGlobalTags(self, persistDir):
        """
        save global tag names to a  given directory.  The tag names are 
        assumed to be persisted in Tags.persistFilename("global").  The 
        directory can either be a ups_db directory or its parent (as 
        taken from the EUPS_PATH).
        """
        if not os.path.isdir(persistDir):
            raise IOError("Tag cache not an existing directory: " + 
                          persistDir)

        dir = os.path.join(persistDir, "ups_db")
        if os.path.isdir(dir):  persistDir = dir
            
        file = os.path.join(persistDir, self.persistFilename("global"))
        self.save(self.global_, file)
        

class Tag(object):

    """
    a representation of a Tag.  This implementation supports == and != with
    other Tag instances and strings.  When compared with other Tags, they 
    are equal if both the group and name are identical.  It is considered 
    equal to a string if the string is identical to the tag name. 
    """

    def __init__(self, name, group=None):

        if name.startswith("user:"):
            name = name[len("user:"):]
            if not group:
                group = Tags.user

        if not group:
            group = Tags.global_

        # the tag name
        self.name = name

        # the group this tag belongs to (usually global or user).
        self.group = group

    def isUser(self):
        """
        return true if this is a user tag
        """
        return self.group == Tags.user

    def isGlobal(self):
        """
        return true if this is a global tag
        """
        return self.group == Tags.global_

    def isPseudo(self):
        """
        return true if this is a pseudo tag
        """
        return self.group == Tags.pseudo

    def __repr__(self):
        if self.isUser():
            return "User Tag: " + self.name
        elif self.isGlobal():
            return "Global Tag: " + self.name
        else:
            return "Tag: %s:%s" % (self.group, self.name)

    def __str__(self):
        if self.isUser():
            return "user:" + self.name
        elif self.isGlobal() or self.isPseudo():
            return self.name
        else:
            return "%s:%s" % (self.group, self.name)
    
    def __eq__(self, that):
        if isinstance(that, Tag):
            return (self.name == that.name and self.group == that.group)
        else:
            # allow either a qualified string ("user:beta") if the group matches or 
            # an unqualified string ("beta").  
            return str(self) == that or self.name == that

    def __ne__(self, that):
        return not (self == that)

    # @staticmethod   # requires python 2.4
    def parse(name, defGroup=Tags.global_):
        """
        create a Tag instance from a fully specified tag name string.
        
        A substring prior to a colon is assumed to be the group name.  If
        there is not group name, it is assumed to be of the group given by
        defGroup (which defaults to global).  
        """
        # This is requires python 2.4
        #   parts = name.rsplit(':', 1)
        # replaced with:
        parts = name.split(':')
        if len(parts) > 2:
            try:
                parts = ":".join(parts[:-1], parts[-1])
            except Exception as e:
                import eups; eups.debug(e)

        if len(parts) == 1:
            return Tag(name, defGroup)
        else:
            if parts[0] == "user":
                parts[0] = Tags.user
            elif parts[0] == "" or parts[0] == "global":
                parts[0] = Tags.global_
            elif parts[0] == "tag":
                return Tag(parts[1])    # unknown tag, probably from a version name

            return Tag(parts[1], parts[0])
    parse = staticmethod(parse) #should work as of python 2.2

def UserTag(name):
    """
    Instantiate a user-defined tag.  This a Tag with the group equal to 
    Tags.user.  
    """
    return Tag.parse(name, Tags.user)


def GlobalTag(name):
    """
    Instantiate a global tag.  This a Tag with the group equal to 
    Tags.global_.  
    """
    return Tag.parse(name, Tags.global_)


class TagNotRecognized(EupsException):
    """
    an exception indicating the use of an unregistered tag.
    """

    def __init__(self, name, group=None, msg=None):
        message = msg
        if message is None:
            if group == Tags.user:
                message = "User tag not recognized: " + name
            elif group == Tags.global_:
                message = "Global tag not recognized: " + name
            elif group is None:
                message = "Tag not recognized: " + name
            else:
                message = "Tag not recognized: %s:%s" % (group, name)
        EupsException.__init__(self, message)
        self.name = name,
        self.group = group

class TagNameConflict(EupsException):
    """
    an exception indicating that a tagname has already been registered.
    """

    def __init__(self, name, found):
        if found == Tags.global_:
            found = "global"
        elif found == Tags.user:
            found = "user"
        else:
            found = "??? (%s)" % found

        EupsException.__init__(self, "Tag \"%s\" is already present in group %s" % (name, found))
        self.name = name,
        self.found = found
            
def checkTagsList(eupsenv, tagList):
    """Check that all tags in list are valid"""
    badtags = [t for t in tagList if not eupsenv.tags.isRecognized(t)]

    for tag in badtags[:]:
        fileName = re.sub(r"^file:", "", tag)
        if os.path.isfile(os.path.expanduser(fileName)):
            if eupsenv.verbose > 1:
                print("File %s defines a tag" % fileName, file=utils.stdinfo)
            badtags.remove(tag)
            
    if badtags:
        raise TagNotRecognized(str(badtags), 
                               msg="Unsupported tag(s): %s" % ", ".join([str(t) for t in badtags]))

def getUserDefinedTags(user):
    """Return all the tags that a given user defines

    N.b. we do this by executing their startup file in a new context
    """
    startupFile = os.path.join(utils.defaultUserDataDir(user), hooks.config.Eups.startupFileName)

    myGlobals, myLocals = {}, {}

    class Foo(list):                    # a place to put attributes
        def __getattr__(self, attr): return self
        
    myGlobals["hooks"] = Foo()
    myGlobals["hooks"].config = Foo()
    myGlobals["hooks"].config.distrib = dict(builder = dict(variables = {}))
    myEups = Foo()
    myGlobals["hooks"].config.Eups = myEups
    myGlobals["eups"] = Foo()
    #
    # Define lists that might be appended to
    #
    for c in [c for c in dir(globals()["hooks"].config.Eups) if not re.search("^_", c)]:
        setattr(myEups, c, [])

    try:
        exec(compile(open(startupFile).read(), startupFile, 'exec'), myGlobals, myLocals)
    except Exception as e:
        print("Error processing %s's startup file: %s" % (user, e), file=utils.stderr)
        return []

    theirTags = []
    for tag in myEups.userTags:
        try:
            name, owner = tag
            continue
        except ValueError:
            pass

        theirTags.append(tag)

    return theirTags

def cloneTag(eupsenv, newTag, oldTag, productList=[]):
    checkTagsList(eupsenv, [newTag, oldTag])

    productsToTag = productList          # may be []
    failedToTag = []                      # products we failed to tag
    for p in eupsenv.findProducts(tags=[oldTag]):
        if productList and p.name not in productList:
            continue

        try:
            eupsenv.declare(p.name, p.version, tag=newTag)
        except EupsException as e:
            print(e, file=utils.stderr)
            failedToTag.append(p.name)

    return failedToTag

def deleteTag(eupsenv, tag):
    checkTagsList(eupsenv, [tag])

    for p in eupsenv.findProducts(tags=[tag]):
        if eupsenv.verbose:
            print("Untagging %-40s %s" % (p.name, p.version), file=utils.stdinfo)
        eupsenv.undeclare(p.name, p.version, tag=tag)

__all__ = "Tags Tag TagNotRecognized TagNameConflict cloneTag deleteTag".split()

