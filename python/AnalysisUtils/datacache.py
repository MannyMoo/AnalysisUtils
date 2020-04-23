'''Classes for caching data.'''

import ROOT, pickle
from datetime import datetime

def write(tfile, name, obj):
    '''Write an object to a TFile. If it's not a TObject, it's pickled and stored in the title of a TNamed.'''
    tfile.cd()
    if not isinstance(obj, ROOT.TObject):
        title = 'pkl:' + pickle.dumps(obj)
        obj = ROOT.TNamed(name, title)
    else:
        obj.SetName(name)
    obj.Write()

def load(tfile, name):
    '''Load an object from a TFile. If it's a TNamed, check if it's a pickled object, and if so, unpickle it.'''
    obj = tfile.Get(name)
    if not obj:
        raise ValueError('TFile {0} doesn\'t contain an object named {1!r}!'.format(tfile.GetName(), name))
    if isinstance(obj, ROOT.TNamed) and obj.GetTitle().startswith('pkl:'):
        obj = pickle.loads(obj.GetTitle()[4:])
    return obj

class DataCache(object):
    '''A class for caching the return values of a function.'''

    def __init__(self, fname, names, function, args = (), kwargs = {}, update = False, debug = False):
        super(DataCache, self).__setattr__('names', set(names))
        self.names.add('ctime')
        self.fname = fname
        self.function = function
        self.args = tuple(args)
        self.kwargs = dict(kwargs)
        self.update = update
        self.debug = debug
        if not debug:
            self.debug_msg = self.null_msg
        self._vals = None

    def debug_msg(self, msg):
        print 'DEBUG:', msg

    def null_msg(self, msg):
        pass

    def properties(self):
        return list(super(DataCache, self).__getattribute__('names')) + ['ctime']

    def load(self):
        '''Load the values, updating them if necessary.'''
        self.debug_msg('load')
        if not self.update:
            self.debug_msg('update not requested, attempt to retrieve')
            vals = self.retrieve()
        else:
            self.debug_msg('update requested')
            vals = None
        if not vals:
            vals = self.execute()
        self.debug_msg('update getter')
        self._get_vals = self._get_vals_no_load
        self.debug_msg('load complete')
        return vals

    _get_vals = load
    def _get_vals_no_load(self):
        return self._vals

    def __get_vals(self):
        return self._get_vals()

    values = property(fget = __get_vals, fset = lambda self, val: setattr(self, '_vals', val))

    def __getattr__(self, attr):
        if attr in self.properties():
            return self.values[attr]
        return super(DataCache, self).__getattribute__(attr)

    def __setattr__(self, attr, val):
        if attr in self.properties():
            self.values[attr] = val
        super(DataCache, self).__setattr__(attr, val)

    def execute(self):
        '''Call the function and assign the return values as attributes.'''
        self.debug_msg('call execute')
        self.debug_msg('update ctime')
        ctime = datetime.today()
        self.debug_msg('call function')
        vals = self.function(*self.args, **self.kwargs)
        vals['ctime'] = ctime
        self.set_vals(vals)
        self.write()
        self.debug_msg('execute complete')
        return vals

    def set_vals(self, vals):
        '''Set the values for the cached items.'''
        self.debug_msg('set_vals')
        if not isinstance(vals, dict):
            raise ValueError('The values for data cache {0!r} must be a dict! Got: {1!r}'\
                             .format(self.fname, vals))
        if set(vals.keys()) != self.names:
            raise ValueError('Expected names {0}, but got {1}'.format(self.names, vals.keys()))
        self._vals = vals
        self.debug_msg('set_vals complete')
        return vals

    def func_name(self):
        '''Get the function name.'''
        return self.function.__module__ + '.' + self.function.__name__

    def write(self):
        '''Save to file.'''
        self.debug_msg('write')
        fout = ROOT.TFile.Open(self.fname, 'recreate')
        for name in self.properties():
            write(fout, name, self._vals[name])
        write(fout, 'names', self.names)
        # Could pickle the function itself, but that just stores its name anyway and forbids
        # functions defined in main, inline, or lambdas.
        write(fout, 'function', self.func_name())
        sortedargs = self.sorted_args()
        write(fout, 'args', sortedargs['pklargs'])
        write(fout, 'kwargs', sortedargs['pklkwargs'])
        fout.Close()
        self.debug_msg('write complete')

    def sorted_args(self):
        '''Get args that should be pickled and args that are instances of DataCache.'''
        pklargs = []
        cacheargs = []
        for arg in self.args:
            if isinstance(arg, DataCache):
                cacheargs.append(arg)
            else:
                pklargs.append(arg)
        pklkwargs = {}
        cachekwargs = {}
        for name, arg in self.kwargs.items():
            if isinstance(arg, DataCache):
                cachekwargs[name] = arg
            else:
                pklkwargs[name] = arg
        return dict(pklargs = pklargs, cacheargs = cacheargs, pklkwargs = pklkwargs, cachekwargs = cachekwargs)

    def retrieve(self):
        '''Retrieved the cached values from the file. Returns None if they should be updated.'''
        self.debug_msg('retrieve')
        fout = ROOT.TFile.Open(self.fname)
        if not fout or fout.IsZombie():
            self.debug_msg('file is None or zombie, return None')
            return None
        sortedargs = self.sorted_args()
        for name, comp in dict(names = self.names, function = self.func_name(), args = sortedargs['pklargs'],
                               kwargs = sortedargs['pklkwargs']).items():
            try:
                obj = load(fout, name)
            except ValueError:
                return None
            if obj != comp:
                self.debug_msg(name + " doesn't match what's in the file:\n" 
                               + "from args:\n{0!r}\nfrom file:\n{1!r}".format(comp, obj))
                self.debug_msg('return None')
                return None
        vals = {}
        for name in self.properties():
            try:
                vals[name] = load(fout, name)
            except ValueError:
                return None
        for arg in sortedargs['cacheargs'] + list(sortedargs['cachekwargs']):
            if arg.ctime > vals['ctime']:
                self.debug_msg('Cache at {0} was updated at {1}, this cache was updated at {2}'\
                               .format(arg.fname, arg.ctime, vals['ctime']))
                self.debug_msg('return None')
                return None
        self.set_vals(vals)
        self.debug_msg('retrieve complete')
        return vals

if __name__ == '__main__':
    cache = DataCache('bla.root', ['bla'], lambda : {'bla': 'spam'}, debug = True)
    print cache.bla
    print cache.bla
    cache2 = DataCache('boop.root', ['boop'], lambda x : {'boop' : x.bla}, args = (cache,), debug = True)
    print cache2.boop
    print cache.ctime, cache2.ctime
