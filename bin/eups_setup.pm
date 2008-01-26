#!/usr/bin/perl
# Parser for eups table files
# Nikhil Padmanabhan, Princeton
#
#
# Jan 22, 2002
#EUPS : A Unix Versioning System
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

BEGIN {
    use Exporter ();
    our @ISA = qw(Exporter);
    our @EXPORT = qw(&fix_special &eups_list &eups_unsetup &eups_setup &eups_find_products &eups_parse_argv &eups_show_options &eups_find_prod_dir &find_best_version &eups_find_roots &eups_version_match &eups_setshell);
    our $VERSION = 1.1;
    our @EXPORT_OK = ();
}
#
# Permitted relational operators
#
$relop_re = "<=?|>=?|==";

my(%setupVersion);		# version that we actually setup (if there's an inconsistency)

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
    my ($in) = @_;
    my @env_var = $in =~ m/\$\{(.+?)\}/g;
    for (my $i = 0; $i < @env_var; $i++) {
	my $val = $ENV{$env_var[$i]};
	if ($val) {
	    $in =~ s/\$\{.+?\}/$val/g;
	}
    }
    return $in;
}

sub pathUnique {
   # Return a version of $var such that each element (separated by delim) occurs only once
   my($var, $delim) = @_;

   my(%elems);
   my(@ovar);
   foreach (split($delim, $var)) {
      if ($_ && !defined($elems{$_})) {
	 push(@ovar, $_);
	 $elems{$_}++;
      }
   }
   
   return join($delim, @ovar);
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
    my $shell = eups_setshell();
    my $name = $_[0];
    my $value = $_[1];
    if ($shell eq "csh") {
       $value =~ s/\$@/\\\!\*/g;
	print $outfile "alias $name \'$value\'\n";
    }
    if ($shell eq "sh") {
	print $outfile "function $name \{ $value \; \}; export -f $name\n";
    }
}

sub unAlias {
    use File::Basename;
    our $outfile;
    my $shell = eups_setshell();
    my $name = $_[0];
    if ($shell eq "csh") {
        print $outfile "unalias $name\n";
    }
    if ($shell eq "sh") {
        print $outfile "unset $name\n";
    }
}


sub envAppend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");

    my($prepend_delim) = 0;	# should we prepend an extra :?
    my($append_delim) = 0;	# should we append an extra :?
    if($val =~ s/^$delim+//) {
	$prepend_delim = 1;
    }
    if($val =~ s/$delim+$//) {
	$append_delim = 1;
    }

    if ($val =~ s/^\$\?{([^\}]*)}/\${$1}/) {
       if (!defined($ENV{$1})) {
	  if ($debug > 0) {
	     warn "\$$1 is not defined; not prepending to $var\n";
	  }
	  
	  return
       }
    }
    
    $curval = $ENV{$var};
    if ($val ne "") {
       if ($curval) {
	  $curval .= $delim;
       }
       $curval .= "$val";
    } else {
       if ($debug > 0) {
	  warn "$_[1] is not defined; ignoring in setting $var\n";
       }
    }

    if ($force && $$oldenv{$var}) {
       undef $$oldenv{$var};
    }
    $ENV{$var} = pathUnique(envInterpolate($curval), $delim);

    if ($prepend_delim && $ENV{$var} !~ /^$delim/) {
	$ENV{$var} = $delim . $ENV{$var};
    }
    if ($append_delim && $ENV{$var} !~ /^$delim/) {
	$ENV{$var} .= $delim;
    }
}

sub envPrepend {
    our $outfile;
    my $var = $_[0];
    my $val = cleanArg($_[1]);
    my $delim = cleanArg($_[2]);
    $delim = ":" if ($delim eq "");

    my($prepend_delim) = 0;	# should we prepend an extra :?
    my($append_delim) = 0;	# should we append an extra :?
    if($val =~ s/^$delim+//) {
	$prepend_delim = 1;
    }
    if($val =~ s/$delim+$//) {
	$append_delim = 1;
    }

    if ($val =~ s/^\$\?{([^\}]*)}/\${$1}/) {
       if (!defined($ENV{$1})) {
	  if ($debug > 0) {
	     warn "\$$1 is not defined; not prepending to $var\n";
	  }
	  
	  return
       }
    }
    
    $curval = "";
    if ($val ne "") {
       $curval .= "$val";
       if ($curval) {
	  $curval .= $delim;
       }
    } else {
       if ($debug > 0) {
	  warn "$_[1] is not defined; ignoring in setting $var\n";
       }
    }
    $curval .= $ENV{$var};

    if ($force && $$oldenv{$var}) {
       undef $$oldenv{$var};
    }

    $ENV{$var} = pathUnique(envInterpolate($curval), $delim);

    if ($prepend_delim && $ENV{$var} !~ /^$delim/) {
	$ENV{$var} = $delim . $ENV{$var};
    }
    if ($append_delim && $ENV{$var} !~ /^$delim/) {
	$ENV{$var} .= $delim;
    }
}

sub envSet {
    my $var = $_[0];
    my $val = cleanArg($_[1]);

    if ($force && $$oldenv{$var}) {
       undef $$oldenv{$var};
    }

    if ($val =~ s/^\$\?{([^\}]*)}/\${$1}/) {
       if (!defined($ENV{$1})) {
	  if ($debug > 0) {
	     warn "\$$1 is not defined; not setting $var\n";
	  }
	  
	  return
       }
    }
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
    $sval =~ s/^$sdelim+//;
    $sval =~ s/$sdelim+$//;

    $curval = $ENV{$var};
    $curval =~ s/$sval//g;
    $curval =~ s/$sdelim+/$sdelim/g;
    $curval =~ s/^$sdelim//;
    $curval =~ s/$sdelim$//;

    if ($force && $$oldenv{$var}) {
       undef $$oldenv{$var};
    }
    $ENV{$var} = $curval;
}

sub envUnset {
    our $outfile;
    my $var = $_[0];
    if ($var !~ /^EUPS_(DIR|PATH)$/) {
       delete $ENV{$var};
    }
}

sub extract_table_commands {
    my($tableFile, $data, $flavor, $build) = @_;	# $tableFile is only for diagnostics

# Protect special characters in flavor and 
# define matching patterns    
    my $flavor = fix_special($flavor);
    my $spattern = "FLAVOR\\s*=\\s*";
    my $pattern = "$spattern($flavor|ANY|NULL)\\s*(\$|\n)";

# Extract the groups - first see if old style table file
    my @group = ($data =~ m/group:(.+?end:)/gsi);
    if (scalar(@group) == 0) {	# Minimal table file
	$data .= "\n";
	my @lines = split  "\n", $data;

	@lines = rewrite_minimal_table(@lines);

	my $record = 1;		# keep this line
	my $block = "";
	for ($i = 0; $i < @lines; $i++) {
	    my $line = $lines[$i]; 
	    if ($line =~ /^\s*if\s*\((.*)\)\s*{\s*$/i) {
	       $record = eval_logical($1, $flavor, $build);
	       next;
	    } elsif ($line =~ /^\s*}\s*$/) {
	       $record = 1;
	       next;
	    }
	    
	    $block .= "$line\n" if ($record);
	}

	@group = ($block);
    } else {			# Old style table file
	my $pos = -1;
	for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
	    $pos = $i if ($group[$i] =~ m/$pattern/gi);
	}
	if ($pos == -1) {           # no flavor was specified
	    warn "FATAL ERROR: no match for flavor \"$flavor\" in table file\n";
	    return -1;
	} else {
	    @group = ($group[$pos] =~ m/Common:(.+?)End:/gsi);
	}
    }

    return $group[0];
}

#
# Evaluate a logical expression:
#
# expr : term
#      | term || term
#      | term && term
#
# term : ( term )
#      | prim == prim
#      | prim != prim
#      | prim <  prim
#      | prim <= prim
#      | prim >  prim
#      | prim >= prim
#
# prim : FLAVOR
#      | string
#
sub eval_logical {
   my($logical) = @_[0];
   local($flavor) = @_[1];
   local($build) = @_[2];

   local(@terminals) = grep(/[^\s]/, split(/(\s|==|!=|[<>]=?|\|\||&&|[()])/, $logical));

   return log_expr();
}

sub log_expr {
   my($lhs) = log_term();
   my($op) = shift(@terminals);

   if (!$op) {
      return $lhs;
   }

   my($rhs) = log_term();
   if ($op eq "||") {
      #warn "RHL expr $lhs || $rhs: " . ($lhs || $rhs ? 1 : 0) . "\n";
      return $lhs || $rhs ? 1 : 0;
   } elsif ($op eq "&&") {
      return $lhs && $rhs ? 1 : 0;
   } else {
      warn "Saw unexpected operator $op in expr ($lhs $op $rhs)\n";
      return 0;
   }
}

sub log_term {
   my($next) = shift(@terminals);

   if ($next eq "(") {
      $term = log_expr();
      $next = shift(@terminals);
      if ($next != ")") {
	 warn "Saw next = \"$next\" in term\n";
      }

      return $term;
   }
   unshift(@terminals, $next);

   my($lhs) = log_prim();
   my($op) = shift(@terminals);

   if (!$op) {
      return "$lhs";
   }

   my($rhs) = log_prim();
   if ($op eq "==") {
      #warn "RHL term $lhs $op $rhs: " . ($lhs eq $rhs ? 1 : 0) . "\n";
      return $lhs eq $rhs ? 1 : 0;
   } elsif ($op eq "!=") {
      return $lhs ne $rhs ? 1 : 0;
   } elsif ($op eq "<") {
      return ($lhs cmp $rhs) < 0 ? 1 : 0;
   } elsif ($op eq "<=") {
      return ($lhs cmp $rhs) <= 0 ? 1 : 0;
   } elsif ($op eq ">") {
      return ($lhs cmp $rhs) > 0 ? 1 : 0;
   } elsif ($op eq ">=") {
      return ($lhs cmp $rhs) >= 0 ? 1 : 0;
   } else {
      warn "Saw unexpected operator $op in term ($lhs $op $rhs)\n";
      return 0;
   }
}

sub log_prim {
   my($term) = shift(@terminals);

   if ($term =~ /^FLAVOR$/i) {
      $term = $flavor;
   } elsif ($term =~ /^BUILD$/i) {
      $term = $build;
   } elsif ($term =~ /^[a-zA-Z0-9_]+$/) {
      ;				# a real terminal
   } else {
      warn "Saw prim \"$term\"\n";
   }

   #warn "RHL prim $term\n";
   
   return $term;
}

#
# Rewrite a minimal table file to use C-style if statements
#
sub rewrite_minimal_table {
   my(@lines) = @_;

   my($i);
   my(@newLines) = undef;
   my($inblock) = 0;
   for ($i = 0; $i < @lines; $i++) {
      my $line = $lines[$i];
      
      if ($line =~ /^flavor\s*=\s*(\S*)/i) {
	 my($logical) = undef;
	 while ($line =~ /$spattern/si) {
	    my($f) = $1;
	    if ($logical) {
	       $logical .= " || ";
	    }
	    $logical .= "FLAVOR == $f";
	    
	    $i++;
	    if ($i == @lines) {
	       last;
	    }
	    $line = "$lines[$i]";	    
	 }

	 push(@newLines, "if ($logical) {");
	 $inblock++;
      }

      if ($line =~ /^\S/) {
	 if ($inblock) {
	    push(@newLines, "}");
	 }
	 if ($inblock) {
	    $inblock--;
	 }
      }
      
      push(@newLines, $line);
   }

   return @newLines;
}	    

#
# Extract an argument from a possibly quoted string
#
sub get_argument {
   my($arg, $file, $lineno, $line) = @_;
   if ($arg =~ /^ *"(.*)" *$/ || $arg =~ /^ *([^\"]*) *$/) {
      return $1;
   } else {
      die "ERROR: syntax error in $file($lineno):\n$line\n\n";
   }
}


sub parse_table {
   my($fn, $proddir, $upsdir, $prod, $vers, $flavor,
      $root, $fwd, $outfile, $only_dependencies, $build, $quiet) = @_;
   
   my $data = 0;

# Define the return value
    my $retval = 0;

    my $db = catfile($root,'ups_db');

# Define the command hashes

   %switchback = (
		  addalias => \&unAlias,
		  envappend => \&envRemove,
		  envprepend => \&envRemove,
		  envremove => \&envAppend,
		  envset => \&envUnset,
		  setenv => \&envUnset,
		  unsetenv => \&envSet,
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
		 setenv => \&envSet,
		 unsetenv => \&envUnset,
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

    my $only_dependencies_recursive = 0; # Don't only setup deps for dependent products

# Read in the table file
    if ($fn eq "none") {
       $data = "";
    } else {
       my @size = stat($fn);
       open FILE, "<$fn";
       read FILE, $data, $size[7];
       close FILE;
       $data =~ s/([ \t]*\#[^\n]*)?//g;	# strip comments
    }

# Extract the commands from the table file
    $group = extract_table_commands($fn, $data, $flavor, $build);
    if ($group==-1) {
	$retval = -1;
	return $retval;
    }

    my $dbdir = catfile($upsdir, "ups_db");

# Replace certain variables
    $group =~ s/\$\{PRODUCTS\}/$db/g;
    $group =~ s/\$\{PRODUCT_DIR\}/$proddir/g;
    $group =~ s/\$\{PROD_DIR\}/$proddir/g;
    $group =~ s/\$\{PRODUCT_FLAVOR\}/$flavor/g;
    $group =~ s/\$\{PRODUCT_NAME\}/$prod/g;
    $group =~ s/\$\{PRODUCT_VERSION\}/$vers/g;
    $group =~ s/\$\{UPS_DIR\}/$upsdir/g;
    $group =~ s/\$\{UPS_DB\}/$dbdir/g;
    # Older synonyms
    $group =~ s/\$\{UPS_PROD_DIR\}/$proddir/g;
    $group =~ s/\$\{UPS_PROD_FLAVOR\}/$flavor/g;
    $group =~ s/\$\{UPS_PROD_NAME\}/$prod/g;
    $group =~ s/\$\{UPS_PROD_VERSION\}/$vers/g;
    $group =~ s/\$\{UPS_UPS_DIR\}/$upsdir/g;
    
# Execute the proddir and setupenv commands directly
    $comm = "setupenv";
    $qaz = $prod;
    $qaz =~ tr/[a-z]/[A-Z]/;
    $arg[0] = "SETUP_$qaz";
    $arg[1] = "$prod $vers -f $flavor -Z $root";
    if (!$only_dependencies) {
       if ($fwd == 0) {
	  $switchback{$comm}->(@arg);
       } else {
	  $switchfwd{$comm}->(@arg);
       }
    }
   
    $arg[0] = "$qaz\_DIR";
    $arg[1] = "$proddir";
    $comm = "proddir";
    if (!$only_dependencies) {
       if ($fwd == 0) {
	  $switchback{$comm}->(@arg);
       }
       else {
	  $switchfwd{$comm}->(@arg);
       }
    }
    #
    # Split the table file into lines
    #
    my @lines = split "\n",$group;

    # If we're unsetting up, expand any remaining variables;
    # they may become undefined as we unsetup products
    if (!$fwd) {
       my($line);
       foreach $line (@lines) {
	  $line = envInterpolate($line);
       }
    }

# Now loop over the remaining commands
    for ($i = 0;$i<@lines;$i++) {
       chomp($lines[$i]);
       next if ($lines[$i] =~ /^\s*($|\#)/);
	#next if (!($lines[$i] =~ m/[a-z]+\(.*\)/i));
	($comm,$arg)= ($lines[$i] =~ m/([a-z]+)\((.*)\)/i);
	my @arg = split ",",$arg;
	$comm =~ tr/[A-Z]/[a-z]/;
	if ($comm eq "setupenv" || $comm eq "proddir") {
	   print STDERR "WARNING: Deprecated command $comm\n" if ($debug > 1);
	} elsif (($comm eq "setuprequired" || $comm eq "setupoptional") && $fwd==0) {
	   if (!$no_dependencies) {
	      local($processing_optional) = ($comm eq "setupoptional"); # not my!  used in eups_setup
	      $qaz = get_argument($arg, $fn, $i+1, $lines[$i]);
	      my($foo) = eups_unsetup($qaz, $outfile, $no_dependencies,
				  $only_dependencies_recursive, $flags, undef,
				  $debug, $quiet);
	      my($p) = split(" ", $qaz);
	      if ($foo && $unsetup_products{$p}) { # we've already unset it; we don't need to do it twice
		 $foo = 0;
	      }
	      
	      if($comm eq "setuprequired" && !defined($processing_optional)) {
		  $retval =+ $foo;
		  print STDERR "ERROR: REQUIRED UNSETUP $qaz failed \n" if ($foo < 0 && $debug >= 0);
	      } else {
		  print STDERR "WARNING: unsetup of optional $qaz failed\n" if ($foo < 0 && $debug > 1);
	      }
	      
	      $unsetup_products{$p}++; # remember that we already unset it
	   }
        } elsif ($comm eq "setuprequired" && $fwd == 1) {
	   if (!$no_dependencies) {
	      $qaz = get_argument($arg, $fn, $i+1, $lines[$i]);
	      $foo = eups_setup($qaz, $outfile, $no_dependencies,
				$only_dependencies_recursive, $flags, undef,
				$debug, $quiet,0);
	      if (!defined($processing_optional)) {
		 print STDERR "ERROR: REQUIRED SETUP $qaz failed while setting up $prod $vers\n" if ($foo < 0);
	      }
	      $retval += $foo;
	   }
        } elsif ($comm eq "setupoptional" && $fwd==1) {
	   if (!$no_dependencies) {
	      local($processing_optional) = 1; # not my!  used in eups_setup
	      $qaz = get_argument($arg, $fn, $i+1, $lines[$i]);
	      if (eups_setup($qaz, $outfile, $no_dependencies,
			     $only_dependencies_recursive, $flags, undef,
			     $debug, $quiet, 1) < 0 && $debug > 1) {
		 warn "WARNING: optional setup of $qaz failed\n";
	      }
	   }
	} else {
	   if ($fwd == 0 && $switchback{$comm}) {
	      if (!$only_dependencies) {
		 $switchback{$comm}->(@arg);
	      }
	   } elsif ($fwd == 1 && $switchfwd{$comm}) {
	      if (!$only_dependencies) {
		 $switchfwd{$comm}->(@arg);
	      }
	   } else {
	      if ($debug > 1 && $lines[$i] !~ /^\s*(Action\s*=\s*setup)\s*$/i) {
		 printf STDERR "Unknown command \"%s\" in $fn, line %d\n", $lines[$i], $i + 1;
	      }
	   }
	}
    }

    return $retval;
}

sub eups_unsetup {

   use File::Spec::Functions;
   use File::Basename;
   
   my $eups_dir = $ENV{"EUPS_DIR"};
   my ($prod_dir, $table_file);

   # We don\'t need error checking here since that 
   # is already done in eups_setup
   
   local $indent = $indent + 1;
   
   # Need to extract the parameters carefully
   local ($args, $outfile, $no_dependencies, $only_dependencies, $flags,
	  $user_table_file, $debug, $quiet) = @_;
   $args =~ s/\-[a-zA-Z]\s+[^ ]+//g;
   @args = split " ",$args;
   my($prod) = $args[0];
   my($uservers) = $args[1];
   my($vers, $flavor, $root);
   if ($user_table_file) {
      ($prod_dir, $table_file) = (undef, $user_table_file);
      warn "Using $table_file rather than a declared product\n" if ($debug > 0);
   } else {
      if ($prod eq "") {
	 print STDERR  "ERROR: Product not specified; use -h to list your options\n";
	 return -1;
      }
   
      my($status);
      ($status, $vers, $flavor, $root) = parse_setup_prod($prod);
      my $db = catfile($root, 'ups_db');

      if ($vers && $uservers && $vers ne $uservers) {
	 if ($debug > 0) {
	    warn "You are unsetting up $prod $vers, but you asked to unsetup $uservers\n";
	 }
      }

      if($status ne "ok") {
	 print STDERR "WARNING: $prod is not setup\n" if ($debug > 1);
	 return -1;
      }
      
      if (($debug >= 1 && !$quiet) || $debug > 2) {
	 show_product_version("Unsetting up", $indent, $prod, $vers, $flavor);
      }
      
      my $capprod = uc($prod) . "_DIR";
      $prod_dir = $ENV{$capprod};
      if ($prod_dir eq "") {
	 print STDERR "ERROR: Environment variable $prod $capprod not set\n" if ($debug >= 1);
	 return -1;
      }

      if ($vers =~ /^LOCAL:(\S*)/) { # they setup a local directory
	 $prod_dir = $1;	# here it is
	 $vers = "";
      }

      # Not necessarily correct anymore.
      $ups_dir = catfile($prod_dir,"ups");
      
      # Now construct the version file\'s name, then read and parse it
      if ($vers eq "") {
	 $table_file = catfile($ups_dir, "$prod.table"); # unknown version, so look in $ups_dir
	 if (! -e $table_file) {
	    $table_file = "none";
	 }
      } else {
	 $fn = catfile($db,$prod,"$vers.version");
	 ($prod_dir, $table_file) = read_version_file($root, $fn, $prod, $flavor, 1, 0);
	 if (not $prod_dir) {
	    return -1;
	 }
      }
   }

   if ($table_file !~ /^none$/i && (!(-e $table_file))) {
      print STDERR "ERROR: Missing table file \"$table_file\"\n" if ($debug >= 1);
      return -1;
   }
   
   #Call the table parser here 
   #The arguments are the full table path, the direction (reversed or not)
   #prod_dir,ups_dir,verbosity

   $fwd = 0;
   return parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,
		      $root,$fwd,$outfile,$only_dependencies,$$flags{build}, $quiet);
}

# Search for the best version for a given product, return the essential paths.
#
# Returns:
#   - the selected root path
#   - the product directory
#   - the product version
#   - the table file name
#
sub find_best_version(\@$$$$$) {
    my ($roots, $prod, $vers, $ignore_version, $flavor, $quiet) = @_;
    my $matchroot = "";

    if ($ignore_version) {
       $vers = "";
    }

    if ($vers eq "") {
	# If no version explicitly specified, get the first db with a current one.
	foreach $root (@{$roots}) {
	    $fn = catfile($root,'ups_db',$prod,"current.chain");
	    if (-e $fn) {
		$vers = read_chain_file($fn, $flavor, $optional || $debug <= 1);
	    
		if ($vers eq "") {
		   print STDERR "ERROR: No version found in chain file $fn for flavor $flavor\n" if ($debug >= 2 + $optional);
		   next;
		}
		$matchroot = $root;
		last;
	    }
	}
	if ($vers eq "") {
	    print STDERR "ERROR: No version of product $prod has been declared current for flavor $flavor\n"
		if ($debug >= 1 + $optional + $quiet);
	    return undef, undef, undef, undef;
	}
    } else {
       if (0) {	# test code for eups_version_cmp
	  my(@tests) = (
			["aa", "aa", 0],
			["aa.2","aa.1", 1],
			["aa.2.1","aa.2", 1],
			["aa.2.1","aa.2.2", -1],
			["aa.2.1","aa.3", -1],
			["aa.2.b","aa.2.a", 1],
			["aa.2.b","aa.2.c", -1],
			["v1_0_0","1.0.2", -1],
			["1_0_0","v1.0.2", -1],
			["v1_0_3","a1.0.2", -1],
			["v1_0_0","v1.0.2", -1],
			["v1_0_3","v1.0.2", 1],
			["v2_0","v1_0", 1],
			["v2_0","v3_0", -1],
			["v1.2.3","v1.2.3+a", -1],
			["v1.2-0","v1.2.3", -1],
			["v1.2-4","v1.2.3", -1],
			["1","1-a", 1],
			["1","1+a", -1],
			["1-a","1", -1],
			["1-b","1-a", 1],
			["1+a","1+b", -1],
			["1-a", "1+a", -1],
			["1+a", "1-a", 1],
			["1-rc2+a", "1-rc2", 1],
			["1-rc2+a", "1-rc2+b", -1],
			["1", "1", 0 ],
			["1.2", "1.1", +1],
			["1.2.1", "1.2", +1],
			["1.2.1", "1.2.2", -1],
			["1.2.1", "1.3", -1],
			["1_0_2", "1.0.0", +1],
			["1.2-rc1", "1.2", -1],
			["1.2-rc1", "1.2-rc2", -1],
			["1.2-rc1", "1.2.3", -1],
			["1.2-rc4", "1.2.3", -1],
			["1.2+h1", "1.2", +1],
			["1.2-rc1+h1", "1.2-rc1", +1],
			);
	  
	  my($test, $result);
	  my($nbad) = 0;
	  foreach $test (@tests) {
	     my($vname, $v, $expected) = @$test;
	     $result = eups_version_cmp($vname, $v);
	     #warn "eups_version_cmp($vname, $v) == $result\n";
	     if ($result != $expected) {
		$nbad++;
		printf STDERR "%-10s %-10s: %2d (expected %2d)\n", $vname, $v, $result, $expected;
	     }
	  }
	  die "quitting after tests; $nbad failed\n";
       }

       if ($vers =~ /$relop_re/o) {
	  (my($expr) = $vers) =~ s/^\s*//;
	  $vers = "";
	  foreach $root (@{$roots}) {
	     my($dir) = catfile($root, 'ups_db', $prod);
	     if (opendir(DFD, $dir)) {
		my(@versions, $file);
		foreach $file (readdir(DFD)) {
		   if ($file =~ /^(.*)\.version$/) {
		      my($prod_dir, $table_file) = read_version_file($root, "$dir/$file", $prod, $flavor, 0, 1);
		      if (not $prod_dir) {
			 next;
		      }
		      
		      push(@versions, $1);
		   }
		}

		@versions = reverse sort by_version_cmp @versions; # so we\'ll try the latest version first

		my($cvers) = undef; # current version
		my($fn) = catfile($root,'ups_db',$prod,"current.chain");
		if (-e $fn) {
		   $cvers = read_chain_file($fn, $flavor, $optional || $debug <= 1);
		   unshift @versions, $cvers;
		}

		my($vname);
		foreach $vname (@versions) {
		   if (eups_version_match($vname, $expr)) {
		      $matchroot = $root;
		      $vers = $vname;

		      if (defined($cvers) && $vers ne $cvers && $debug > 0 + $quiet) {
			 warn("Using version $vers to satisfy \"$expr\" ($cvers is current)\n");
		      }

		      my($extra) = ($debug >= 3 + $quiet) ? "in $root " : "";
		      warn("Version $vers ${extra}satisfies condition \"$expr\" for product $prod\n")
			  if ($debug >= 2 + $quiet);
		      
		      last;
		   }
		}
	     }
	  }
       } else {
	  # Find the first db with a matching prod:version
	  foreach $root (@{$roots}) {
	     $fn = catfile($root,'ups_db',$prod,"$vers.version");
	     
	     if (-e $fn) {
		my ($prod_dir, $table_file) = read_version_file($root, $fn, $prod, $flavor, 0, 1);
		if (defined($prod_dir)) {
		   $matchroot = $root;
		   last;
		}
	     }
	  }
       }

	if ($matchroot eq "") {
	    return undef, undef, undef, undef;
	}
    }
    
    my $matchdb = catfile($matchroot, 'ups_db');

    # Now construct the version file\'s name, then read and parse it
    $fn = catfile($matchdb,$prod,"$vers.version");
    my ($prod_dir, $table_file) = read_version_file($matchroot, $fn, $prod, $flavor, 0, 0);
    if (!$prod_dir) {
	return undef, undef, undef, undef;
    }
    
    # Clean up any truncated paths [??? CPL]
    if (!($prod_dir =~ m"^/")) {
	$prod_dir = catfile($matchroot,$prod_dir);
    }
    if (!($table_file =~ m"^/" || $table_file =~ m/^none$/)) {
	$table_file = catfile($prod_dir,$table_file);
    }

    
    #print STDERR "found: $prod  $matchroot, $prod_dir, $vers, $table_file\n";
    return $matchroot, $prod_dir, $vers, $table_file;
}
      
sub by_version_cmp {
   # sort functions use a different "more efficient" calling convention. Sigh.
   return eups_version_cmp($a, $b);
}

sub eups_version_cmp {
   #
   # Compare two version strings
   #
   # The strings are split on [._] and each component is compared, numerically
   # or as strings as the case may be.  If the first component begins with a non-numerical
   # string, the other must start the same way to be declared a match.
   #
   # If one version is a substring of the other, the longer is taken to be the greater
   #
   # If the version string includes a '-' (say VV-EE) the version will be fully sorted on VV,
   # and then on EE iff the two VV parts are different.  VV sorts to the RIGHT of VV-EE --
   # e.g. 1.10.0-rc2 comes to the LEFT of 1.10.0
   #
   # Additionally, you can specify another modifier +FF; in this case VV sorts to the LEFT of VV+FF
   # e.g. 1.10.0+hack1 sorts to the RIGHT of 1.10.0
   #
   my($v1, $v2, $suffix) = @_;
    
   sub split_version($) {
      # Split a version string of the form VVV(-EEE)?(+FFF)?
      my($version) = @_;
      
      $version =~ /^([^-+]+)((-)([^-+]+))?((\+)([^-+]+))?/;

      return ($1, $4, $7);	# == VVV EEE FFF
   }

   my($prim1, $sec1, $ter1) = split_version($v1);
   my($prim2, $sec2, $ter2) = split_version($v2);

   if ($prim1 eq $prim2) {
      if ($sec1 || $sec2 || $ter1 || $ter2) {
	 if ($sec1 || $sec2) {
	    my($ret);
	    if ($sec1 && $sec2) {
	       $ret = eups_version_cmp($sec1, $sec2, 1);
	    } else {
	       return ($sec1) ? -1 : +1;
	    }
	    if ($ret == 0) {
	       return eups_version_cmp($ter1, $ter2, 1);
	    } else {
	       return $ret;
	    }
	 }
	 return eups_version_cmp($ter1, $ter2, 1);
      } else {
	 return 0;
      }
   }

   my(@c1) = split(/[._]/, $prim1);
   my(@c2) = split(/[._]/, $prim2);
   #
   # Check that leading non-numerical parts agree
   #
   if (!$suffix) {
      my($prefix) = "";
      if (@c1[0] =~ /^([^0-9]+)/) {
	 $prefix = $1;
	 
	 if (@c2[0] !~ /^$prefix/) {
	    return -1;
	 }
      } elsif (@c2[0] =~ /^([^0-9]+)/) {
	 $prefix = $1;

	 
	 if (@c1[0] !~ /^$prefix/) {
	    return -1;
	 }
      }

      @c1[0] =~ s/^$prefix//;
      @c2[0] =~ s/^$prefix//;      
   }

   my($n1, $n2); $n1 = @c1; $n2 = @c2;
   my($i, $n); $n = $n1 < $n2 ? $n1 : $n2;

   for ($i = 0; $i < $n; $i++) {
      if (@c1[$i] =~ /^\d*$/) { # numerical
	 if (@c1[$i] != @c2[$i]) {
	    return (@c1[$i] <=> @c2[$i]);
	 }
      } else {		# string
	 if (@c1[$i] ne @c2[$i]) {
	    return (@c1[$i] cmp @c2[$i]);
	 }
      }
   }
   # So far, the two versions are identical.  The longer version should sort later
   return ($n1 <=> $n2);
}

sub eups_version_match($$) {
   #
   # Return $vname if it matches the logical expression @expr
   #
   my($vname, $expr) = @_;

   my(@expr) = grep(!/^$/, split(/\s*($relop_re|\|\|)\s*/o, $expr));

   my($nprim, $i, $op, $v, $or);
   $or = 1;			# We are ||ing primitives
   $nprim = @expr;		# scalar context so length of list
   
   for ($i = 0; $i < $nprim; $i++) {
      if ($expr[$i] =~ /$relop_re/o) {
	 $op = $expr[$i++]; $v = $expr[$i];
      } elsif ($expr[$i] =~ /^[-+a-zA-Z0-9_.]+$/) {
	 $op = "==";
	 $v = $expr[$i];
      } elsif ($expr == "||") {
	 $or = 1;		# fine; that is what we expected to see
	 next;
      } else {
	 warn "Unexpected operator $expr[$i] in \"$expr\"\n";
	 last;
      }
      
      if ($or) {	# Fine;  we have a primitive to OR in
	 if (eups_version_match_prim($op, $vname, $v)) {
	    return $vname;
	 }
	 $or = 0;
      } else {
	 warn "Expected logical operator || in \"$expr\" at $v\n";
      }
   }

   return undef;
}

sub eups_version_match_prim {
   #
   # Compare two version strings, using the specified operator (< <= == >= >), returning
   # true if the condition is satisfied
   #
   # Uses eups_version_cmp to define sort order
   #
   my($op, $v1, $v2) = @_;

   if ($op eq "<") {
      return (eups_version_cmp($v1, $v2) <  0) ? 1 : 0;
   } elsif ($op eq "<=") {
      return (eups_version_cmp($v1, $v2) <= 0) ? 1 : 0;
   } elsif ($op eq "==") {
      return (eups_version_cmp($v1, $v2) == 0) ? 1 : 0;
   } elsif ($op eq ">") {
      return (eups_version_cmp($v1, $v2) >  0) ? 1 : 0;
   } elsif ($op eq ">=") {
      return (eups_version_cmp($v1, $v2) >= 0) ? 1 : 0;
   } else {
      warn("Unknown operator $op used with $v1, $v2--- complain to RHL\n");
   }
}

sub eups_setup {

   use File::Spec::Functions;
   use File::Basename;
   
   local $indent = $indent + 1;
   
   # Need to extract the parameters carefully
   local ($args, $outfile, $no_dependencies, $only_dependencies, $flags,
	  $_user_table_file, $debug, $quiet, $optional, $oldenv, $force) = @_;
   my($user_table_file) = $_user_table_file; undef($_user_table_file);

   my $qaz = $args;
   $args =~ s/\-[a-zA-Z]\s+[^ ]+//g;
   @args = split " ",$args;
   $prod = $args[0]; shift(@args);
   # Extract version info if any
   my($vers) = $args[0]; shift(@args);
   if ($vers =~ /$relop_re/ && defined($args[0])) {
      $vers .= " " . join(" ", @args);
   } elsif ($args[0]) {
      warn "WARNING: ignoring extra arguments: @args\n";
   }
   
   my($initial_eups_path) = $ENV{"EUPS_PATH"}; # needed if we are setting up eups
   if (!$user_table_file) {
      if ($prod eq "") {
	 print STDERR  "ERROR: Product not specified; try -h to list your options\n";
	 return -1;
      }
      
      # Attempt an unsetup
      
      my($SETUP_PROD) = "SETUP_".uc($prod);
      if (defined($ENV{$SETUP_PROD})) {
	 eups_unsetup($qaz, $outfile, $no_dependencies, 0, $flags, undef, $debug, 1);
	 
	 if (defined(%unsetup_products)) {	# we used this to suppress warning if products were unset twice
	    undef(%unsetup_products);
	 }
      }
   }
   
   #Determine flavor - first see if specified on command line
   #else get it from the environment EUPS_FLAVOR
   # We want this to propagate to subproducts
   ($flavor) = $qaz =~ m/\-f  *([^ ]+)/;
   $flavor = $ENV{"EUPS_FLAVOR"} if ($flavor eq ""); 
   if ($flavor eq "") {
      print STDERR "ERROR: No flavor specified, Use -f or set EUPS_FLAVOR\n";
      return -1;
   }
   $ENV{"EUPS_FLAVOR"} = $flavor; 	# propagate to sub-products

   #Fetch all the eups roots
   my $root = "";
   @roots = eups_find_roots($initial_eups_path);
   
   # Now check to see if the table file and product directory are 
   # specified. If so, extract these and immediately start, else 
   # complain 
   $table_file = "";
   $prod_dir = "";
   $ups_dir = "";
   ($prod_dir) = $qaz =~ m/\-r  *([^ ]+)/;
   
   if ($user_table_file) {
      ($root, $prod_dir, $vers, $table_file) =
	  ("none", undef, undef, $user_table_file);
      warn "Using $table_file rather than a declared product\n" if ($debug > 0);
   } elsif ($prod_dir eq "") {
      #Determine version - check to see if already defined, otherwise
      #determine it from current.chain
      #Also construct the full version file and check if it exists.
      my($ivers) = $vers;
      ($root, $prod_dir, $vers, $table_file) =
	  find_best_version(@roots, $prod, $vers, $$flags{ignore_versions}, $flavor,0);
      if (not $root) {
	 my($msg);
	 if ($ivers) {
	    $msg = "product $prod with version $ivers cannot be found.";
	 } else {
	    $msg = "no version of product $prod is declared current.";
	 }

	 if ($optional) {
	    warn "WARNING: $msg\n" if ($debug > 1);
	 } else {
	    warn "WARNING: $msg\n";
	    return -1;
	 }
      }
   } else {
      if ($prod_dir !~ m|^/|) {
	 use Cwd;
	 if ($prod_dir eq ".") {
	    $prod_dir = getcwd();
	 } else {
	    $prod_dir = catfile(getcwd(), $prod_dir);
	 }
	 # handle "setup -r ../../foo"
	 while ($prod_dir =~ s|[^/]+/\.\./||) {
	    ;
	 }
      }

      if (! -d $prod_dir) {
	 warn "FATAL ERROR: directory $prod_dir doesn't exist\n";
	 return -1;
      }

      # In case anyone cares which root -r shadows, try to find a matching version.
      ($Xroot, $Xprod_dir, $Xvers, $Xtable_file) =
	  find_best_version(@roots, $prod, $vers, $$flags{ignore_versions}, $flavor, 1);
      if (not $Xroot) {
	  $root = $roots[0];
      } else {
	  #$vers = $Xvers;
	  $root = $Xroot;
      }
      
      # Yuck. All this should be controllable with eups_declare\'s table file machinery.
      $table_file = "$prod.table";
      $table_file = catfile("ups",$table_file);
      if (!($prod_dir =~ m"^/")) {
	 $prod_dir = catfile($root,$prod_dir);
      }
      if (!($table_file =~ m"^/")) {
	 $table_file = catfile($prod_dir,$table_file);
      }
      
      if ($table_file ne "" && $debug >= 1) {
	 print STDERR "WARNING: Using table file $table_file\n";
	 $vers = "LOCAL:$prod_dir";
      }
   } 

   if (($debug >= 1 && !$quiet) || $debug > 1) {
      if (defined($prod)) {
	 if ($debug > 1 || !defined($setupVersion{$prod})) {	     
	    show_product_version("Setting up", $indent, $prod, $vers, $flavor);
	 }
      }
   }
   if (!defined($setupVersion{$prod})) {
      $setupVersion{$prod} = $vers;
   } else {
      if ($setupVersion{$prod} ne $vers) {
	 print STDERR "WARNING: You setup $prod $setupVersion{$prod}, and are now setting up $vers \n";
      }
      $setupVersion{$prod} = $vers;
   }
   
   if ($table_file !~ /^none$/i && !(-e $table_file)) {
      print STDERR "ERROR: Missing table file $table_file\n" if ($debug >= 1);
      return -1;
   }

   #Call the table parser here 
   $fwd = 1;
   return parse_table($table_file,$prod_dir,$ups_dir,$prod,$vers,$flavor,
		      $root,$fwd,$outfile,$only_dependencies,$$flags{build},$quiet);
}

###############################################################################
#
# Parse the SETUP_PROD environment variable for product $prod
#
sub parse_setup_prod {
   my($prod) = @_;
   
   my($key) = "SETUP_\U$prod";
   $args = $ENV{$key};
   if ($args eq "") {
      return (undef, undef, undef, undef)
   }

   # Now parse the string
   my($prod, $vers, $flavor, $z, $root) = ($args =~ /^\s*(\S+)\s+(\S*)\s*-f\s+(\S+)\s+-([zZ])\s+(\S+)/);

   return ("ok", $vers, $flavor, $root);
}

###############################################################################

sub eups_find_prod_dir {
   my($root, $flavor, $prod, $vers) = @_;
   
   $fn = catfile($root,'ups_db',$prod,"$vers.version");

   my ($prod_dir, $table_file) = read_version_file($root,$fn, $prod, $flavor, 0, 0);
   return $prod_dir;
}

###############################################################################

sub eups_list {

   use File::Spec::Functions;
   use File::Basename;

# Need to extract the parameters carefully
   local ($args,$outfile,$debug,$quiet,$current, $setup, $just_directory, $just_tablefile) = @_;

   my $qaz = $args;
   $args =~ s/\-[a-zA-Z]\s+[^ ]+//g;
   @args = split " ",$args;
   $prod = $args[0]; shift(@args);
   my($version) = $args[0]; shift(@args);
   if ($args[0]) {
      warn "WARNING: ignoring extra arguments: @args\n";
   }

#Determine flavor - first see if specified on command line
#else get it from the environment EUPS_FLAVOR

   ($flavor) = $qaz =~ m/\-f  *([^ ]+)/;
   $flavor = $ENV{"EUPS_FLAVOR"} if ($flavor eq ""); 
   if ($flavor eq "") {
      warn "ERROR: No flavor specified, Use -f or set EUPS_FLAVOR\n";
      return -1;			# 
   }					# 

   #
   # Did they specify a product?
   #
   my($one_product) = 1;	# did they just ask about one product?
   my($setup_prod_dir);
   if ($prod) { 
      $setup_prod_dir = $ENV{uc($prod) . "_DIR"};
   } else {
      $one_product = 0;
   }

   #Determine database

   my($printed_current) = 0; # did I print current/directory/tablefile for them?
   my($found_prod_dir) = 0;	# Have I found the setup PRODUCT_DIR somewhere on EUPS_PATH?
   my($found_product) = 0; # Have I found a reference to the requested product?
   
   foreach $root (eups_find_roots()) {
       $db = catfile($root, 'ups_db');

       if ($prod eq "") {
	   if (!opendir(DB, $db)) {
	       warn "ERROR: Unable to get list of products from $db\n";
	       return;
	   }
	   @products = grep(/^[^.].*$/, sort(readdir DB));
	   closedir DB;
       } else {
	   @products = ($prod);
       }
       #
       # Find the current version
       #
       foreach $prod (@products) {
	   $fn = catfile($db,$prod,"current.chain");
	   if (-e $fn) {
	       $current_vers = read_chain_file($fn, $flavor, 1);
	   } else {
	      $current_vers = "";
	   }
	   
	   # Look through directory searching for version files

	   $setup_prod_dir = $ENV{uc($prod) . "_DIR"};
	   foreach $file (glob(catfile($db,$prod,"*.version"))) {
	       ($vers = basename($file)) =~ s/\.version$//;

	       if ($version and !eups_version_match($vers, $version)) {
		  next;
	       }
	       
	       my ($prod_dir, $table_file) = read_version_file($root, $file, $prod, $flavor, 0, 1);
	       if (not $prod_dir) {
		   next;
	       }
	       $found_product = 1;
	       
	       $info = "";
	       if ($current_vers && $vers eq $current_vers) {
		   $printed_current = 1;
		   $info .= " Current";
	       } elsif($current) {
		   next;
	       }
	       if ($prod_dir eq $setup_prod_dir) {
		   $found_prod_dir = 1;
		   $info .= " Setup";
	       } elsif($setup) {
		   next;
	       }
	       
	       $vers = sprintf("%-10s", $vers);
	       if ($debug) {
		   $vers .= sprintf("\t%-20s\t%-30s", $root, $prod_dir);
	       }
	       
	       if ($info) {
		   $info = "\t\t$info";
	       }
	       
	       if ($just_directory || $just_tablefile) {
		  if ($just_directory) {
		     my($dir) = $prod_dir;
		     if ($dir eq "none") {
			$dir = "";
		     }
		     print $outfile "echo \"$dir\"\n";
		  }
		  if ($just_tablefile) {
		     print $outfile "echo \"$table_file\"\n";
		  }
	       } else {
		  my($msg) = "";
		  if(!$one_product) {
		     $msg .= sprintf("%-20s", $prod);
		  }
		  print $outfile "echo \"$msg   ${vers}$info\"\n";
	       }
	   }
       }
   }
   #
   # Look for any products that are setup locally (i.e. via --root)
   #
   if (!$one_product) {
      foreach $key (keys %ENV) {
	 if($key =~ /^([A-Z_]+)_DIR$/) {
	    my($prod) = $1;
	    if ($ENV{"SETUP_$prod"} =~ /LOCAL:/) {
	       my($msg) = print_local_product(sprintf("%-20s", "\L$prod"),
					       $ENV{$key}, $just_directory, $just_tablefile);
	       print $outfile "echo \"$msg\"\n";
	    }
	 }
      }
   }

   if($current && $one_product && !$printed_current) {
      warn "No version is declared current\n";
   }

   if (!$current && !$version && $one_product && !$found_prod_dir) { # we haven't seen the directory that's actually setup; must be declared -r
      if (!$setup_prod_dir) {		# not setup in environment
	 if (!$found_product && !$quiet) {
	    warn "I don't know anything about product \"$prod\"\n";
	 }
      } else {			# yes; it's setup
	 my($msg) = print_local_product("", $setup_prod_dir, $just_directory, $just_tablefile);
	 print $outfile "echo \"$msg\"\n";
      }
   }
}

#
# Print the properties of a product found only in the environment
#
sub print_local_product($$$$)
{
   my($prod_name, $prod_dir, $just_directory, $just_tablefile) = @_;

   if ($just_directory) {
      return $prod_dir;
   } elsif ($just_tablefile) {
      my($table_file) = "$prod_dir/ups/$prod.table"; # just an inspired guess
      if (-f $table_file) {
	 return $table_file;
      }
   } else {
      my($info) = "\t\t Setup";
      my($vers) = sprintf("%-10s", "LOCAL:$prod_dir");
      if ($debug) {
	 $vers .= sprintf("\t%-20s\t%-30s", "LOCAL", $prod_dir);
      }
      return "$prod_name   ${vers}$info";
   }
}

###############################################################################
#
# Read and parse current.chain file
#
sub read_chain_file
{
   my($fn, $flavor, $quiet) = @_;

   if (!(-e $fn)) {
      print STDERR "ERROR: No version or current.chain\n" if ($debug >= 1);
      return "";
   }
   my $versinfo;
   my @size = stat($fn);
   open FILE, "<$fn";
   read FILE, $versinfo, $size[7];
   close FILE;
# Now strip out all comments
   $versinfo =~ s/\#.*\n//g;
   $versinfo =~ s/flavor/##FLAVOR/gsi;
   my @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
# Match the last flavor
   my @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
   my @group = (@groups2,@groups3);
#Now find the appropriate group
   $flavor = fix_special($flavor);
   my $pattern = "FLAVOR *= *$flavor( |\n)";
   my $pattern2 = "FLAVOR *= *ANY( |\n)";
   my $pattern3 = "FLAVOR *= *NULL( |\n)";

   my $pos = -1;
   for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
      $pos = $i if ($group[$i] =~ m/$pattern/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
   }
   if ($pos == -1) {
      print STDERR "ERROR: Flavor $flavor not found in chain file $fn\n" if ($debug >= 3 + $quiet);
      return "";
   }
   ($vers) = $group[$pos] =~ m/VERSION *= *(.+?) *\n/i;

   return $vers;
}

###############################################################################
# read in the version file and start to parse it
#
sub read_version_file($$$$$$)
{
   my ($root, $fn, $prod, $flavor, $useenv, $quiet) = @_;
   my $dbdir = "$root/ups_db";

   if (!(open FILE,"<$fn")) {
      print STDERR "ERROR: Cannot open version file $fn\n" if ($debug >= 1);
      return undef, undef;
   }
   my @size = stat($fn);
   my $versinfo;
   
   # print STDERR "reading version file: $root, $fn, $prod, $flavor, $quiet\n";

   read FILE,$versinfo,$size[7];
   close FILE;
   # Now strip out all comments
   $versinfo =~ s/\#.*\n//g;
   # Extract the groups - either defined by group-end or between two flavors
   my(@groups) = $versinfo =~ m/group:(.+?)end:/gsi;
   $versinfo =~ s/group:(.+?)end://gsi;
   $versinfo =~ s/flavor/##FLAVOR/gsi;
   @groups2 = $versinfo =~ m/#(flavor.+?)#/gsi;
   # Match the last flavor
   @groups3 = $versinfo =~ m/.*(flavor.+\Z)/gsi;
   @group = (@groups,@groups2,@groups3);

   #Now find the appropriate group
   $pos = -1;
   $flavor = fix_special($flavor);
   $pattern = "FLAVOR *= *$flavor( |\n)";
   my $pattern2 = "FLAVOR *= *ANY( |\n)";
   my $pattern3 = "FLAVOR *= *NULL( |\n)";
   for ($i = 0; ($i<@group)&&($pos==-1);$i++) {
      $pos = $i if ($group[$i] =~ m/$pattern/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern2/gsi);
      $pos = $i if ($group[$i] =~ m/$pattern3/gsi);
   }
   if ($pos == -1) {
      print STDERR "ERROR: Flavor $flavor not found in version file $fn\n" if (!$quiet && $debug >= 1);
      return undef, undef;
   }

   # Now extract the prod_dir and table_file
   my($prod_dir)  = $group[$pos] =~ m/PROD_DIR[ \t]*=[ \t]*(\S*)/i;
   my($table_file) = $group[$pos] =~ m/TABLE_FILE[ \t]*=[ \t]*(\S*)/i;
   my($ups_dir) = $group[$pos] =~ m/UPS_DIR[ \t]*=[ \t]*(\S*)/i;
   $ups_dir = "ups" if (not $ups_dir);

   # Does the product directory have an environment variable set in it?
   @env = $prod_dir =~ m/\$\{(.+?)\}/g;
   for ($i = 0; $i < @env; $i++) {
      $val = $ENV{"$env[$i]"};
      $prod_dir =~ s/\$\{$env[$i]\}/$val/g;
   }
   if (!$prod_dir) {
      $prod_dir = $root;
   } elsif (!($prod_dir =~ m"^/") && $prod_dir ne "none") {
      $prod_dir = catfile($root,$prod_dir);
   }
   
   # Should we overwrite anything we have learnt about $proddir
   # from the PRODUCT_DIR environment variable?
   if ($useenv) {
       my $proddir_envname = uc($prod) . "_DIR";
       if ($ENV{$proddir_envname}) {
	   $prod_dir = $ENV{$proddir_envname};
	   warn "INFO : using PRODUCT_DIR from the environment ($prod_dir)\n" if ($debug > 2);
       }
   }

   # Disgustingly specific interpolation. Do this after we have nailed down $prod_dir. 
   $ups_dir =~ s/\$UPS_DB/$dbdir/g;
   $ups_dir =~ s/\$PROD_DIR/$prod_dir/g;
   
   if (!($ups_dir =~ m"^/")) {
      $ups_dir = catfile($prod_dir,$ups_dir);
   }

   if ($table_file !~ /^none$/i) {
      $table_file = catfile($ups_dir,$table_file);
   }

   if ($table_file !~ /^none$/i and not -r $table_file) {
      warn "WARNING: table file $table_file is invalid or unreadable (referenced in $fn)\n";
   }

   return ($prod_dir, $table_file);
}

###############################################################################
#
# List (and mildly check) the eups directories
#
# If an argument is passed, is the value of EUPS_PATH
#
sub eups_find_roots() {
    my($rootstring) = @_;
    if (!$rootstring) {
       $rootstring = $ENV{EUPS_PATH};
    }

    if (!$rootstring) {
	return ();
    }

    my @rootlist = ();
    foreach $part (split(/:/, $rootstring)) {
	my $dbdir = $part . "/ups_db";
	if (not -d $dbdir) {
	    warn "ERROR: $part in \$EUPS_PATH does not contain a ups_db directory, and is being ignored";
	    next;
	}
	push(@rootlist, $part);
    }

    die "ERROR: no valid products root directory is defined\n" if ($#rootlist eq -1);

    return @rootlist;
}

###############################################################################

sub show_product_version
{
   my($str, $indent, $prod, $vers, $flavor) = @_;
   printf STDERR "%-14s %-20s  Flavor: %-10s Version: %s\n",
   sprintf("%s:", $str), sprintf("%*s%s", $indent, "", $prod) ,$flavor,
   ($vers eq "" ? "LOCAL" : $vers);
}

###############################################################################
#
# Parse arguments. Many are actually interpreted by eups_setup.pm
#
%longopts = (
	     '--current',	'-c',
	     '--database',	'-Z',
	     '--directory',	'-d',
	     '--only-dependencies', '-D',
	     '--select-db',	'-z',
	     '--flavor',	'-f',
	     '--force',		'-F',
	     '--help',		'-h',
	     '--ignore-versions', '-i',
	     '--just'	,	'-j',
	     '--list'	,	'-l',
	     '--noaction',	'-n',
	     '--table'	,	'-m',
	     '--quiet',		'-q',
	     '--root',		'-r',
	     '--setup',		'-s',
	     '--type',		'-t',
	     '--version',	'-V',
	     '--verbose',	'-v',
	     );

%aliasopts = (
	      '-C', '-c',
	      );

sub eups_parse_argv
{
   my($opts, $args, $words) = @_;
   
   while ($ARGV[0]) {
      if ($ARGV[0] !~ /^-/) {	# not an option
	 push(@$words, $ARGV[0]); shift @ARGV;
	 next;
      }
      
      $ropt = $opt = $ARGV[0]; shift @ARGV;
      
      if (defined($longopts{$opt})) {
	 $opt = $longopts{$opt};
      }
      if (defined($aliasopt{$opt})) {
	 $opt = $aliasopt{$opt};
      }
      
      if ($opt eq "-h") {
	 return "-h";
      } elsif (grep(/^$opt$/, keys(%$opts))) {
	 if ($$opts{$opt}) {	# require an argument
	    if (!defined($ARGV[0])) {
	       warn "You must specify a value with $ropt\n";
	       return -1;
	    }
	    $val = $ARGV[0]; shift @ARGV;
	 }
	 
	 if ($opt eq "-v") {
	    $ENV{"EUPS_DEBUG"}++;
	 } elsif ($opt eq "-V") {
	    my($version) = &get_version();
	    warn "Version: $version\n";
	    return -1;
	 } elsif ($opt eq "-Z") {
	    $ENV{"EUPS_PATH"} = $val;
	 } elsif ($opt eq "-z") {
	    # filter to PATH parts which contain a complete directory matching $match
	     my @newpath = ();
	     foreach $part (split(/:/, $ENV{EUPS_PATH})) {
		 if ($part =~ m@(^|/)$val(/|$)@) {
		     push(@newpath, $part);
		 }
	     }
	     $ENV{"EUPS_PATH"} = join(':', @newpath);
	 } else {
	    if ($$opts{$opt}) {	# push argument
	       push(@$args, $opt);
	       push(@$args, $val);
	       
	       $opts{$opt} = $val;
	    } else {
	       $opts{$opt} = 1;
	    }
	 }
      } else {			# unknown argument
	 warn "Unknown option: $ropt\n";
	 return -1;
      }
   }

   if ($ENV{"EUPS_PATH"} eq "") {
      if (!defined($opts{-r})) {
	 warn("WARNING: no product directories available (check eups path and the -Z/-z options)\n");
      }
   }


   return \%opts;
}

###############################################################################
#
# Get version number from cvs
#
sub
get_version()
{
   my($version) = '\$Name: not supported by cvs2svn $';	# 'version from cvs

   if ($version =~ /^\\\$[N]ame:\s*(\S+)\s*\$$/) {
      $version = $1;
   } else {
      $version = "(NOCVS)";
   }

   return $version;
}

###############################################################################

sub eups_setshell {
    use File::Basename;

    if (!defined($ENV{"SHELL"})) {
       warn "FATAL ERROR: environment variable \$SHELL is not defined\n";
       return undef;
    }

    my($shell) = basename($ENV{"SHELL"});

    # Do some quick translations
    $shell = "sh" if ($shell eq "bash");
    $shell = "csh" if ($shell eq "tcsh");

    if ($shell eq "") {
	print STDERR "ERROR : SHELL not set\n";
	return undef;

    } elsif (!(($shell eq "sh")||($shell eq "csh"))) {
	print STDERR "ERROR : Unknown shell $shell\n";
	return undef;
    }
    
    return $shell;
}

###############################################################################

sub eups_show_options
{
   my($opts, $command) = @_;	# "setup" => options for [un]setup etc.

   my $strings = {
       -h => "Print this help message",
       -c => ($command eq "setup") ? "Show current version" :
	   ($command eq "declare") ? "Declare this product current" :
	       "Declare this product to not be current",
       -d => "Print product directory to stderr (useful with -s)",
       -D => "Only setup dependencies, not this product",
       -f => "Use this flavor. Default: \$EUPS_FLAVOR or \`eups_flavor\`",
       -F => "Force requested behaviour (e.g. redeclare a product)",
       -i => "Ignore any explicit versions in table files",
       -j => "Just setup product, no dependencies",
       -l => "List available versions (-v => include root directories)",
       -n => "Don\'t actually do anything",
       -m => ($command eq "setup" ? "Print name of" : "Use"). " table file (may be \"none\") Default: product.table",
	       -M => $command eq "setup" ?
		   "Setup the dependent products in this table file" :
		       "Import the given table file directly into the database\n(may be \"-\" for stdin)",
       -q => "Be extra quiet",
       -r => "Location of product being " . ($command eq "setup"? "setup" : $command . "d"),
       -s => "Show which version is setup",
       -t => "Specify type of setup (permitted values: build)",
       -v => "Be chattier (repeat for even more chat)",
       -V => "Print eups version number and exit",
       -Z => "Use this products path. Default: \$EUPS_PATH",
       -z => "Select the product paths which contain this directory. Default: all",
    };

   foreach $key (keys %longopts) { # inverse of longopts table
      $rlongopts{$longopts{$key}} = $key;
   }

   my(%aliases);
   foreach $key (keys %aliasopts) {
      if (defined($$opts{$aliasopts{$key}})) {
	 $aliases{$key} = $aliasopts{$key};
      }
   }

   warn "Options:\n";

   foreach $opt ("-h", sort {lc($a) cmp lc($b)} (keys(%$opts), keys(%aliases))) {
      my($line) = "$opt";
      if (defined($rlongopts{$opt})) {
	 $line .= ", $rlongopts{$opt}";
      }
      if ($$opts{$opt}) {
	 $line .= " arg";
      }
	 
      my($descrip) = $$strings{$opt};
      if (!$descrip && defined($aliases{$opt})) {
	 $descrip = "Alias for $aliases{$opt}";
      }

      my(@details) = split("\n", $descrip);
      foreach (@details) {
	 printf STDERR "\t%-20s\t$_\n", "$line";
	 $line = "";
      }
   }
}

1;
