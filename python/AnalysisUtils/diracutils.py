import subprocess, re, pprint
from collections import defaultdict

def dirac_call(*args) :
    '''Call something in the LHCbDirac environment and capture the stdout, stderr
    and exit code.'''

    proc = subprocess.Popen(('lb-run', 'LHCbDirac/prod') + args,
                            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    exitcode = proc.poll()
    return {'stdout' : stdout, 'stderr' : stderr, 'exitcode' : exitcode}

def get_bk_decay_paths(evttype, exclusions = (), outputfile = None) :
    '''Get bk paths for the given event type, sorted by year. Paths 
    containing any of the regexes in 'exclusions' are removed. If
    'outputfile' is given, the return dict is written to that file.'''

    returnval = dirac_call('dirac-bookkeeping-decays-path', str(evttype))
    if returnval['exitcode'] != 0 :
        raise OSError('''Call to dirac-bookkeeping-decays-path failed!
stdout:
''' + returnval['stdout'] + '''
stderr:
''' + returnval['stderr'])
    paths = [p[0] for p in eval('[' + returnval['stdout'].replace('\n', ',') + ']')]
    paths = filter(lambda p : not any(re.search(excl, p) for excl in exclusions), paths)
    pathsdict = defaultdict(set)
    for path in paths :
        pathsdict[path.split('/')[2]].add(path)
    pathsdict = dict((year, list(paths)) for year, paths in pathsdict.items())
    if outputfile :
        with open(outputfile, 'w') as f :
            f.write('''# Evttype : {0}
# Exclusions : {1}
decaypaths = \\
{2}
'''.format(evttype, exclusions, pprint.pformat(pathsdict)))
    return pathsdict
