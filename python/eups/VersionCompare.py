import re

class VersionCompare(object):
    """
    A comparison function class that compares two product versions.
    """
    def compare(self, v1, v2, mustReturnInt=True):
        """Compare two versions.

If mustReturnInt is True, return value must be acceptable to sort(), i.e. an int

If mustReturnInt is False and you don't want to allow the versions to be sorted, throw ValueError
        """
        return self.stdCompare(v1, v2, mustReturnInt=mustReturnInt)

    def stdCompare(self, v1, v2, suffix=True, mustReturnInt=True):
        prim1, sec1, ter1 = self._splitVersion(v1)
        prim2, sec2, ter2 = self._splitVersion(v2)

        if prim1 == prim2:
            # the same primary release component 
            if sec1 or sec2 or ter1 or ter2:
                if sec1 or sec2:
                    if (sec1 and sec2):
                        ret = self.stdCompare(sec1, sec2, True)
                    else:
                        if sec1:
                            return -1
                        else:
                            return 1

                    if ret == 0:
                        return self.stdCompare(ter1, ter2, True)
                    else:
                        return ret

                return self.stdCompare(ter1, ter2, True)
            else:
                return 0

        c1 = re.split(r"[._]", prim1)
        c2 = re.split(r"[._]", prim2)
        #
        # Check that leading non-numerical parts agree
        #
        if not suffix:
            prefix1, prefix2 = "", ""
            mat = re.search(r"^([^0-9]+)", c1[0])
            if mat:
                prefix1 = mat.group(1)

            mat = re.search(r"^([^0-9]+)", c2[0])
            if mat:
                prefix2 = mat.group(1)

            # look for a common prefix.  If there is no common prefix,
            # the one with the longer non-numeric prefix comes first.
            if len(prefix1) > len(prefix2): # take shorter prefix
                prefix = prefix2
                if not re.search(r"^%s" % prefix, c1[0]):
                    return +1
            else:
                prefix = prefix1
                if not re.search(r"^%s" % prefix1, c2[0]):
                    return -1

            # remove the common prefix
            c1[0] = re.sub(r"^%s" % prefix, "", c1[0])
            c2[0] = re.sub(r"^%s" % prefix, "", c2[0])

        n1 = len(c1); n2 = len(c2)
        if n1 < n2:
            n = n1
        else:
            n = n2

        for i in range(n):
            c12AreIntegral = False      # are c1[i] and c2[i] integers?
            try:                        # try to compare as integers, having stripped a common prefix
                _c2i = None             # used in test for a successfully removing a common prefix

                mat = re.search(r"^([^\d]+)\d+$", c1[i])
                if mat:
                    prefixi = mat.group(1)
                    if re.search(r"^%s\d+$" % prefixi, c2[i]):
                        _c1i = int(c1[i][len(prefixi):])
                        _c2i = int(c2[i][len(prefixi):])

                if _c2i is None:
                    _c1i = int(c1[i])
                    _c2i = int(c2[i])

                c1[i] = _c1i
                c2[i] = _c2i
                c12AreIntegral = True
            except ValueError:
                pass

            different = cmp(c1[i], c2[i])
            if different:
                if mustReturnInt or c12AreIntegral:
                    return different
                else:
                    raise ValueError("Versions %s and %s cannot be sorted" % (v1, v2))

        # So far, the two versions are identical.  The longer version should sort later
        return cmp(n1, n2)

    def _splitVersion(self, version):
        """
        Break a version string down into its 3 main components: 
          o  a base release name (e.g. 1.2.3),
          o  an optional decrementing annotation (e.g. -2)
          o  an optional incrementing annotation (e.g. +svn1039)
        """
        if not version:
            return "", "", ""

        if len(version.split("-")) > 2: 
            # a version string such as rel-0-8-2 with more than one hyphen
            return version, "", ""

        mat = re.search(r"^([^-+]+)((-)([^-+]+))?((\+)([^-+]+))?", version)
        vvv, eee, fff = mat.group(1), mat.group(4), mat.group(7)

        if not eee and not fff:             # maybe they used VVVm# or VVVp#?
            mat = re.search(r"(m(\d+)|p(\d+))$", version)
            if mat:
                suffix, eee, fff = mat.group(1), mat.group(2), mat.group(3)
                vvv = re.sub(r"%s$" % suffix, "", version)

        return vvv, eee, fff

    def __call__(self, v1, v2, mustReturnInt=True):
        """
        make an instance behave like a callable function
        """
        return self.compare(v1, v2, mustReturnInt)

