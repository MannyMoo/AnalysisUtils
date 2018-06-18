#!/bin/env python

from TCKUtils import utils as tckutils
from argparse import ArgumentParser
from pprint import pprint, pformat

def version_sort_key(ver, nmax = 4) :
    '''Predicate to sort version strings.'''
    ver = ver.split('_')[-1]
    ver = ver.split('r')
    v = ver[0].zfill(nmax)
    if len(ver) > 1 :
        r = ver[1].zfill(nmax)
        ver = ver[1].split('p')
    else :
        r = '0' * nmax
    if len(ver) > 1 :
        p = ver[1].zfill(nmax)
    else :
        p = '0' * nmax
    return v + r + p

def output(obj, outputfile) :
    if outputfile :
        with open(outputfile, 'w') as f :
            if isinstance(obj, str) :
                f.write(obj)
            else :
                f.write(pformat(obj))
        print 'Written to', outputfile
    else :
        if isinstance(obj, str) :
            print obj
        else :
            pprint(obj)

def tcks(mooreversion, hlttype) :
    return tuple(sorted(tckutils.getTCKs(mooreversion, hlttype), key = (lambda x : x[0])))

def hlttypes(mooreversion) :
    hlttypes = sorted(tckutils.getHltTypes(mooreversion))
    if not hlttypes :
        return None
    typesdict = []
    for hlttype in hlttypes :
        #typesdict[hlttype] = tcks(mooreversion, hlttype)
        typesdict.append((hlttype, tcks(mooreversion, hlttype)))
    return tuple(typesdict)

def mooreversions() :
    versions = sorted(tckutils.getReleases(), key = version_sort_key)
    versionsdict = []
    for version in versions :
        #versionsdict[version] = hlttypes(version)
        versionsdict.append((version, hlttypes(version)))
    return tuple(versionsdict)

def main() :
    argparser = ArgumentParser()
    argparser.add_argument('--tck', default = None,
                           help = '''If given, list HLT1 & HLT2 lines for the given TCK.
Overrides --mooreversion and --hlttype.''')
    argparser.add_argument('--mooreversion', default = None,
                           help = '''If not given (without --tck), output all Moore versions, HLT types & TCKs.
If given without --hlttype, output HLT types & TCKs for the given version.
If given with --hlttype, output TCKs for the given version & HLT type.''')
    argparser.add_argument('--hlttype', default = None,
                           help = '''If given with --mooreversion, output TCKs for the given version & HLT type.''')
    argparser.add_argument('--outputfile', default = None,
                           help = 'Name of file to which to write output. If None the output is printed to the console')

    args = argparser.parse_args()

    if None != args.tck :
        hlt1lines = [line.replace('Hlt::Line/', '') for line in \
                         tckutils.getHlt1Lines(int(args.tck, 16))]
        hlt2lines = [line.replace('Hlt::Line/', '') for line in \
                         tckutils.getHlt2Lines(int(args.tck, 16))]
        lines = {'Hlt1' : hlt1lines,
                 'Hlt2' : hlt2lines}
        print 'HLT lines for tck', args.tck
        output(lines, args.outputfile)
        return
    if None != args.mooreversion :
        if None != args.hlttype :
            tckslist = tcks(args.mooreversion, args.hlttype)
            print 'TCKs for Moore version', args.mooreversion
            output(tckslist, args.outputfile)
            return
        types = hlttypes(args.mooreversion)
        if not types :
            print 'No hlt types for', args.mooreversion
            print '--mooreversion must be one of:'
            pprint(sorted(tckutils.getReleases(), key = version_sort_key))
            return
        print 'Hlt types for', args.mooreversion
        output(types, args.outputfile)
        return
    print 'Moore versions:'
    versions = mooreversions()
    output(versions, args.outputfile)

if __name__ == '__main__' :
    main()
        
    
