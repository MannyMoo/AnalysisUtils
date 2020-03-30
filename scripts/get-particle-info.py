#!/usr/bin/env python

'''Get info on a particle from the ParticePropertySvc.'''

pps = None

def initialise(dddbtag = '', datatype = '') :
    global pps
    if pps :
        return
    import PartProp.PartPropAlg
    import PartProp.Service
    from   GaudiPython.Bindings import AppMgr
    import sys
    from Configurables import LHCbApp

    if dddbtag :
        LHCbApp().DDDBtag = dddbtag
    elif datatype:
        from Configurables import CondDB
        CondDB().LatestGlobalTagByDataType = datatype
    gaudi = AppMgr()

    # Annoyingly have to initialise the AppMgr to initialise the ppSvc
    gaudi.initialize()

    pps   = gaudi.ppSvc()

def print_info(pname, dddbtag = '', datatype = '') :

    initialise(dddbtag, datatype)

    # See if it's an int ID.
    try :
        pname = int(pname)
    except ValueError :
        pass
    part = pps.find(pname)
    if part != None :
        print part, ', tau:', part.lifetime()*1000., 'ps'
    else :
        print "Couldn't find particle named {0!r}".format(pname)
    print

def print_all(dddbtag = '', datatype = '') :
    initialise(dddbtag, datatype)
    print pps.all()

def main() :
    from argparse import ArgumentParser

    argparser = ArgumentParser()
    argparser.add_argument('--dddbtag', default = '',
                           help = 'DDDB tag to use. Note that the DDDB contains ParticleTable.txt so it\'s\
important to use the correct tag.')
    argparser.add_argument('--datatype', default = '', help = 'Set the DataType to get the latest global tags.')
    argparser.add_argument('--all', action = 'store_true',
                           help = 'Print the full particle table.')
    argparser.add_argument('particles', nargs = '*',
                           help = 'Names or IDs of particles to print')

    args = argparser.parse_args()

    if args.all :
        print_all(args.dddbtag, args.datatype)
    
    for partname in args.particles :
        print_info(partname, args.dddbtag, args.datatype)

if __name__ == '__main__' :
    main()
