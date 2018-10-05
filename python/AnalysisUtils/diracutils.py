import subprocess, re, pprint
from collections import defaultdict

def dirac_call(*args, **kwargs) :
    '''Call something in the LHCbDirac environment and capture the stdout, stderr
    and exit code. By default an exception is raised if the exit code of the call
    isn't zero. This can be overridden by passing raiseonfailure = False.'''

    proc = subprocess.Popen(('lb-run', 'LHCbDirac/prod') + args,
                            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    exitcode = proc.poll()
    if 0 != exitcode and kwargs.get('raiseonfailure', True) :
        raise OSError('''Call to {0!r} failed!
stdout:
'''.format(' '.join(args)) + returnval['stdout'] + '''
stderr:
''' + returnval['stderr'])
    
    return {'stdout' : stdout, 'stderr' : stderr, 'exitcode' : exitcode}

def get_bk_decay_paths(evttype, exclusions = (), outputfile = None) :
    '''Get bk paths for the given event type, sorted by year. Paths 
    containing any of the regexes in 'exclusions' are removed. If
    'outputfile' is given, the return dict is written to that file.'''

    returnval = dirac_call('dirac-bookkeeping-decays-path', str(evttype))
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

def get_lfns(*args, **kwargs) :
    '''Get the LFNs from the given BK query. If the keyword arg 'outputfile' is given,
    the LFNs are saved as an LHCb dataset to that file.'''
    
    result = dirac_call('dirac-bookkeeping-get-files', *args)
    lfns = filter(lambda line : line.startswith('/lhcb'), result['stdout'].splitlines())
    lfns = [lfn.split()[0] for lfn in lfns]
    if not kwargs.get('outputfile', None) :
        return lfns
    with open(kwargs['outputfile'], 'w') as f :
        f.write('''# lb-run LHCbDirac/prod dirac-bookkeeping-get-files {0}

from Gaudi.Configuration import *
from GaudiConf import IOHelper
IOHelper('ROOT').inputFiles(
{1},
clear=True)
'''.format(' '.join(args), pprint.pformat(['LFN:' + lfn for lfn in lfns])))
        
    return lfns

def get_lfns_from_path(path, outputfile = None) :
    '''Get the LFNs from the given BK path.'''
    return get_lfns('-B', path, outputfile = outputfile)
                
def get_step_info(stepid) :
    '''Get info on the given production step.'''
    
    args = ['python', '-c', '''
import sys, subprocess
from DIRAC.Core.Base.Script import parseCommandLine
parseCommandLine() # Need this for some reason.
from LHCbDIRAC.BookkeepingSystem.Client.BookkeepingClient import BookkeepingClient

bk = BookkeepingClient()
stepid = '%s'
info = bk.getAvailableSteps({'StepId' : stepid})
info = dict(zip(info['Value']['ParameterNames'], info['Value']['Records'][0]))
print repr(info)
''' % stepid]
    result = dirac_call(*args)
    info = eval(result['stdout'])
    return info
