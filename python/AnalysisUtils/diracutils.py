import subprocess, re, pprint, os
from collections import defaultdict

def dirac_call(*args, **kwargs) :
    '''Call something in the LHCbDirac environment and capture the stdout, stderr
    and exit code. By default an exception is raised if the exit code of the call
    isn't zero. This can be overridden by passing raiseonfailure = False.'''

    # proc = subprocess.Popen(('lb-run', 'LHCbDirac/prod') + args,
    #                         stdout = subprocess.PIPE, stderr = subprocess.PIPE)

    env = {k : os.environ[k] for k in ('HOME', 'TERM', 'USER')}
    env['PATH'] = '/usr/sue/bin:/bin:/usr/bin:/usr/sbin:/sbin'

    proc = subprocess.Popen(('which', 'LbLogin.sh'),
                            stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    lblogin = stdout.strip()

    cmd = '''. {0} >& /dev/null
lb-run -c best LHCbDirac/prod {1}'''.format(lblogin,
                                            ' '.join(repr(arg) for arg in args))

    proc = subprocess.Popen(('bash', '-c', cmd), env = env, stdout = subprocess.PIPE,
                            stderr = subprocess.PIPE)
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
    # Move the event type to the end of the path
    if path.startswith('evt+std:/') :
        splitpath = filter(None, path.split('/'))
        path = '/' + '/'.join(splitpath[1:3] + splitpath[4:-1] + splitpath[3:4] + splitpath[-1:])
    # Remove any sim+std:/ prefix.
    elif ':/' in path :
        path = '/' + '/'.join(filter(None, path.split('/')[1:]))
    return get_lfns('-B', path, outputfile = outputfile)

def gen_xml_catalog(fname, lfns, rootvar = None, ignore = False, extraargs = []) :
    '''Generate the xml catalog for the given LFNs and the .py file to include in your options.
    'rootvar' can be the name of an environment variable which will be used as the root for the
     path of the .xml in the .py. 'fname' can also include unexpanded environment variables,
     in which case 'rootvar' is ignored.'''

    xmlname = os.path.abspath(os.path.expandvars(fname))
    pyname = xmlname[:-4] + '.py'
    
    if not fname.startswith('$') :
        if rootvar :
            fname = os.path.join('$' + rootvar, os.path.relpath(xmlname, os.environ[rootvar]))
        else :
            fname = xmlname

    args = ['dirac-bookkeeping-genXMLCatalog', '-l', ','.join(lfns), '--Catalog=' + xmlname]
    if ignore :
        args += ['--Ignore']
    if lfns[0].lower().endswith('.rdst') :
        args += '--Depth=2'
    if extraargs :
        args += list(extraargs)

    returnvals = dirac_call(*args)
    if not os.path.exists(xmlname) :
        raise OSError('''Call to {0!r} failed!
Exit code: {1}
stdout:
'''.format(' '.join(args), returnvals['exitcode']) + returnvals['stdout'] + '''
stderr:
''' + returnvals['stderr'])

    with open(pyname, 'w') as f :
        f.write('''
from Gaudi.Configuration import FileCatalog

FileCatalog().Catalogs += [ 'xmlcatalog_file:{0}' ]
'''.format(fname))
    return returnvals

def extract_lfns(lfnsfile, nfiles = 0, raiseexecpt = True) :
    '''Extract LFNs from a data file.'''
    
    with open(os.path.expandvars(lfnsfile)) as f :
        contents = f.read()
    # This assumes that the first list in the options file is the list of LFNs.
    lfns = eval(contents[contents.index('['):contents.index(']')+1])
    lfns = [lfn.replace('LFN:', '') for lfn in lfns]
    if nfiles :
        lfns = lfns[:nfiles]

    if not lfns and raiseexcept :
        raise OSError('Failed to extract any LFNs from file ' + lfnsfile)

    return lfns

def gen_xml_catalog_from_file(lfnsfile, xmlfile = None, rootvar = None, nfiles = 0, ignore = False, extraargs = []) :
    '''Extract the LFNs from lfnsfile and pass them to gen_xml_catalog.'''

    lfns = extract_lfns(lfnsfile, nfiles)
    if not xmlfile :
        # Assumes lfnsfile ends with .py
        xmlfile = lfnsfile[:-3] + '_catalog.xml'
    return gen_xml_catalog(fname = xmlfile, lfns = lfns, rootvar = rootvar, ignore = ignore, extraargs = extraargs)

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

def lfn_bk_path(lfn) :
    '''Get the bookkeping path for the given LFN.'''
    returnval = dirac_call('dirac-bookkeeping-file-path', '-l', lfn)
    bkpath = returnval['stdout'].splitlines()[-1].split()[2]
    return bkpath

def prod_for_path(path) :
    '''Get the productions for the given path.'''
    returnval = dirac_call('dirac-bookkeeping-prod4path', '-B', path)
    prods = []
    for line in returnval['stdout'].splitlines()[2:-1] :
        name, prod = line.strip().split(': ')
        prods.append((name, prod))
    return prods

def production_info(prod) :
    '''Get info on the given production from bkk. This requires a lot of string parsing and is thus a bit fragile.'''
    returnval = dirac_call('dirac-bookkeeping-production-information', prod)
    stdout = returnval['stdout']
    splitlines = stdout.splitlines()
    path = splitlines[-1].strip()
    splitlines = filter(None, stdout.split('-----------------------'))
    steps = []
    for info in splitlines[1:-1] :
        infodict = {}
        for line in filter(None, info.splitlines()) :
            name, val = line.split(':')
            infodict[name.strip()] = val.strip()
        if infodict :
            infodict['OptionFiles'] = infodict['OptionFiles'].split(';')
            steps.append(infodict)
        
    return {'info' : stdout,
            'path' : path,
            'steps' : steps}

def get_data_settings(fname, debug = False, forapp = 'DaVinci', fout = None) :
    '''Get the tags and data type for the data in the given file of LFNs.'''
    if debug :
        def output(*vals) :
            print ' '.join(str(v) for v in vals)
    else :
        def output(*vals) :
            pass

    lfn = extract_lfns(fname, 1)[0]
    output('LFN:', lfn)
    inputtype = lfn.split('.')[-1].upper()
    output('InputType:', inputtype)

    bkpath = lfn_bk_path(lfn)
    output('Bk path:', bkpath)

    prods = prod_for_path(bkpath)
    output('Productions:', prods)
    prods = filter(lambda x : not 'merge' in x[0].lower(), prods)
    prod = prods[-1][1]

    output('Production:', prod)

    info = production_info(prod)
    output('Production info:', info)

    # Get the tags.
    opts = 'from Configurables import {0}\n'.format(forapp)
    dddb = None
    conddb = None
    for step in info['steps'][::-1] :
        if not step['DDB'].startswith('from') :
            dddb = step['DDB']
        if not step['CONDDB'].startswith('from') :
            conddb = step['CONDDB']
        if dddb and conddb :
            break
    if not (conddb and dddb) :
        if not debug :
            get_data_settings(fname, True, forapp)
        raise Exception('Failed to get data tags for file {0}!'.format(fname))

    opts += '''{0}().CondDBtag = {1!r}
{0}().DDDBtag = {2!r}
'''.format(forapp, conddb, dddb)

    # Check if it's simulation
    simulation = False
    if 'sim' in conddb.lower() :
        simulation = True
        opts += '{0}().Simulation = True\n'.format(forapp)
    
    # Get the DataType.
    datatype = None
    for step in info['steps'][::-1] :
        for opt in step['OptionFiles'] :
            if 'DataType' in opt :
                datatype = os.path.split(opt)[1].replace('DataType-', '').replace('.py', '')
                break
        if datatype :
            break
    if not datatype :
        if not debug :
            get_data_settings(fname, True, forapp)
        raise Exception('Failed to get data type for file {0}!'.format(fname))

    if forapp in ('DaVinci', 'Brunel') :
        opts += '{0}().DataType = {1!r}\n'.format(forapp, datatype)
    else :
        opts += '''if 'DataType' in {0}().getProperties() :
    {0}().DataType = {1!r}
'''.format(forapp, datatype)

    opts += '{0}().InputType = {1!r}\n'.format(forapp, inputtype)
        
    if not fout :
        fout = fname.replace('.py', '_settings.py')
    with open(fout, 'w') as f :
        f.write("""'''
{0}
'''

""".format(info['info']))
        f.write(opts)
    
    return {'CondDBtag' : conddb, 'DDDBtag' : dddb, 'DataType' : datatype, 'Simulation' : simulation,
            'InputType' : inputtype}
