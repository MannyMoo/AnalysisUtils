# For ppSvc decorator
# Not sure why this means the EventSelector then can't be found ...
#import PartProp.PartPropAlg
#import PartProp.Service
import GaudiPython

def start_appmgr(initialise = True) :

    appmgr = GaudiPython.AppMgr()
    if initialise :
        appmgr.initialize()
    #ppsvc   = appmgr.ppSvc()
    toolsvc = appmgr.toolSvc()
    evtsvc = tes = TES = appmgr.evtSvc()
    return locals()

def import_argv_opts(start = 1) :
    import sys
    from Gaudi.Configuration import importOptions
    for opts in sys.argv[start:] :
        if opts.endswith('.py') :
            print 'importOptions', opts
            importOptions(opts)

def main() :
    
    import_argv_opts()
    
    return start_appmgr()
