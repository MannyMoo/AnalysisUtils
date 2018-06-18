#!/usr/bin/env python
# =============================================================================
# $Id: PartPropSvc.py,v 1.3 2008-12-03 17:35:54 ibelyaev Exp $ 
# =============================================================================
## @file PartProp/PartPropSvc.py
#  Demo-file for interactive work with new Particle Property Service
#  @author Vanya BELYAEV Ivan.Belyaev@nikhef.nl
#  @date 2010-10-22
# =============================================================================
"""

Trivial script to dump the table of Particle Properties 

Last modification $Date$
               by $Author$
"""
# =============================================================================
__author__  = "Vanya BELYAEV Ivan.Belyaev@nikhef.nl"
__version__ = "version $Revision: 1.3 $" 
# =============================================================================
import PartProp.PartPropAlg
import PartProp.Service
from   GaudiPython.Bindings import AppMgr
import sys

# =============================================================================

gaudi = AppMgr()

# Annoyingly have to initialise the AppMgr to initialise the ppSvc
gaudi.initialize()

pps   = gaudi.ppSvc()

#print pps.all()
for pname in sys.argv[1:] :
    try :
        pname = int(pname)
        
    except ValueError :
        pass
    part = pps.find(pname)
    if part != None :
        print part
    else :
        print "Couldn't find particle named {0!r}".format(pname)
    print

# =============================================================================
# The END 
# =============================================================================
