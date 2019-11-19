'''General handy functions for Ganga.'''

from GangaCore.GPI import Local, LocalFile
import os, glob

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
