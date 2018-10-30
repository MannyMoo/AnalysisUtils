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
    returnval = {'stdout' : stdout, 'stderr' : stderr, 'exitcode' : exitcode}
    if 0 != exitcode and kwargs.get('raiseonfailure', True) :
        raise OSError('''Call to {0!r} failed!
Exit code: {1}
stdout:
'''.format(' '.join(args), returnval['exitcode']) + returnval['stdout'] + '''
stderr:
''' + returnval['stderr'])
    
    return returnval

def get_bk_decay_paths(evttype, exclusions = (), outputfile = None) :
    '''Get bk paths for the given event type, sorted by year. Paths 
    containing any of the regexes in 'exclusions' are removed. If
    'outputfile' is given, the return dict is written to that file.'''

    returnval = dirac_call('dirac-bookkeeping-decays-path', str(evttype))
    paths = [p for p in eval('[' + returnval['stdout'].replace('\n', ',') + ']')]
    paths = filter(lambda p : not any(re.search(excl, p[0]) for excl in exclusions), paths)
    paths = {p[0] : p[1:] for p in paths}
    pathsdict = defaultdict(set)
    for path in paths :
        pathsdict[path.split('/')[2]].add(path)
    _pathsdict = {}
    for year, _paths in pathsdict.items() :
        _pathsdict[year] = []
        for path in _paths :
            _pathsdict[year].append({'path' : path, 'dddbtag' : paths[path][0], 'conddbtag' : paths[path][1],
                                     'nfiles' : paths[path][2], 'nevents' : paths[path][3],
                                     'production' : paths[path][4]})
    if outputfile :
        with open(outputfile, 'w') as f :
            f.write('''# Evttype : {0}
# Exclusions : {1}
decaypaths = \\
{2}
'''.format(evttype, exclusions, pprint.pformat(_pathsdict)))
    return _pathsdict

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

def get_access_urls(lfns, outputfile = None, urls = None, protocol = 'xroot') :
    '''Get the access URLs for the given LFNs. Returns a dict of {LFN : [URLs]}. If 
    an existing dict 'urls' is given, it will attempt to update the URLs for
    LFNs that don't currently have any.'''

    # If an existing dict is given, just update the URLs for those that're missing.
    if urls :
        lfns = filter(lambda lfn : not urls.get(lfn, []), set(urls.keys() + lfns))
        for lfn in lfns :
            if not lfn in urls :
                urls[lfn] = []
    else :
        urls = {lfn : [] for lfn in lfns}
    returnval = dirac_call('dirac-dms-lfn-accessURL', '--Protocol=' + protocol, '-l', ','.join(lfns))
    lines = returnval['stdout'].splitlines()
    for iline, line in enumerate(lines) :
        if 'Successful' in line :
            break
    for line in lines[iline+1:] :
        line = line.strip()
        if not line.startswith('/lhcb') :
            continue
        lfn, url = line.split(' : ')
        urls[lfn.strip()].append(url.strip())
    if outputfile :
        with open(outputfile, 'w') as f :
            f.write('''urls = \\
''' + pprint.pformat(urls))
    print 'Got URLs for', str(sum(int(bool(url)) for url in urls.values())) + '/' + str(len(urls)), 'LFNs.'
    return urls
