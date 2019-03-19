'''Annoyingly there seems to be no way to access the particle database
in the LHCb software without starting an LHCbApp and accessing the
particleSvc through it, so this packages it in a more portable format.'''

try :
    from ParticleList import particlelist
except ImportError :
    # In case the particle list hasn't been made yet.
    particlelist = []
import os, pprint

def update_particle_list() :
    import PartProp.PartPropAlg
    import PartProp.Service
    from   GaudiPython.Bindings import AppMgr
    from AnalysisUtils.DecayDescriptors.ParticleInfo import from_lhcb_property
    gaudi = AppMgr()
    gaudi.initialize()
    pps   = gaudi.ppSvc()
    particles = [from_lhcb_property(part) for part in pps.all()]

    with open(os.path.join(os.environ['ANALYSISUTILSROOT'], 'python',
                           'AnalysisUtils', 'DecayDescriptors', 'ParticleList.py'), 'w') as f :
        f.write('from AnalysisUtils.DecayDescriptors.ParticleInfo import ParticleInfo\n')
        f.write('particlelist = \\\n' + pprint.pformat(particles) + '\n')
        
class ParticleDB(object) :
    __slots__ = ('particlelist',)

    def __init__(self, particlelist) :
        self.particlelist = list(particlelist)

    def find_particle(self, partid) :
        if isinstance(partid, int) :
            matches = filter(lambda part : (part.pdgid == partid), 
                             self.particlelist)
        else :
            matches = filter(lambda part : (part.name == partid),
                             self.particlelist)
        if matches :
            return matches[0]
        return None

particledb = ParticleDB(particlelist)
