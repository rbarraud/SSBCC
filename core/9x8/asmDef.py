################################################################################
#
# Copyright 2012, Sinclair R.F., Inc.
#
# Collection of utilities for the assembler.
#
################################################################################

import re

################################################################################
#
# Iterator for files that returns bodies of lines of the file.  Each body
# contains optional comment lines preceding the directive, the line with the
# directive, and optional lines following the directive up to the optional
# comments preceding the next directive.
#
# The directive must be the first non-white spaces on a line.
#
# The iterator outputs a list whos first element is the line number for the
# first line of the block and whose subsequent elements are the lines with the
# content of the block.
#
# This iterator handles the ".include" directive.
#
################################################################################

class FileBodyIterator:

  def __init__(self, fps, ad):
    # Do sanity check on arguments.
    if ad.IsDirective(".include"):
      raise Exception('".include" directive defined by FileBodyIterator');
    # Initialize the raw processing states
    self.fpPending = list(fps);
    self.ad = ad;
    self.current = list();
    self.pending = list();
    # Prepare the file parsing
    self.included = list();
    for fp in self.fpPending:
      if fp.name in self.included:
        raise Exception('Input file %s listed more than once' % fp.name);
      self.included.append(fp.name);
    self.fpStack = list();
    self.fpStack.append(dict(fp=self.fpPending.pop(0), line=0));
    self.pendingInclude = str();

  def __iter__(self):
    return self;

  def next(self):
    # Discard the body emitted by the previous call.
    self.current = self.pending;
    self.pending = list();
    # Loop until all of the files have been processed
    while self.fpStack or self.fpPending or self.pendingInclude:
      # Ensure the bodies in closed files are all emitted before continuing to
      # the next/enclosing file.
      if 'closed' in self.fpStack[-1]:
        if self.current:
          return self.current;
        self.fpStack.pop();
        continue;
      # Handle a queued ".include" directive.
      if self.pendingInclude:
        # Don't open the include file until all previous content has been emitted.
        if self.current:
          return self.current;
        if self.pendingInclude in self.included:
          raise Exception('File "%s" already included' % self.pendingInclude);
        self.included.append(self.pendingInclude);
        fp_pending = open(self.pendingInclude,'r');
        self.fpStack.append(dict(fp=fp_pending, line=0));
        self.pendingInclude = str();
      # Get the next file to process if fpStack is empty.
      if not self.fpStack:
        self.fpStack.append(dict(fp=self.fpPending.pop(0),line=0));
      # Process/continue processing the top file.
      fp = self.fpStack[-1];
      for line in fp['fp']:
        fp['line'] = fp['line'] + 1;
        # Handle '.include' directives.
        if re.match(r'\s*\.include\s', line):
          a = re.findall(r'\s*\.include\s+(\S+)(\s*|\s*;.*)$', line);
          if not a:
            raise Exception('Malformed .include directive at %s(%d)' % (fp['fp'].name, fp['line']));
          if not self.pending:
            self.pending.append(fp['fp'].name);
            self.pending.append(fp['line']);
          self.pending.append(line);
          self.pendingInclude = a[0][0];
          if not self.current:
            self.current = self.pending;
            self.pending = list();
          return self.current;
        # Append empty and comment lines to the pending block.
        if re.match(r'\s*(;|$)', line):
          if not self.pending:
            self.pending.append(fp['fp'].name);
            self.pending.append(fp['line']);
          self.pending.append(line);
          continue;
        # See if the line starts with a directive.
        tokens = re.findall(r'\s*(\S+)',line);
        if self.ad.IsDirective(tokens[0]):
          if not self.pending:
            self.pending.append(fp['fp'].name);
            self.pending.append(fp['line']);
          self.pending.append(line);
          if self.current:
            return self.current;
          self.current = self.pending;
          self.pending = list();
          continue;
        # Otherwise, this line belongs to the body of the preceding directive.
        if not self.current:
          self.current += self.pending[0:1];
        self.current += self.pending[2:];
        self.current.append(line);
        self.pending = list();
      # Past the last line of the current file -- close it.
      self.fpStack[-1]['fp'].close();
      self.fpStack[-1]['closed'] = True;
      # Prepare to emit pending bodies if any.
      if not self.current:
        self.current = self.pending;
        self.pending = list();
    raise StopIteration;

################################################################################
#
# Extract the tokens from a block of code.
#
# These blocks of code should be generated by FileBodyIterator.
#
################################################################################

def RawTokens(filename,startLineNumber,lines,ad):
  """Extract the list of tokens from the provided list of lines"""

  tokens = list();
  lineNumber = startLineNumber - 1;
  for line in lines:
    lineNumber = lineNumber + 1;
    col = 0;
    spaceFound = True;
    while col < len(line):
      # TODO -- ensure tokens are separated by whitespace
      # ignore white-space characters
      if re.match(r'\s',line[col:]):
        spaceFound = True;
        col = col + 1;
        continue;
      if not spaceFound:
        raise Exception('Missing space in %s(%d), column %d' % (filename, lineNumber, col+1));
      spaceFound = False;
      # ignore comments
      if line[col] == ';':
        break;
      # look for decimal value
      a = re.match(r'([+\-]?[1-9]\d*|0)\b',line[col:]);
      if a:
        tokens.append(dict(type='value', value=int(a.group(0)), line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # look for an octal value
      # TODO -- get correct conversion function
      a = re.match(r'0[0-7]+\b',line[col:]);
      if a:
        tokens.append(dict(type='value', value=int(a.group(0),8), line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # look for a hex value
      # TODO -- get correct conversion function
      a = re.match(r'0x[0-9A-Fa-f]+\b',line[col:]);
      if a:
        tokens.append(dict(type='value', value=int(a.group(0)[2:],16), line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # capture double-quoted strings (won't capture embedded double quotes)
      # TODO -- improve double-quoted string capture and escape character interpretation
      if re.match(r'[CN]"',line[col:]):
        a = re.match(r'[CN]"([^"]|\\")+[^\\\\]"',line[col:]);
        if not a:
          raise Exception('Unmatched \'"\' in %s(%d), column %d' % (filename, lineNumber, col+1));
        tokens.append(dict(type='string', value=a.group(0)[1:len(a.group(0))-1], line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # capture single-quoted character
      if line[col] == "'":
        a = re.match(r'\'.\'',line[col:]);
        if (not a) or ((col+3 < len(line)) and (not re.match(r'\s',line[col+3]))):
          raise Exception('Malformed \'.\' in %s(%d), column %d' % (filename, lineNumber, col+1));
        tokens.append(dict(type='value', value=ord(a.group(0)[1]), line=lineNumber, col=col+1));
        col = col + 3;
        continue;
      # look for directives and macros
      a = re.match(r'\.[A-Za-z]\w*(\(\w+\))?',line[col:]);
      if a:
        if (col+len(a.group(0)) < len(line)) and (not re.match(r'\s',line[col+len(a.group(0))])):
          raise Exception('Malformed directive or macro in %s(%d), column %d' % (filename, lineNumber, col+1));
        b = re.match(r'\.[A-Za-z]\w*',a.group(0));
        if ad.IsDirective(b.group(0)):
          if b.group(0) != a.group(0):
            raise Exception('Malformed directive in %s(%d), column %d' % (filename, lineNumber, col+1));
          if len(tokens) > 0:
            raise Exception('Directive must be first entry on line in %s(%d), column %d' % (filename, lineNumber, col+1));
          tokens.append(dict(type='directive', value=a.group(0), line=lineNumber, col=col+1));
          col = col + len(a.group(0));
          continue;
        if ad.IsMacro(b.group(0)):
          if b.group(0) == a.group(0):
            macroArgs = list();
          else:
            macroArgs = re.findall(r'([^,)]+)',a.group(0)[len(b.group(0))+1:]);
          if len(macroArgs) != ad.MacroNumberArgs(b.group(0)):
            raise Exception('Wrong number of arguments to macro in %s(%d), column %d' % (filename, lineNumber, col+1));
          tokens.append(dict(type='macro', value=b.group(0), line=lineNumber, col=col+1, argument=macroArgs));
          col = col + len(a.group(0));
          continue;
        raise Exception('Unrecognized directive or macro "%s" in %s(%d), column(%d)' % (a.group(0), filename, lineNumber, col+1));
      # look for instructions
      a = re.match(r'\S+',line[col:]);
      if ad.IsInstruction(a.group(0)):
        tokens.append(dict(type='instruction', value=a.group(0), line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # look for a label definition
      a = re.match(r':[A-Za-z]\w*',line[col:]);
      if a:
        if (col+len(a.group(0))) and (not re.match(r'\s',line[col+len(a.group(0))])):
          raise Exception('Malformed label in %s(%d), column %d' % (filename, lineNumber, col+1));
        tokens.append(dict(type='label', value=a.group(0)[1:], line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # look for symbols
      # Note:  This should be the last check performed as every other kind of
      #        token should be recognizable
      a = re.match(r'[A-Za-z]\w+',line[col:]);
      if a:
        if (col+len(a.group(0))) and (not re.match(r'\s',line[col+len(a.group(0))])):
          raise Exception('Malformed symbol in %s(%d), column %d' % (filename, lineNumber, col+1));
        tokens.append(dict(type='symbol', value=a.group(0), line=lineNumber, col=col+1));
        col = col + len(a.group(0));
        continue;
      # anything else is an error
      raise Exception('Malformed statement in %s(%d), column %d' % (filename, lineNumber, col+1));
  return tokens;
