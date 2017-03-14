"""
Merge.py
Read a *.s file generated by gcc -g and generate an annotated version of the
file by transcribing the corresponding lines of C before each block of assembly.

@author: Rob Whitaker
@date: Feb 2017
"""

import sys, re

separator = '### ' + ('-' * 68) + '\n'

def readfiles(fnames):
	""" Open each file specified in fnames and store it as a list
	of lines.  Return a list of lines for each c file as source,
	for the assembly file as asm, and the .s file's name as asmname.
	"""

	source = list()
	for name in fnames:
		if name.endswith('.c'):
			# List of lists of lines of c source by file
			with open(name, 'r') as file:
				source.append(file.readlines())
		elif name.endswith('.s'):
			asmname = name[:-2] + '-merged.s'
			# Assume single assembly file, save lines in list
			with open(name, 'r') as file:
				asm = file.readlines()

	return (source, asm, asmname)

def header(fname, author=''):
	""" Return header line with filename and spacers
	"""
	h = separator
	h += '### ' + fname
	h += '\n### Author: ' + author + '\n'

	return h


def save(lines, fname):
	""" Write each line of lines to file. Prepend with header.
	"""
	with open(fname, 'w') as file:
		# Write header
		file.write(header(fname))
		# Write body
		for line in lines:
			file.write(line)

def merge(asm, source):
	""" Process each line of assembly in asm and insert
	the corresponding lines of source where appropriate.
	Also remove extraneous/verbose/confusing lines of assembly.
	Return merged/process version as mergedlines.
	"""

	# Lines of processed version
	mergedlines = list()

	# List of lines of source that have been used
	used = list()

	# List of directives to keep
	whitelist = ['.section', '.globl', '.byte', '.word', \
		'.long', '.quad', '.type', '.asciz', '.string', '.skip']

	# Regular expression for removing comments
	comment = re.compile('##.*')
	empty = re.compile('^\s*$')
	labels = re.compile('^(Ltmp)|(Lfunc)')

	# Parse each line in assembly file
	for line in asm:
		# Strip comments
		line = comment.sub('', line)
		# Skip empty lines
		if empty.match(line) is not None: continue
		# Skip system-level labels
		if labels.match(line) is not None: continue

		# Find .loc directives
		if line.startswith('\t.loc'):
			mergedlines.append(loc(line, source))

		# Skip DWARF tree information at the end of the file
		elif '__DWARF' in line:
			break

		# Prune confusing directives
		elif line.startswith('\t.'):
			# Prepend new sections with divider
			if '.section' in line:
				mergedlines.append(separator)

			# Check for other allowed directives
			for directive in whitelist:
				if directive in line:
					mergedlines.append(line)

		# Keep all other nonempty lines
		else:
			if line: mergedlines.append(line)

	return mergedlines

def loc(line, source):
	""" Process a line with a .loc directive and return
	the corresponding line or lines of C as assembly comments.
	"""

	# Initialize list of used lines
	if not hasattr(loc, 'used'):
		loc.used = []

	# split .loc and arguments
	tokens = line.split()

	# parse file number and line number from directive
	f = int(tokens[1])
	l = int(tokens[2])

	# keep track of file-line pairs to not repeat
	if (f,l) in loc.used: return ''
	else: loc.used.append((f,l))

	# find line of c
	cline = source[f-1][l-1]

	# further investigate cline to make sure it's what we should write
	if cline.strip() == '{':
		cline = '\n\t## ' + source[f-1][l-2] + '\t## ' + cline
	else:
		cline = '\n\t## ' + cline

	return cline

if __name__ == "__main__":

	# Get filename from stdin
	fnames = sys.stdin.read().split()

	# Read files
	(source, asm, name) = readfiles(fnames)

	# List of lines of code to gather
	mergedlines = merge(asm, source)

	save(mergedlines, name)

