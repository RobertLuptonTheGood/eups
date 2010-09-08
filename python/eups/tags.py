import os, pwd, re, sys
import lock
from exceptions import EupsException

who = pwd.getpwuid(os.geteuid())[0]

tagListFileExt = "tags"
tagListFileTmpl = "%s." + tagListFileExt
tagListFileRe = re.compile(r"^(\w\S*).%s$" % tagListFileExt)
commRe = re.compile(r"\s*#.*$")

class Tags(object):
    """
    a manager of a set of known tag names.  Tags are organized into 
    groups; however, the same name may not be allowed in more than one 
    group.  Two groups are handled by default: global and user.  

    @author  Raymond Plante
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

        for group in groups:
            if not self.bygrp.has_key(group):
                self.bygrp[group] = []

        if isinstance(globals, str):
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
        if isinstance(tag, str) and tag.find(':') >= 0:
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
            out.extend(map(lambda x: self.getTag(x), self.bygrp[group]))
        return out

    def getTag(self, tag):
        """
        return a Tag instance for a given tag name or Tag instance.  
        TagNotRecognized is thrown if the name is not registered.

        @param tag :    the name as a string or a Tag instance
        @return Tag : a representation of the tag
        """
        if isinstance(tag, str) and tag.find(':') >= 0:
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

        @param name :  the name of the tag
        @param group : the class of tag to register it as.  If null, it 
                       will be registered as a global tag.
        @param force : Allows the tag to be redefined, maybe in a different group

        @throws TagNameConflict  if the name has already been registered.
        """
        if group is None:
            group = self.global_

        if isinstance(name, Tag):
            name = name.name

        found = self.groupFor(name)
        if found:
            if found != group and not force:
                raise TagNameConflict(name, found)

            self.bygrp[found].remove(name)
            found = False               # it aint there now

        if not found:
            self.bygrp[group].append(name)

    def registerUserTag(self, name, force=False):
        """
        register a user tag.  This is equivalent to 
        registerTag(name, Tags.user).  

        @param string name : the name of the tag
        @throws TagNameConflict  if the name has already been registered.
        """
        return self.registerTag(name, self.user, force)

    def _lockfilepath(self, file):
        return file + ".lock"

    def _lock(self, file):
        lock.lock(self._lockfilepath(file), who)

    def _unlock(self, file):
        lock.unlock(self._lockfilepath(file), who)

    # @staticmethod   # requires python 2.4
    def persistFilename(group):
        if group in (Tags.global_, Tags.pseudo):  group = "global"
        if group == Tags.user:     group = "user"
        return tagListFileTmpl % group
    persistFilename = staticmethod(persistFilename) #should work as'f python 2.2

    def load(self, group, file, lock=True):
        """
        load registered tag names in from a file.

        @param group : the group to load the tags into
        @param file :  the file to load the tags from.  If null, load them 
                          from configured location.
        @param lock :  file must be locked before being read
        """

        if lock:
            self._lock(file)

        try:
            fd = open(file)
            if not self.bygrp.has_key(group): 
                self.bygrp[group] = []
            for line in fd:
                line.strip()
                line = commRe.sub('', line)
                line = filter(lambda t: t not in self.bygrp[group], 
                              line.split())
                self.bygrp[group].extend(line)
            fd.close()
        finally:
            if lock:
                self._unlock(file)

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
        self._lock(file)
        try:
            fd = open(file, "w")
            print >> fd, " ".join(self.bygrp[group])
            fd.close()
        finally:
            self._unlock(file)


    def loadFromEupsPath(self, eupsPath, verbosity=0):
        """
        load tag names of all groups cached in the given eups product 
        stacks.  Return True if tags were found to be loaded.  
        @param eupsPath   the list product root directories (product 
                            stacks) given either as a list of strings 
                            or a single colon-delimited string.
        """
        if isinstance(eupsPath, str):
            eupsPath = eupsPath.split(':')
        if not isinstance(eupsPath, list):
            raise TypeError("Tags.loadFromEupsPath(): eupsPath not a str/list:"
                            + str(eupsPath))

        loaded = False
        for dir in eupsPath:
            if not os.path.exists(dir):
                if verbosity > 1:
                    print >> sys.stderr, \
                        "%s: EUPS root directory does not exist; skipping..." \
                        % dir
                continue
            if not os.path.isdir(dir):
                if versbose > 0:
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
                        print >> sys.stderr, \
                            "Skipping apparent user tags in EUPS_PATH:", \
                            file
                    continue
                if group == "global":
                    group = self.global_

                if verbosity > 1:
                    print >> sys.stderr, "Reading tags from", file
                try:
                    try:
                        self.load(group, file)
                    except OSError, e:
                        if verbosity > 1:
                            print >> sys.stderr, ("Unable to lock %s; reading anyway" % file)
                        self.load(group, file, lock=False)
                    loaded = True
                except IOError, e:
                    if verbosity >= 0:
                        print >> sys.stderr, \
                            "Skipping troublesome tag file (%s): %s" % \
                            (str(e), file)

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
        file = os.path.join(userPersistDir, self.persistFilename("user"))
        if not os.path.exists(file):
            # that's okay: no user tags cached
            return False

        self.load(self.user, file)
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
        assumed to be persisted in Tags.persistFilename("user").  The 
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
        import hooks
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

    def equals(self, that):
        """
        return true if the given tag is the same as this tag.  The given 
        tag can be either another Tag instance or a string.  This is 
        equivalent to (self == that).  Two Tag instances are equal if both 
        their group and name attributes are equal.  A string will be equal
        to this Tag if it is equal to this Tag's name.  
        """
        return self.__cmp__(that)

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
            except Exception, e:
                import eups; eups.debug(e)

        if len(parts) == 1:
            return Tag(name, defGroup)
        else:
            if parts[0] == "user":
                parts[0] = Tags.user
            elif parts[0] == "" or parts[0] == "global":
                parts[0] = Tags.global_
            return Tag(parts[1], parts[0])
    parse = staticmethod(parse) #should work as'f python 2.2

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
    badtags = filter(lambda t: not eupsenv.tags.isRecognized(t), tagList)

    for tag in badtags:
        if os.path.isfile(tag):
            if eupsenv.verbose > 1:
                print >> sys.stderr, "File %s defines a tag" % tag
            badtags.remove(tag)
            
    if badtags:
        raise TagNotRecognized(str(badtags), 
                               msg="Unsupported tag(s): %s" % ", ".join(map(lambda t: str(t), badtags)))

__all__ = "Tags Tag TagNotRecognized TagNameConflict".split()

