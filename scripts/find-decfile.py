#!/usr/bin/env python

import os, subprocess, argparse

argparser = argparse.ArgumentParser()
argparser.add_argument('expr', help = 'Regex to search for in decfiles, can be, eg, event type, decay descriptor, etc')
argparser.add_argument('-v', '--version', help = 'Version of DecFiles to use. Default is whatever\'s used for the '
                       'current software stack. Can be \'latest\' to use the latest release.', default = None)

def version(v):
    '''Get a list of [version, revision, patch].'''
    v = v.split('p')
    l = []
    if len(v) > 1:
        l.insert(0, int(v[1]))
    else:
        l.insert(0, 0)
    v = v[0].split('r')
    l.insert(0, int(v[1]))
    l.insert(0, int(v[0][1:]))
    return l

args = argparser.parse_args()
if not args.version:
    path = os.path.expandvars('$DECFILESROOT/')
elif args.version.lower() == 'latest':
    path = os.path.expandvars('$LHCb_release_area/DBASE/Gen/DecFiles/')
    versions = sorted(os.listdir(path), key = version)
    path = os.path.join(path, versions[-1])
else:
    path = os.path.join(os.path.expandvars('$LHCb_release_area/DBASE/Gen/DecFiles/'), args.version)

decfiles = os.path.join(path, 'dkfiles/*.dec')
print 'Searching', decfiles
args = ['grep', '-H', '-i', args.expr, decfiles]
subprocess.call(' '.join(args), shell = True)
