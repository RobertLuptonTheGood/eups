"""
a module for dealing with an inventory of products in a software stack
which can be cached to disk for fast reloading into memory.  
The major classes are:
   ProductStack    an inventory of all products declared in a single EUPS 
                       database.  Product metadata stored in a instance of 
                       this class can be automatically persisted to disk
                       to speed up recreation of a stack instance later.
   ProductFamily   a collection of different versions of product (installed 
                       for the same flavor).  
"""
from ProductFamily import ProductFamily
from ProductStack import ProductStack
