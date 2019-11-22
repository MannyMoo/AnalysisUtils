'''General handy functions for Ganga.'''

from GangaCore.GPI import Local, LocalFile, GaudiExec, Job, box, LHCbDataset
import os, glob

def gaudi_exec(app = '', **kwargs):
    '''Get a GaudiExec instance for the current project.'''
    key = app.upper() + 'DEV_PROJECT_ROOT'
    keys = filter(lambda k : k.endswith(key), os.environ)
    if not keys:
        raise ValueError("Couldn't find project root (environment variable ending with {0})".format(key))
    dirname = os.environ[keys[0]]
    if not 'platform' in kwargs:
        # Find build directories.
        builds = filter(lambda x : os.path.isdir(x), glob.glob(os.path.join(dirname, 'build.*')))
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
            
def remove_tests(jobs, status = ('completed', 'failed', 'killed'), namestart = 'Test-'):
    '''Remove test jobs (names starting with namestart) with the given statuses.'''
    for j in jobs:
        if j.name.startswith(namestart) and j.status in statuses:
            j.remove()
