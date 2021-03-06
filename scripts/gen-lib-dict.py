#!/usr/bin/env python

'''Generate the xml and header file for the python bindings dictionary from a shared library (kind of works).'''

import subprocess, os

def gen_dict(libname, headersdirs, rootdir, xmlfile, headerfile) :
    '''Generate the xml and header file from a library.
    libname = path to the library. It should be built with debugging info.
    headersdir = directory to find shared headers.
    xmlfile = the name of the output xml file.
    headerfile = the name of the output header file.'''

    if isinstance(headersdirs, str) :
        headersdirs = (headersdirs,)

    args = ['nm', '-D', '--defined-only', '--demangle', '--line-numbers', libname]
    proc = subprocess.Popen(args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if 0 != proc.poll() :
        raise OSError('Failed to call ' + ' '.join(args) + '! Exit code: ' + str(proc.poll())
                      + '\nstdout:\n' + stdout + '\nstderr:' + stderr)
    symbols = {}
    for line in stdout.splitlines() :
        #if not ' T ' in line :
        #    continue
        try :
            splitline = line.split()
            name = splitline[2]
            fname = splitline[-1]
        except IndexError :
            continue
        if not '(' in name or name.startswith('operator') :
            continue
        name = name.split('(')[0]
        symbols[name] = fname

    for name in list(symbols) :
        if not name in symbols :
            continue
        if not '::' in name :
            continue
        splitname = name.split('::')
        if splitname[-2] != splitname[-1] and not splitname[-1].startswith('~') :
            continue
        start = '::'.join(splitname[:-1])
        for othername in list(symbols) :
            if othername == name :
                continue
            if '::'.join(othername.split('::')[:-1]) == start :
                del symbols[othername]

    funcs = {}
    classes = {}
    for name, fname in symbols.items() :
        fname = fname.split(':')[0]
        fname = os.path.split(fname)[1]
        hname = ''
        __hname = '.'.join(fname.split('.')[:-1]) + '.h'
        for headersdir in headersdirs :
            _hname = os.path.join(headersdir, __hname)
            if os.path.exists(_hname) :
                hname = _hname
                break
        if not hname :
            continue
        print fname, hname, os.path.relpath(hname, rootdir)
        splitname = name.split('::')
        if '::' in name and (splitname[-2] == splitname[-1] or splitname[-1].startswith('~')) :
            classes['::'.join(splitname[:-1])] = hname
        else :
            funcs[name] = hname

    with open(xmlfile, 'w') as xmlfile :
        xmlfile.write('<lcgdict>\n')
        for functype, names in ('class', classes), ('function', funcs) :
            for name in sorted(names) :
                xmlfile.write('  <{0} name="{1}" />\n'.format(functype, name))
        xmlfile.write('</lcgdict>\n')
    
    defname = os.path.split(headerfile)[1].replace('.', '_').upper()
    addedheaders = set()
    with open(headerfile, 'w') as headerfile :
        headerfile.write('''#ifndef {0}
#define {0}

#include <map>
#include <string>
#include <vector>
'''.format(defname))
        for functype, names in ('class', classes), ('function', funcs) :
            for name, headername in names.items() :
                headername = os.path.relpath(headername, rootdir)
                print 'Add', functype, name, 'from', headername
                if headername in addedheaders :
                    continue
                addedheaders.add(headername)
                headerfile.write('#include <{0}>\n'.format(headername))
        headerfile.write('#endif\n')
        
if __name__ == '__main__' :
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('lib', help = 'Library to examine (should be built with debug info).')
    parser.add_argument('xmlfile', help = 'Output xml file name')
    parser.add_argument('headerfile', help = 'Output header file name')
    parser.add_argument('rootdir', help = 'Root directory to take header paths wrt.')
    parser.add_argument('headersdirs', nargs = '+', help = 'Directory containing header files.')
    args = parser.parse_args()
    gen_dict(args.lib, args.headersdirs, args.rootdir, args.xmlfile, args.headerfile)
