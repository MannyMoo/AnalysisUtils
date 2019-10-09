def start_appmgr(initialize = True) :
    '''Import GaudiPython and start AppMgr. If initialise = True, then call appMtr.initialize().'''
    # For ppSvc decorator
    # Not sure why this means the EventSelector then can't be found ...
    #import PartProp.PartPropAlg
    #import PartProp.Service
    import GaudiPython

    appmgr = GaudiPython.AppMgr()
    if initialize :
        appmgr.initialize()
    #ppsvc   = appmgr.ppSvc()
    toolsvc = appmgr.toolSvc()
    evtsvc = tes = TES = appmgr.evtSvc()
    return locals()

def import_opts(*opts, **kwargs) :
    '''Import the given options files. If kwargs contains a 'namespace' argument, that's used as the
    namespace in which to exec the options.'''
    namespace = kwargs.get('namespace', {})
    for opt in opts :
        if opt.endswith('.py') :
            print 'importOptions', opt
            execfile(opt, namespace)
    return namespace

def main() :
    '''Main function. Imports the options, starts the AppMgr, then executes any post config options.'''
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('options', nargs = '*', help = 'Options to import before initialising the AppMgr', default = [])
    parser.add_argument('--postoptions', nargs = '*', help = 'Options to execute after initialising the AppMgr', default = [])
    parser.add_argument('--batch', '-b', action = 'store_true', help = 'Run in batch mode, rather than interactive.')
    
    args = parser.parse_args()
    import_opts(*args.options)
    
    namespace = start_appmgr()

    namespace = import_opts(*args.postoptions, namespace = namespace) 

    if args.batch:
        return namespace
    
    try:
        import IPython
        IPython.start_ipython(argv = [], user_ns = namespace)
    except ImportError:
        import code
        code.interact(local = namespace)
    return namespace
