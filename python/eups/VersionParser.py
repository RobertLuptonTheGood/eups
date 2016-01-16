"""A simple recursive descent parser for logical expressions"""

import os
import re

class VersionParser(object):
    """Evaluate a logical expression, returning a Bool.  The grammar is:

        expr : term
               expr || term          (or  is also accepted)
               expr && term          (and is also accepted)

        term : prim == prim
               prim =~ regexp
               prim != prim
               prim !~ regexp
               prim < prim
               prim <= prim
               prim > prim
               prim >= prim

	prim : int
               string
               name
               ( expr )

names are declared using VersionParser.define()
        """
    def __init__(self, exprStr):
        exprStr = re.sub(r"['\"]([^'\"]+)['\"]", r"\1", exprStr)
        self._tokens = re.split(r"(\$\??{[^}]+}|[\w.+]+|\s+|==|!=|<=|>=|[()<>])", exprStr)
        self._tokens = filter(lambda p: p and not re.search(r"^\s*$", p), self._tokens)
        
        self._symbols = {}
        self._caseSensitive = False

    def define(self, key, value):
        """Define a symbol, which may be substituted using _lookup"""
        
        self._symbols[key] = value

    def _lookup(self, key):
        """Attempt to lookup a key in the symbol table"""
        key0 = key
        
        try:
            envVar, modifier, value = re.search(r"^\${([^:}]*)(:-([^\}*]*))?}", key).groups()

            if not value or value == "false":
                value = False

            if envVar in os.environ:
                return os.environ[envVar]
            elif modifier:
                return value
            else:
                raise RuntimeError("Environment variable $%s is not defined" % envVar)
        except TypeError:
            pass
        except AttributeError:
            pass

        if not self._caseSensitive:
            key = key.lower()

        try:
            return self._symbols[key]
        except KeyError:
            return key0        

    def _peek(self):
        """Return the next terminal symbol, but don't pop it off the lookahead stack"""
        
        if not self._tokens:
            return "EOF"

        tok = self._lookup(self._tokens[0])

        try:                            # maybe it's an int
            tok = int(tok)
        except TypeError:
            pass
        except ValueError:
            pass

        if tok == "True" or tok == "False": # or a bool
            tok = (tok == "True")

        return tok

    def _push(self, tok):
        """Push a token back onto the lookahead stack"""

        if tok != "EOF":
            self._tokens = [tok] + self._tokens
    
    def _next(self):
        """Return the next terminal symbol, popping it off the lookahead stack"""
        
        tok = self._peek()
        if tok != "EOF":
            self._tokens.pop(0)

        return tok
    
    def eval(self):
        """Evaluate the logical expression, returning a Bool"""

        if isinstance(self._tokens, bool):
            return self._tokens

        val = self._expr()              # n.b. may not have consumed all tokens as || and && short circuit

        if val == "EOF":
            return False
        else:
            return val

    def _expr(self):
        lhs = self._term()

        while True:
            op = self._next()

            if op == "||" or op == "or":
                lhs = lhs or self._term()
            elif op == "&&" or op == "and":
                lhs = lhs and self._term()
            else:
                self._push(op)
                return lhs

    def _term(self):
        lhs = self._prim()
        op = self._next()

        if op == "EOF":
            return lhs

        if op == "==":
            if isinstance(lhs, list):
                return self._prim() in lhs
            else:
                return lhs == self._prim()
        elif op == "=~":
            return re.search(self._prim(), lhs)
        elif op == "!=":
            if isinstance(lhs, list):
                return not (self._prim() in lhs)
            else:
                return lhs != self._prim()
        elif op == "!~":
            return not re.search(self._prim(), lhs)
        elif op == "<":
            return lhs < self._prim()
        elif op == "<=":
            return lhs <= self._prim()
        elif op == ">":
            return lhs > self._prim()
        elif op == ">=":
            return lhs >= self._prim()
        else:
            self._push(op)
            return lhs

    def _prim(self):
        next = self._peek()

        if next == "(" or (next == "!" or next == "not"):
            self._next()

            term = self._expr()
            
            if next == "!" or next == "not":
                term = not term
            elif next == "(":
                next = self._next()
                if next != ")":
                    raise RuntimeError("Saw next = \"%s\" in prim" % next)

            return term

        return self._next()
