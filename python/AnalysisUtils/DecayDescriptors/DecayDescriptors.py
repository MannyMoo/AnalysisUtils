'''Decay descriptor manipulation is pretty crude. Probably be better writing a
dedicated class to handle it, but it'll do for now.'''

import re
from ParticleDB import particledb

def strip_descriptor(desc) :
    '''This is particularly crude as some particles have brackets in their names,
    like D*(2010)+, and others have cc in their names, like Xicc.'''
    for c in '[', ']', '(', ')', 'cc', 'CC' :
        desc = desc.replace(c, '')
    return desc

def head_descriptor(desc) :
    desc = strip_descriptor(desc)
    return desc.split()[0], desc

def full_decay_descriptor(stages) :
    desc = stages[-1]
    '''Possibly need to deal better with intermediate cc's rather than just stripping them away ...'''
    for nextdesc in stages[-2::-1] :
        head, strippeddesc = head_descriptor(nextdesc)
        desc = desc.replace(head, '(' + strippeddesc + ')')
    return desc

def full_decay_descriptors(alldescs) :
    counts = [0 for i in xrange(len(alldescs))]
    lens = [len(descs) for head, descs in alldescs.iteritems()]
    heads = alldescs.keys()
    fulldescs = []
    while counts[0] < lens[0] :
        stages = [alldescs[head][counts[i]] for i, head in enumerate(heads)]
        fulldescs.append(full_decay_descriptor(stages))
        counts[-1] += 1
        for i in xrange(len(counts)-1, 0, -1) :
            if counts[i] == lens[i] :
                counts[i] = 0
                counts[i-1] += 1
    return set(desc.replace(']cc', ']CC') for desc in fulldescs)

def descriptor_to_name(desc) :
    subs = (('->', 'To'), 
            ('*', 'st'), 
            ('(', ''), 
            (')', ''),
            ('[', ''),
            (']', ''),
            ('cc', ''),
            ('CC', ''),
            ('+', ''),
            ('-', ''),
            (' ', ''))
    return reduce(lambda desc, sub : desc.replace(*sub), subs, desc)

def add_carets(decay) :
    return re.sub(' ([(A-Za-z])', ' ^\\1', decay)

class ParticleDescriptor(object) :
    __slots__ = ('particle', 'cc', 'daughters', 'caret', 'alias')

    def __init__(self, partid, cc = False, daughters = (), alias = None) :
        try :
            self.particle = particledb.find_particle(partid)
        except TypeError :
            raise TypeError('ParticleDescriptor.__init__: Couldn\'t find particle from ID {0!r}.'.format(partid))
        if not self.particle :
            raise ValueError('ParticleDescriptor.__init__: Couldn\'t find particle from ID {0!r}.'.format(partid))
        self.cc = cc
        self.daughters = list(daughters)
        self.caret = False
        self.alias = alias

    def __repr__(self) :
        selfstr = self.__module__ + '.' + self.__class__.__name__ + '('
        selfstr += 'partid = ' + str(self.particle.pdgid) + ', '
        attrs = tuple(attr for attr in self.__slots__ if attr not in ('particle', 'caret'))
        selfstr += ', '.join(attr + ' = ' + repr(getattr(self, attr)) for attr in attrs)
        selfstr += ')'
        return selfstr
    
    def __str__(self) :
        return self.to_string()

    def conjugate(self) :
        return ParticleDescriptor(-1 * self.particle.pdgid, cc = self.cc,
                                   daughters = tuple(daughter.conjugate() for daughter \
                                                         in self.daughters))

    def copy(self) :
        return ParticleDescriptor(self.particle.pdgid, cc = self.cc,
                                  daughters = tuple(daughter.copy() for daughter \
                                                        in self.daughters))
        

    def set_carets(self, val) :
        for daughter in self :
            daughter.caret = val

    def to_string(self, arrow = '->', ishead = True, carets = False, depth = -1) :
        if carets :
            self.set_carets(carets)
        selfstr = ''
        selfstr += self.particle.name
        if self.daughters and depth != 0 :
            selfstr += ' ' + arrow
            for daughter in self.daughters :
                selfstr += ' ' + daughter.to_string(arrow, False, depth = depth-1)
            if ishead :
                if self.cc :
                    selfstr = '[' + selfstr + ']CC'
            else :
                if self.cc :
                    selfstr = '[' + selfstr + ']cc'
                else :
                    selfstr = '(' + selfstr + ')'
                if self.caret :
                    selfstr = '^' + selfstr
        else :
            if self.cc :
                if ishead :
                    selfstr = '[' + selfstr + ']CC'
                else :
                    selfstr = '[' + selfstr + ']cc'
            if self.caret :
                selfstr = '^' + selfstr
        if carets :
            self.set_carets(False)
        return selfstr
        
    def n_daughters(self) :
        n = len(self.daughters)
        for daughter in self.daughters :
            n += daughter.n_daughters()
        return n

    def get_daughter(self, i) :
        if i == 0 :
            return self
        count = 0 
        # Not sure if this is the way to do it, essentially working right down
        # one branch of the decay tree, then the next. 
        for daughter in self.daughters :
            count += 1
            ndaughters = daughter.n_daughters()
            if count + ndaughters >= i :
                return daughter.get_daughter(i-count)
            count += ndaughters
    
    def __iter__(self) :
        for i in xrange(self.n_daughters()+1) :
            yield self.get_daughter(i)

    def get_alias(self) :
        if self.alias :
            return self.alias
        alias = self.particle.name
        for match, sub in ('+', 'plus'), ('-', 'minus'), ('~', 'bar'), ('*', 'star'), \
                ('(', '_'), (')', '_'):
            alias = alias.replace(match, sub)
        return alias

    def set_aliases(self, aliases) :
        if isinstance(aliases, (tuple, list)) :
            for daughter, alias in zip(self, aliases) :
                daughter.alias = alias
        elif isinstance(aliases, dict) :
            for i, daughter in enumerate(self) :
                if daughter.particle.name in aliases :
                    daughter.alias = aliases[daughter.particle.name]
                elif i in aliases :
                    daughter.alias = aliases[i]

    def set_labX_aliases(self) :
        for i, daughter in enumerate(self) :
            daughter.alias = 'lab' + str(i)

    def branches(self) :
        for daughter in self :
            daughter.caret = False
        branches = {}
        for daughter in self :
            daughter.caret = True
            alias = daughter.get_alias()
            if alias in branches :
                i = 0
                while alias + str(i) in branches :
                    i += 1
                alias = alias + str(i)
            branches[alias] = self.to_string()
            daughter.caret = False
        return branches

    def get_full_alias(self) :
        selfstr = self.get_alias()
        if self.daughters :
            selfstr += 'To'
            for daughter in self.daughters :
                if daughter.daughters :
                    selfstr += '_' + daughter.get_full_alias() + '_'
                else :
                    selfstr += daughter.get_alias()
        return selfstr

    def get_substitutions(self, substitutions) :
        # This assumes that the substitutions are done by index, could add option to 
        # do them by ID as well. 
        self.set_carets(False)
        subs = {}
        if isinstance(substitutions, dict) :
            substitutions = tuple(substitutions.iteritems())
        else :
            substitutions = enumerate(substitutions)
        originalcc = self.cc
        newdesc = ParticleDescriptor(self.particle.pdgid, daughters = self.daughters, 
                                     cc = self.cc,
                                     alias = self.alias)
        self.cc = False
        conj = self.conjugate()
        for i, sub in substitutions :
            newdesc.get_daughter(i).particle = particledb.find_particle(sub)
            subdesc = ParticleDescriptor(sub)
            subdescconj = subdesc.conjugate()
            for fulldesc, subd in (self, subdesc), (conj, subdescconj) :
                fulldesc.get_daughter(i).caret = True
                subs[fulldesc.to_string()] = subd.to_string()
                fulldesc.get_daughter(i).caret = False
        self.cc = originalcc
        return subs, newdesc

def parse_decay_descriptor(desc) :
    originaldesc = desc
    desc = desc.replace('^', '').strip()
    cc = False
    if desc.lower()[-2:] == 'cc' :
        cc = True
        desc = desc[:-2]
    if desc[0] in ('[', '(') :
        desc = desc[1:-1].strip()
    splitdesc = desc.split()
    head = splitdesc[0]
    rhs = splitdesc[2:]
    daughters = []
    try :
        while rhs :
            # need to handle [], and sub-brackets. 
            if rhs[0][0] == '(' :
                i = 1 
                while i < len(rhs) and ')' not in rhs[i] :
                    i += 1
                daughters.append(parse_decay_descriptor(' '.join(rhs[:i+1])))
                rhs = rhs[i+1:]
            else :
                daughters.append(ParticleDescriptor(rhs.pop(0)))
        return ParticleDescriptor(head, cc, daughters)
    except :
        print 'parse_decay_descriptor: failed to parse', repr(originaldesc)
        raise
