#!/usr/bin/perl
# Parser for evilups table files
# Nikhil Padmanabhan, Princeton
#
#
# Jan 22, 2002
#EvilUPS : A Unix Versioning System
#Copyright (C) 2003 Nikhil Padmanabhan

#    This program is free software; you can redistribute it and/or
#modify it under the terms of the GNU General Public License
#    as published by the Free Software Foundation; either version 2
#of the License, or (at your option) any later version.

#This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

############################

package eups_setup;
require Exporter;

our @ISA = qw(Exporter);
our @EXPORT = qw(eups_unsetup eups_setup);
our $VERSION = 1.1;

#Subroutines follow

sub fix_special {
# This is essential since some of the flavors have special characters in 
# them.
    my $arg = $_[0];
    $arg =~ s/\\/\\\\/g;
    $arg =~ s/\./\\\./g;
    $arg =~ s/\+/\\\+/g;
    $arg =~ s/\(/\\\(/g;
    $arg =~ s/\)/\\\)/g;
    $arg =~ s/\{/\\\{/g;
    $arg =~ s/\}/\\\}/g;
    $arg =~ s/\^/\\\^/g;
    $arg =~ s/\*/\\\*/g;
    $arg =~ s/\?/\\\?/g;
    $arg =~ s/\[/\\\[/g;
    $arg =~ s/\|/\\\|/g;
    return $arg;
}

sub envInterpolate {
# Interpolates in values of environment variables
    my $in = $_[0];
    my @env_var = $in =~ m/\$\{(.+?)\}/g;
    for (my $i = 0; $i < @env_var; $i++) {
	my $val = $ENV{$env_var[$i]};
	$in =~ s/\$\{.+?\}/$val/g;
    }
    return $in;
}

sub cleanArg {
# Cleans out quotes and leading spaces
    my $pval = $_[0];
# $pval might have leading spaces - remove these
    my ($val) = $pval =~ m/ *([^ ].*)/;
# Maybe $val is quoted
    if ($val =~ m/".*"/) {
        ($pval) = $val =~ m/"(.*)"/;
        $val = $pval;
    }
    return $val;
}

sub addAlias {
    use File::Basename;
    our $outfile;
    my $shell = basename($ENV{"SHELL"});
    $shell = "sh" if ($shell eq "bash");
    $shell = "csh" if ($shell eq "tcsh");
    my $name = $_[0];
    my $value = $_[1];
    if ($shell eq "csh") { 
	print $outfile "alias $name \"$value\"\n";
    }
    if ($shell eq "sh") {
	print $outfile "function $name \{ $value \; \} \n";
    }
}

sub unAlias {
    use File::Basename;
    our $outfile;
    my $shell = basename($ENV{"SHELL"});
    $shell = "sh" if ($shell eq "bash");
    $shell = "csh" if ($shell eq "tcsh");
    my $name = $_[0];
    if ($shell eq "csh") {
        print $outfile "unalias $name\n";
    }
    if ($shell eq "sh") {
        print $outfile "unfunction $name\n";
    }
}


sub envAppend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");
    $curval = $ENV{$var};
    $curval = "$curval$delim$val";
    $ENV{$var} = envInterpolate($curval);
}

sub envPrepend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");
    $curval = $ENV{$var};
    $curval = "$val$delim$curval";
    $ENV{$var} = envInterpolate($curval);
}

sub envSet {
    my $var = $_[0];
    my $val = cleanArg($_[1]);

    $ENV{$var} = envInterpolate($val);
}

sub envRemove {
    my $var = $_[0];
    my $pval = $_[1];
    $pval = envInterpolate($pval);
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    my $sval = fix_special($val);
    $delim = ":" if ($delim eq "");
    my $sdelim = fix_special($delim);
    $curval = $ENV{$var};
    $curval =~ s/$sval//;
    $curval =~ s/$sdelim$sdelim/$sdelim/;
    $curval =~ s/^$sdelim//;
    $curval =~ s/$sdelim$//;
    $ENV{$var} = $curval;
}

sub envUnset {
    our $outfile;
    my $var = $_[0];
    delete $ENV{$var};
}

sub parse_table {
    my $fn = $_[0];
    my $proddir = $_[1];
    my $upsdir = $_[2];
    my $prod = $_[3];
    my $vers = $_[4];
    my $flavor = $_[5];
    my $db = $_[6];
    my $fwd = $_[7];
    our $outfile = $_[8];
    my $data = 0;

# Define the return value
    my $retval = 0;

# Define the command hashes

%switchback = (
addalias => \&unAlias,
envappend => \&envRemove,
envprepend => \&envRemove,
envremove => \&envAppend,
envset => \&envUnset,
envunset => \&envSet,
pathappend => \&envRemove,
pathprepend => \&envRemove,
pathremove => \&envAppend,
proddir => \&envUnset,
setupenv => \&envUnset,
	       );

%switchfwd = (
addalias => \&addAlias,
envappend => \&envAppend,
envprepend => \&envPrepend,
envremove => \&envRemove,
envset => \&envSet,
envunset => \&envUnset,
pathappend => \&envAppend,
pathprepend => \&envPrepend,
pathremove => \&envRemove,
proddir => \&envSet,
setupenv => \&envSet,
               );

# Some local variables
    my $pos; my $i;
    my $comm; my $arg; my $qaz;


# Read in the table file
    open FILE, "<$fn";
    read FILE, $data, 1000000;
    close FILE;
    $data =~ s/\#.*?\n//g;

    my @group = $data =~ m/group:(.+?end:)/gsi;
    $pos = -1;
    my $flavour = fix_special($flavor);
    my $pattern = "FLAVOR *= *$flavour( |\n)";
    my $pattern2 = "FLAVOR *= *ANY( |\n)";
    my $pattern3 = "FLAVOR *= *NULL( |\n)";
    for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	$pos = $i if ($group[$i] =~ m/$pattern/gsi);
	$pos = $i if ($group[$i] =~ m/$pattern2/gsi);
	$pos = $i if ($group[$i] =~ m/$pattern3/gsi);
    }
    @group = $group[$pos] =~ m/Common:(.+?)End:/gsi;
    my $group = $group[0];
# Replace certain variables
    $group =~ s/\$\{PRODUCTS\}/$db/g;
    $group =~ s/\$\{UPS_PROD_DIR\}/$proddir/g;
    $group =~ s/\$\{UPS_PROD_FLAVOR\}/$flavor/g;
    $group =~ s/\$\{UPS_PROD_NAME\}/$prod/g;
    $group =~ s/\$\{UPS_PROD_VERSION\}/$vers/g;
    $group =~ s/\$\{UPS_UPS_DIR\}/$upsdir/g;
    
    my @lines = split "\n",$group;
    for ($i = 0;$i<@lines;$i++) {
	next if (!($lines[$i] =~ m/[a-z]+\(.*\)/i));
	($comm,$arg)=$lines[$i] =~ m/([a-z]+)\((.*)\)/i;
	my @arg = split ",",$arg;
	$comm =~ tr/[A-Z]/[a-z]/;
	if ($comm eq "setupenv") {
	    $qaz = $prod;
	    $qaz =~ tr/[a-z]/[A-Z]/;
	    $arg[0] = "SETUP_$qaz";
	    $arg[1] = "$prod $vers -f $flavor -z $db"; 
	}
	if ($comm eq "proddir") {
	    $qaz = $prod;
            $qaz =~ tr/[a-z]/[A-Z]/;
            $arg[0] = "$qaz\_DIR";
            $arg[1] = "$proddir";
	}
	if (($comm eq "setuprequired")&&($fwd==0)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            $foo = eups_unsetup($qaz,$outfile);
	    $retval =+ $foo;
	    print STDERR "ERROR : REQUIRED UNSETUP $qaz failed \n" if ($foo < 0);
	    next;
	}
        if (($comm eq "setupoptional")&&($fwd==0)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
	    eups_unsetup($qaz,$outfile);
	    next;
        }
        if (($comm eq "setuprequired")&&($fwd==1)) {
	    ($qaz) = $arg =~ m/ *"(.*)"/;
            $foo = eups_setup($qaz,$outfile);
	    $retval =+ $foo;
            print STDERR "ERROR : REQUIRED SETUP $qaz failed \n" if ($foo < 0);
	    next;
        }
        if (($comm eq "setupoptional")&&($fwd==1)) {
            ($qaz) = $arg =~ m/ *"(.*)"/;
            eups_setup($qaz,$outfile);
	    next;
        }
	if ($fwd == 0) {
	    if ($switchback{$comm}) {
		$switchback{$comm}->(@arg)}
	    else 
	    {
		print STDERR "Unknown command $comm in $fn\n";
	    }
	} 
	else {
            if ($switchfwd{$comm}) {
                $switchfwd{$comm}->(@arg)}
            else
            {
                print STDERR "Unknown command $comm in $fn\n";
            }
        } 

    }   

    return $retval;
}



sub eups_unsetup {

use File::Spec::Functions;
use File::Basename;

my $eups_dir = $ENV{"EUPS_DIR"};
# We don't need error checking here since that 
# is already done in evilsetup

my $retval = 0;

my $debug = $ENV{"EUPS_DEBUG"};
$debug = 0 if ($debug eq "");

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR : PROD_DIR_PREFIX not specified\n";
    $retval = -1;
    goto END;
}


# Need to extract the parameters carefully
my ($args,$outfile) = @_;
$args =~ s/\-[a-zA-Z]  *[^ ]+//g;
@args = split " ",$args;
$prod = $args[0];
if ($prod eq "") {
    print STDERR  "ERROR : Product not specified\nSyntax : evilsetup unsetup <product>\n";
    $retval = -1;
    goto END;
}

# Now get the information from eups_flavor
$comm = "eups_flavor -a $prod";
$comm = catfile($eups_dir,"bin",$comm);
$out = `$comm`;
if ($out eq "") {
   print STDERR "ERROR running eups_flavor : $comm\n" if ($debug == 1);
   $retval = -1;
   goto END;
}
# Parse the output for the flavor and version file
($vers,$flavor,$db,$temp) = split " ",$out;

print STDERR "Unsetting up : $prod  " if ($debug == 1);
print STDERR "Version: $vers\nFlavor: $flavor\n" if ($debug == 1);

# The version file reading code used to go here.
# This has been removed since it is no longer used.
# The software assumes that the file is in a ups directory.

my $capprod = $prod;
$capprod =~ tr/[a-z]/[A-Z]/;
$capprod = "$capprod\_DIR";
$prod_dir = $ENV{"$capprod"};
if ($prod_dir eq "") {
    print STDERR "ERROR: Environment variable $prod $capprod not set\n" if ($debug == 1);
    $retval=-1;
    goto END;
}
$ups_dir = catfile($prod_dir,"ups");
$table_file = "$prod.table";
$table_file = catfile($ups_dir,$table_file);

if (!(-e $table_file)) {
  print STDERR "ERROR: Missing table file $table_file\n" if ($debug == 1);
  $retval=-1;
  goto END;
}

#Call the table parser here 
#The arguments are the full table path, the direction (reversed or not)
#prod_dir,ups_dir,verbosity

$fwd = 0;
$retval = parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile);

END:

return $retval;
}



sub eups_setup {

use File::Spec::Functions;
use File::Basename;

my $retval = 0;

my $debug = $ENV{"EUPS_DEBUG"};

$debug = 0 if ($debug eq "");

#Some more environment variables
$prodprefix = $ENV{"PROD_DIR_PREFIX"};
if ($prodprefix eq "") {
    print STDERR  "ERROR : PROD_DIR_PREFIX not specified\n";
    $retval = -1;
    goto END;
}


# Need to extract the parameters carefully
my ($args,$outfile) = @_;
my $qaz = $args;
$args =~ s/\-[a-zA-Z]  *[^ ]+//g;
@args = split " ",$args;
$prod = $args[0];
# Extract version info if any
$vers = $args[1]; 
if ($prod eq "") {
    print STDERR  "ERROR : Product not specified\n";
    print STDERR "Syntax : evilsetup setup <product> [version] [-f <flavor>] [-z <database>]\n";
    $retval = -1;
    goto END;
}

#Determine flavour - first see if specified on command line
#else get it from the environment EUPS_FLAVOR
($flavor) = $qaz =~ m/\-f  *([^ ]+)/;
$flavor = $ENV{"EUPS_FLAVOR"} if ($flavor eq ""); 
if ($flavor eq "") {
    print STDERR "ERROR : No flavor specified, Use -f or set EUPS_FLAVOR\n";
    $retval = -1;
    goto END;
}

#Determine database - or get it from environment PRODUCTS
#We want this to propagate to subproducts
my $dbset = 0;
($db) = $qaz =~ m/\-z  *([^ ]+)/;
#$db = $ENV{"PRODUCTS"} if ($db eq "");
if ($db eq "") {
    $db = $ENV{"PRODUCTS"};
} else {
    my $db_old = $ENV{"PRODUCTS"};
    $ENV{"PRODUCTS"} = $db;
    $dbset = 1;
}
    
if ($db eq "") {
    print STDERR "ERROR : No database specified, Use -z or set PRODUCTS\n";
    $retval = -1;
    goto END;
}

print STDERR "Setting up : $prod   " if ($debug == 1);
# Now check to see if the table file and product directory are 
# specified. If so, extract these and immediately start, else 
# complain 
$table_file = "";
$prod_dir = "";
$ups_dir = "";
($prod_dir) = $qaz =~ m/\-r  *([^ ]+)/;
# Table files no longer used.
#($table_file) = $qaz =~ m/\-m  *([^ ]+)/;
if (!($prod_dir eq "")) {
    $table_file = "$prod.table";
    $table_file = catfile("ups",$table_file);
    if (!($table_file eq "")) {
	print STDERR "WARNING : Overriding the table file setting with $prod.table\n" if ($debug==1);
    }
    if (!($prod_dir =~ m"^/")) {
	$prod_dir = catfile($prodprefix,$prod_dir);
    }
    if (!($table_file =~ m"^/")) {
	$table_file = catfile($prod_dir,$table_file);
    }
    $vers = "LOCAL" if ($vers eq "");
    print STDERR "   Flavour:  $flavor\n" if ($debug == 1);
    goto START;
}


#Determine version - check to see if already defined, otherwise
#determine it from current.chain
#Also construct the full version file and check if it exists.
if ($vers eq "") {
    $fn = catfile($db,$prod,"current.chain");
    if (!(-e $fn)) {
	print STDERR "ERROR : No version or current.chain\n" if ($debug == 1);
	$retval = -1;
	goto END;
    }
    open FILE, "<$fn";
    read FILE, $versinfo, 1000000;
    close FILE;
# Now strip out all comments
    $versinfo =~ s/\#.*\n//g;
    $versinfo =~ s/flavor/##FLAVOR/gsi;
    @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
    @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
    @group = (@groups2,@groups3);
#Now find the appropriate group
    $pos = -1;
    $flavour = fix_special($flavor);
    $pattern = "FLAVOR *= *$flavour( |\n)";
    my $pattern2 = "FLAVOR *= *ANY( |\n)";
    my $pattern3 = "FLAVOR *= *NULL( |\n)";
    for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	$pos = $i if ($group[$i] =~ m/$pattern/gsi);
	$pos = $i if ($group[$i] =~ m/$pattern2/gsi);
	$pos = $i if ($group[$i] =~ m/$pattern3/gsi);
    }
    if ($pos == -1) {
	print STDERR "ERROR: Flavor $flavor not found in chain file $fn\n" if ($debug == 1);
	$retval = -1;
	goto END;
    }
    ($vers) = $group[$pos] =~ m/VERSION *= *(.+?) *\n/i;
    if ($vers eq "") {
        print STDERR "ERROR: No version found in chain file $fn\n" if ($debug == 1);
        $retval = -1;
        goto END;
    }
}
# Now construct the filename
$fn = catfile($db,$prod,"$vers.version");

print STDERR "  Version: $vers Flavour: $flavor\n" if ($debug == 1);

# Now read in the version file and start to parse it
if (!(open FILE,"<$fn")) {
    print STDERR "ERROR: Cannot open version file $fn\n" if ($debug == 1);
    $retval = -1;
    goto END;
}
read FILE,$versinfo,1000000;
close FILE;
# Now strip out all comments
$versinfo =~ s/\#.*\n//g;
# Extract the groups - either defined by group-end or between two flavours
@groups = $versinfo =~ m/group:(.+?)end:/gsi;
$versinfo =~ s/group:(.+?)end://gsi;
$versinfo =~ s/flavor/##FLAVOR/gsi;
@groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
@groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
@group = (@groups,@groups2,@groups3);

#Now find the appropriate group
$pos = -1;
$flavour = fix_special($flavor);
$pattern = "FLAVOR *= *$flavour( |\n)";
my $pattern2 = "FLAVOR *= *ANY( |\n)";
my $pattern3 = "FLAVOR *= *NULL( |\n)";
for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
    $pos = $i if ($group[$i] =~ m/$pattern/gsi);
    $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
    $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
}
if ($pos == -1) {
    print STDERR "ERROR: Flavor $flavor not found in version file $fn\n" if ($debug == 1);
    $retval = -1;
    goto END;
}

# Now extract the prod_dir, ups_dir, table_dir and table_file
($prod_dir)  = $group[$pos] =~ m/PROD_DIR *= *(.+?) *\n/i;
$ups_dir = "ups";
$table_dir = "ups";
$table_file = "$prod.table";

#Table files now must be in UPS directory
#($ups_dir) = $group[$pos] =~ m/UPS_DIR *= *(.+?) *\n/i;
#($table_dir) = $group[$pos] =~ m/TABLE_DIR *= *({^ ,.}+?) *\n/i;
#($table_file) = $group[$pos] =~ m/TABLE_FILE *= *(.+?) *\n/i;

# Does the product directory have an environment variable set in it
@env = $prod_dir =~ m/\$\{(.+?)\}/g;
for ($i = 0; $i < @env; $i++) {
    $val = $ENV{"$env[$i]"};
    $prod_dir =~ s/\$\{$env[$i]\}/$val/g;
}
if (!($prod_dir =~ m"^/")) {
    $prod_dir = catfile($prodprefix,$prod_dir);
}
if (!($ups_dir =~ m"^/")) {
    $ups_dir = catfile($prod_dir,$ups_dir);
}
$table_file = catfile($ups_dir,$table_file);


START:
if (!(-e $table_file)) {
  print STDERR "ERROR: Missing table file $table_file\n" if ($debug == 1);
  $retval=-1;
  goto END;
}

#Call the table parser here 
#The arguments are the full table path, the direction (reversed or not)
#prod_dir,ups_dir,verbosity

$fwd = 1;
$retval = parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,$db,$fwd,$outfile);


END:

# If we overrode the database, restore it.
if ($dbset == 1) {
    $ENV{"PRODUCTS"} = $db_old;
}

return $retval;
}





