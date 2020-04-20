from __future__ import print_function
import subprocess, re, pprint, os, sys
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
    lblogin = stdout.strip().decode(sys.stdout.encoding)

    cmd = '''. {0} >& /dev/null
lb-run -c best LHCbDirac/prod {1}'''.format(lblogin,
                                            ' '.join('"' + str(arg) + '"' for arg in args))

    proc = subprocess.Popen(('bash', '-c', cmd), env = env, stdout = subprocess.PIPE,
                            stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    stdout = str(stdout.decode(sys.stdout.encoding))
    stderr = str(stderr.decode(sys.stdout.encoding))
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

def write_lfns(fout, *lfns, **kwargs) :
    '''Write the given LFNs to an options file. If 'comment' is in kwargs, it's written first 
    as a multiline comment.'''

    lines = ''
    comment = kwargs.get('comment', '')
    if comment :
        lines += """'''
{0}
'''
""".format(comment)
    
    lines += '''
from GaudiConf import IOHelper
IOHelper('ROOT').inputFiles(
{0},
clear=True)
'''.format(pprint.pformat(['LFN:' + lfn for lfn in lfns]))
    
    with open(fout, 'w') as f :
        f.write(lines)

def get_bk_stats(path):
    '''Get the stats for the given bk path.'''
    stats = dirac_call('dirac-bookkeeping-get-stats', '-B', path)
    for line in filter(None, stats['stdout'].splitlines()[1:]):
        splitline = line.split(':')
        stats[splitline[0].strip()] = splitline[1].strip().replace("'", '')
    return stats
    
def get_lfns(*args, **kwargs) :
    '''Get the LFNs from the given BK query. If the keyword arg 'outputfile' is given,
    the LFNs are saved as an LHCb dataset to that file. If the 'stats' keyword arg is given
    and is True, the stats for the BK query are added as a comment to the top of the file.
    An additional comment can be added to the top of the output file with the 'comment' kwarg.'''
    
    result = dirac_call('dirac-bookkeeping-get-files', *args)
    lfns = filter(lambda line : line.startswith('/lhcb'), result['stdout'].splitlines())
    lfns = [lfn.split()[0] for lfn in lfns]
    if not kwargs.get('outputfile', None) :
        return lfns

    comment = 'lb-run LHCbDirac/prod dirac-bookkeeping-get-files {0}'.format(' '.join(args))
    if kwargs.get('stats', False):
        stats = dirac_call('dirac-bookkeeping-get-stats', *args)
        comment += '\n\n' + stats['stdout']
    if 'comment' in kwargs:
        comment += '\n' + comment
    write_lfns(kwargs['outputfile'], *lfns,
               comment = comment)        
    return lfns

def get_lfns_from_path(path, outputfile = None, stats = True, dataQuality = 'OK') :
    '''Get the LFNs from the given BK path.'''
    # Move the event type to the end of the path
    if path.startswith('evt+std:/') :
        splitpath = list(filter(None, path.split('/')))
        path = '/' + '/'.join(splitpath[1:3] + splitpath[4:-1] + splitpath[3:4] + splitpath[-1:])
    # Remove any sim+std:/ prefix.
    elif ':/' in path :
        path = '/' + '/'.join(filter(None, path.split('/')[1:]))
    args = ['-B', path]
    if dataQuality:
        args += ['--DQFlags', dataQuality]
    return get_lfns(*args, outputfile = outputfile, stats = stats)

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

def get_bk_data(path, outputfile, stats = True, dataQuality = 'OK', genxml = True, xmlfile = None, rootvar = None,
                nfiles = 0, ignore = False, settings = True, latestTagsForRealData = True):
    '''Get bookkeeping data from the given path and save it to the output file. Optionally saving the xml
    catalog and data settings as well.'''
    get_lfns_from_path(path = path, outputfile = outputfile, stats = stats, dataQuality = dataQuality)
    if genxml:
        gen_xml_catalog_from_file(outputfile, xmlfile = xmlfile, rootvar = rootvar, nfiles = nfiles, ignore = ignore)
    if settings:
        get_data_settings(outputfile, latestTagsForRealData = latestTagsForRealData)

def extract_lfns(lfnsfile, nfiles = 0, raiseexecpt = True) :
    '''Extract LFNs from a data file.'''
    
    with open(os.path.expandvars(lfnsfile)) as f :
        contents = f.read()
    
    # Find the first instance of LFN:
    istart = contents.index('LFN:')-10
    # Then find the start and end of the list.
    istart = contents.index('[', istart)
    iend = contents.index(']', istart)
    lfns = eval(contents[istart:iend+1])
    lfns = [str(lfn.replace('LFN:', '')) for lfn in lfns]
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
from __future__ import print_function
import sys, subprocess
from DIRAC.Core.Base.Script import parseCommandLine
parseCommandLine() # Need this for some reason.
from LHCbDIRAC.BookkeepingSystem.Client.BookkeepingClient import BookkeepingClient

bk = BookkeepingClient()
stepid = '%s'
info = bk.getAvailableSteps({'StepId' : stepid})
info = dict(zip(info['Value']['ParameterNames'], info['Value']['Records'][0]))
print(repr(info))
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
    print('Got URLs for', str(sum(int(bool(url)) for url in urls.values())) + '/' + str(len(urls)), 'LFNs.')
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
        try :
            name, prod = line.strip().split(': ')
        except ValueError :
            continue
        prods.append((name, prod.split(',')))
    if not prods:
        raise Exception('''Failed to get productions for path
{0}
stdout:
{1}
stderr:
{2}
'''.format(path, returnval['stdout'], returnval['stderr']))
    return prods

def production_info(prod) :
    '''Get info on the given production from bkk. This requires a lot of string parsing and is thus a bit fragile.'''
    returnval = dirac_call('dirac-bookkeeping-production-information', prod)
    stdout = returnval['stdout']
    splitlines = stdout.splitlines()
    path = splitlines[-1].strip()
    splitlines = list(filter(None, stdout.split('-----------------------')))
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

def transformation_info(prod):
    '''Get the transformation info for the given production/transformation number.'''
    returnval = dirac_call('dirac-transformation-information', prod)
    vals = {}
    for line in returnval['stdout'].splitlines()[1:]:
        splitline = line.split(': ')
        vals[splitline[0].strip()] = ': '.join(splitline[1:]).strip()
    return vals

def request_for_prod(prod):
    '''Get the MC request number from the given production. Note that this returns the parent
    request, if it has sub-requests.'''
    info = transformation_info(prod)
    return int(info['Request'])

def request_for_path(path):
    '''Get the MC request number from the given bk path.'''
    prods = prod_for_path(path)
    requests = []
    for name, _prods in prods:
        _requests = tuple(request_from_prod(prod) for prod in _prods)
        requests.append((name, _requests))
    return requests

def get_data_settings(fname, debug = False, forapp = 'DaVinci', fout = None, latestTagsForRealData = True) :
    '''Get the tags and data type for the data in the given file of LFNs.'''
    if debug :
        def output(*vals) :
            print(' '.join(str(v) for v in vals))
    else :
        def output(*vals) :
            pass

    lfn = extract_lfns(fname, 1)[0]
    output('LFN:', lfn)

    opts = 'from Configurables import {0}\n'.format(forapp)

    # Get the input type.
    inputtype = lfn.split('.')[-1].upper()
    if inputtype == 'XDIGI' :
        inputtype = 'DIGI'
    output('InputType:', inputtype)
    opts += '{0}().InputType = {1!r}\n'.format(forapp, inputtype)

    bkpath = lfn_bk_path(lfn)
    output('Bk path:', bkpath)

    prods = prod_for_path(bkpath)
    output('Productions:', prods)
    prods = list(filter(lambda x : not 'merge' in x[0].lower(), prods))
    name, prods = prods[-1]
    prod = prods[-1]

    output('Production:', prod)

    info = production_info(prod)
    output('Production info:', info)

    # Get the DataType.
    # First try the LFN path.
    datatype = None
    years = range(2010, 2013) + range(2015, 2019)
    datatypes = {str(year) : ['Collision' + str(year)[2:], 'MC/' + str(year)] for year in years}
    for dtype, matches in datatypes.items():
        if any(match in lfn for match in matches):
            datatype = dtype
            break
    # If that fails, try the options.
    if not datatype:
        for step in info['steps'][::-1] :
            for opt in step['OptionFiles'] :
                opt = os.path.split(opt)[1]
                for test in 'DataType-', 'Tesla_Data_', 'Tesla_Simulation_':
                    if re.match(test + '[0-9]*\.py', opt) :
                        datatype = opt[len(test):-3]
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

    # Get the tags.
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

    # Check if it's simulation
    simulation = False
    if 'sim' in conddb.lower() :
        simulation = True
        opts += '{0}().Simulation = True\n'.format(forapp)

    if simulation or not latestTagsForRealData:
        opts += '''{0}().CondDBtag = {1!r}
{0}().DDDBtag = {2!r}
'''.format(forapp, conddb, dddb)
    else:
        opts +='''
from Configurables import CondDB
CondDB().LatestGlobalTagByDataType = {0}().getProp('DataType')
'''.format(forapp)
            
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
