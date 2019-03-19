from collections import OrderedDict

class ParticleInfo(object) :
    __slots__ = ('name', 'geantid', 'pdgid', 'charge', 'mass', 'lifetime', 
                 'evtgenname', 'pythiaid', 'maxwidth')

    def __init__(self, name, geantid, pdgid, charge, mass, lifetime, 
                 evtgenname, pythiaid, maxwidth) :
        for attr in self.__slots__ :
            setattr(self, attr, locals()[attr])
    
    def __repr__(self) :
        selfstr = self.__class__.__name__ + '('
        selfstr += ', '.join([attr + ' = ' + repr(getattr(self, attr)) \
                                  for attr in self.__slots__])
        selfstr += ')'
        return selfstr

    def table_entry(self) :
        strattrs = OrderedDict((attr, str(getattr(self, attr))) for attr in self.__slots__)
        strattrs['mass'] = str(self.mass/1000.) # masses are in GeV in the particle table. 
        return ' '.join(strattrs.values())

def from_lhcb_property(prop) :
    return ParticleInfo(name = prop.name(), 
                        geantid = prop.pid().pid(), 
                        pdgid = prop.pdgID().pid(), 
                        charge = prop.charge(),
                        mass = prop.mass(), 
                        lifetime = prop.lifetime()*1e-9, # ns
                        evtgenname = prop.evtGen(), 
                        pythiaid = prop.pythia(), 
                        maxwidth = prop.maxWidth())
            
