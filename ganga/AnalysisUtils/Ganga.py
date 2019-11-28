'''General handy functions for Ganga.'''

from GangaCore.GPI import Local, LocalFile, GaudiExec, Job, box, LHCbDataset
import os, glob, re, sys
from pprint import pformat
from AnalysisUtils.diracutils import get_access_urls

class OptionsFile(object):
    '''Get an options file path from the given options directory.'''

    def __init__(self, optsdir):
        '''Constructor: takes the options directory, which will be expanded and made absolulte.'''
        self.optsdir = os.path.abspath(os.path.expandvars(optsdir))

    def __call__(self, fname):
        '''Get an options file path from the given options directory.'''
        if not os.path.isabs(fname):
            return os.path.join(self.optsdir, fname)
        return fname

    def data_files(self, matchpatterns = (), vetosuffices = ('_settings.py', '_catalog.py')):
        '''Get data options file from the given directory.'''
        if isinstance(matchpatterns, str):
            matchpatterns = (matchpatterns,)
        fnames = glob.glob(self('*.py'))
        if not matchpatterns:
            filterfunc = lambda fname: not any(fname.endswith(suff) for suff in vetosuffices)
        else:
            filterfunc = lambda fname: (any(re.search(pat, fname) for pat in matchpatterns)
                                        and not any(fname.endswith(suff) for suff in vetosuffices))
        return list(filter(filterfunc, fnames))

# Options directory and options file getter.
optsdir = os.path.expandvars('$ANALYSISUTILSROOT/options/')
options_file = OptionsFile(optsdir)

def run_dir(app = ''):
    '''Get the current application project root.'''
    key = app.upper() + 'DEV_PROJECT_ROOT'
    keys = list(filter(lambda k : k.endswith(key), os.environ))
    if not keys:
        raise ValueError("Couldn't find project root (environment variable ending with {0})".format(key))
    return os.environ[keys[0]]

def run(args, app = '', raiseonfailure = True):
    '''Run a command in the current project.'''
    runexe = os.path.join(run_dir(app), 'run')
    args = [runexe] + args
    proc = subprocess.Popen(args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = proc.communicate()
    exitcode = proc.poll()
    returnval = {'stdout' : stdout, 'stderr' : stderr, 'exitcode' : exitcode}
    if 0 != exitcode and raiseonfailure :
        raise OSError('''Call to {0!r} failed!
Exit code: {1}
stdout:
'''.format(' '.join(args), returnval['exitcode']) + returnval['stdout'] + '''
stderr:
''' + returnval['stderr'])
    
    return returnval

def gaudi_exec(app = '', **kwargs):
    '''Get a GaudiExec instance for the current project.'''
    dirname = run_dir(app)
    if not 'platform' in kwargs:
        # Find build directories.
        builds = list(filter(lambda x : os.path.isdir(x), glob.glob(os.path.join(dirname, 'build.*'))))
        if builds:
            # Sort by modification time and take the most recent.
            builds = sorted(builds, key = (lambda d : os.stat(d).st_mtime))
            kwargs['platform'] = os.path.split(builds[-1])[1][len('build.'):]
    return GaudiExec(directory = dirname, **kwargs)

def gaudi_exec_job(name, datafile = None, options = [], appkwargs = {}, **kwargs):
    '''Get a job with a GaudiExec application from the current project.'''
    appkwargs['options'] = list(options)
    j = Job(name = name, application = gaudi_exec(**appkwargs), **kwargs)
    if datafile:
        add_data(j, datafile)
    return j

def add_data(j, datafile):
    '''Add data from the given data file.'''
    datafile = os.path.expandvars(datafile)
    dataname = os.path.split(datafile)[1][:-3]
    settingsfile = datafile[:-3] + '_settings.py'
    if os.path.exists(settingsfile):
        j.application.options.insert(0, settingsfile)
    try:
        # Box is a bit prone to corruption.
        data = box[dataname]
        j.inputdata = data
    except:
        j.application.readInputData(datafile)
        data = LHCbDataset(files = j.inputdata.files)
        box.add(data, dataname)
    return data

def resubmit_failed(j) :
    '''Resubmit failed jobs/subjobs.'''
    if hasattr(j, '__iter__') :
        for sj in j :
            resubmit_failed(sj)
        return None
    if len(j.subjobs) > 0 :
        resubmit_failed(j.subjobs)
        return None
    if j.status == 'failed' :
        j.resubmit()

def mv_job_output(j, destDir) :
    '''Move output .root files to the given directory, numbering them according to job
    no and subjob no.'''
    if not os.path.exists(destDir) :
        os.makedirs(destDir)
    
    export(j, os.path.join(destDir, 'job.ganga'))
    for sj in j.subjobs :
        for fullname in glob.glob(os.path.join(sj.outputdir, '*.root')) :
            dirName, fname = os.path.split(fullname)
            destname = os.path.join(destDir, fname.replace('.root', '_' + str(j.id) + '_' + str(sj.id).zfill(3) + '.root'))
            os.rename(fullname, destname)

def test_job(j, nevts = 1000, nfiles = 3) :
    '''Make a local test job with the given number of events and files.'''
    j = j.copy(True)
    j.name = 'Test-' + j.name
    j.inputdata.files = j.inputdata.files[:nfiles]
    j.application.extraOpts += '''from Configurables import ApplicationMgr
ApplicationMgr().EvtMax = {0}
'''.format(nevts)
    j.backend = Local()
    j.splitter = None
    j.outputfiles = [LocalFile(f.namePattern) for f in j.outputfiles]
    return j
            
def remove_tests(jobs, statuses = ('completed', 'failed', 'killed'), namestart = 'Test-'):
    '''Remove test jobs (names starting with namestart) with the given statuses.'''
    for j in jobs:
        if j.name.startswith(namestart) and j.status in statuses:
            j.remove()

def get_output_lfns(jobs, outputfile, urlsfile = None, overwrite = False) :
    '''Get LFNs for job output files and save them to the given file. Optionally their access URLs and save
    them to 'urlsfile'. If 'urlsfile' exists and overwrite = False, the urls will only be obtained for LFNs
    that don't yet have a URL.'''
    if not hasattr(jobs, '__iter__') :
        jobs = [jobs]
    lfns = []
    failures = []
    jobinfos = {}
    for job in jobs :
        ntot = len(job.subjobs)
        ncomplete = 0
        nok = 0
        nfail = 0
        for sj in job.subjobs.select(status = 'completed') :
            ncomplete += 1
            fout = sj.outputfiles[0]
            try :
                lfns.append(fout.lfn)
                nok += 1
            except :
                failures.append(sj)
                nfail += 1
        jobinfo = {'id' : job.id,
                   'nsubjobs' : ntot,
                   'ncomplete' : ncomplete,
                   'nLFNOK' : nok,
                   'nLFNFail' : nfail}
        jobinfos[job.name] = jobinfo
    with open(outputfile, 'w') as f :
        f.write('jobinfos = ' + pformat(jobinfos).replace('\n', '\n' + ' ' * len('jobinfos = ')) + '\n')
        f.write('lfns = ' + pformat(lfns).replace('\n', '\n' + ' ' * len('lfns = ')))
    print('Got LFNs for {0}/{1} subjobs'.format(len(lfns), sum(len(j.subjobs.select(status = 'completed')) for j in jobs)))
    if not urlsfile:
        return lfns, failures
    
    urls = None
    if not overwrite and os.path.exists(urlsfile):
        dirname, fname = os.path.split(urlsfile)
        sys.path.insert(0, dirname)
        mod = __import__(fname[:-3], fromlist = ['urls'])
        urls = mod.urls
        sys.path.pop(0)
    urls = get_access_urls(lfns, outputfile = urlsfile, urls = urls)
    return lfns, failures, urls

def get_dataset(jobs, excludedataset = None):
    '''Get an LHCbDataset from the inputdata of the given jobs.'''
    data = LHCbDataset()
    for j in jobs:
        data.files += j.inputdata.files
    if excludedataset:
        data = data.difference(excludedataset)
    return data

def copy_job(j, onlyfailed = True, excludedataset = None):
    '''Copy a job, by default only selecting input files from failed subjobs.'''
    jc = j.copy(True)
    if onlyfailed:
        jc.inputdata = get_dataset(j.subjobs.select(status = 'failed'), excludedataset)
    return jc
