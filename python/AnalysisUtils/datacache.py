'''Classes for caching data.'''

from __future__ import print_function
import ROOT, pickle, sys
from datetime import datetime
from Silence import Silence, TempFileRedirectOutput

def should_pickle(obj):
    '''Check if an object should be pickled rather than using ROOT persistency.'''
    if not isinstance(obj, ROOT.TObject):
        return True
    # Classes inheriting from TOBject that we prefer to be pickled.
    # Bit hacky, but can't think of another way to do it just now.
    pkllist = ('DataChain',)
    if obj.__class__ in pkllist:
        return True
    return False

def write(tfile, name, obj):
    '''Write an object to a TFile. If it's not a TObject, it's pickled and stored in the title of a TNamed.'''
    tfile.cd()
    if should_pickle(obj):
        title = 'pkl:' + pickle.dumps(obj)
        obj = ROOT.TNamed(name, title)
    else:
        obj.SetName(name)
    obj.Write()

def load(tfile, name, fileresident = False):
    '''Load an object from a TFile. If it's a TNamed, check if it's a pickled object, and if so, unpickle it.'''
    obj = tfile.Get(name)
    if not obj:
        raise ValueError('TFile {0} doesn\'t contain an object named {1!r}!'.format(tfile.GetName(), name))
    if not fileresident:
        try:
            obj.SetDirectory(None)
        except AttributeError:
            pass
    if isinstance(obj, ROOT.TNamed) and obj.GetTitle().startswith('pkl:'):
        obj = pickle.loads(obj.GetTitle()[4:])
    return obj

class DataCache(object):
    '''A class for caching the return values of a function.'''

    def __init__(self, name, fname, names, function, args = (), kwargs = {}, update = False, debug = False,
                 cachestdout = True, printstdout = True):
        super(DataCache, self).__setattr__('names', set(names))
        self.name = name
        for prop in 'ctime', 'stdout', 'stderr':
            self.names.add(prop)
        self.fname = fname
        self.function = function
        self.args = tuple(args)
        self.kwargs = dict(kwargs)
        self.doupdate = update
        self.debug = debug
        if not debug:
            self.debug_msg = self.null_msg
        self.cachestdout = cachestdout
        self.printstdout = printstdout
        self._vals = None

    def debug_msg(self, *msg):
        print('DEBUG:', self.name + ':', *msg)

    def null_msg(self, *msg):
        pass

    def load(self):
        '''Load the values, updating them if necessary.'''
        self.debug_msg('load')
        if not self.doupdate:
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
        if attr in self.names:
            return self.values[attr]
        return super(DataCache, self).__getattribute__(attr)

    def __setattr__(self, attr, val):
        if attr in self.names:
            self.values[attr] = val
        super(DataCache, self).__setattr__(attr, val)

    def execute(self):
        '''Call the function and assign the return values as attributes.'''
        self.debug_msg('call execute')
        self.debug_msg('update ctime')
        ctime = datetime.today()
        self.debug_msg('call function')
        if self.cachestdout:
            self.debug_msg('caching stdout')
            try:
                with TempFileRedirectOutput() as redirect:
                    vals = self.function(*self.args, **self.kwargs)
            except:
                # Call it again without the redirect to get the full traceback.
                self.debug_msg('caught exception, call function again to raise it')
                vals = self.function(*self.args, **self.kwargs)
            stdout, stderr = redirect.read()
            if self.printstdout:
                print(stdout, end = '')
                print(stderr, end = '', file = sys.stderr)
        else:
            vals = self.function(*self.args, **self.kwargs)
            stdout = stderr = None
        vals['ctime'] = ctime
        vals['stdout'] = stdout
        vals['stderr'] = stderr
        self.set_vals(vals)
        self.write()
        self.debug_msg('execute complete')
        return vals

    update = execute

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

    def open_file(self, mode = ''):
        '''Open the cache .root file.'''
        with Silence():
            fout = ROOT.TFile.Open(self.fname, mode)
        return fout

    def write(self):
        '''Save to file.'''
        self.debug_msg('write')
        fout = self.open_file('recreate')
        for name in self.names:
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
        fout = self.open_file()
        if not fout or fout.IsZombie():
            self.debug_msg('file is None or zombie, return None')
            return None
        sortedargs = self.sorted_args()
        for name, comp in dict(names = self.names, function = self.func_name(), args = sortedargs['pklargs'],
                               kwargs = sortedargs['pklkwargs']).items():
            try:
                obj = load(fout, name)
            except ValueError:
                self.debug_msg('Failed to retrieve', name, ', return None')
                return None
            if obj != comp:
                self.debug_msg(name + " doesn't match what's in the file:\n" 
                               + "from args:\n{0!r}\nfrom file:\n{1!r}".format(comp, obj))
                self.debug_msg('return None')
                return None
        vals = {}
        for name in self.names:
            try:
                vals[name] = load(fout, name)
            except ValueError:
                self.debug_msg('Failed to retrieve', name, ', return None')
                return None
        for arg in sortedargs['cacheargs'] + list(sortedargs['cachekwargs'].values()):
            if arg.ctime > vals['ctime']:
                self.debug_msg('Cache at {0} was updated at {1}, this cache was updated at {2}'\
                               .format(arg.fname, arg.ctime, vals['ctime']))
                self.debug_msg('return None')
                return None
        self.set_vals(vals)
        self.debug_msg('retrieve complete')
        return vals

if __name__ == '__main__':
    from ROOT import TRandom3
    import os

    def calc_pi(n = 1000, seed = 1234):
        print('calculate pi with n = ', n, 'seed =', seed)
        rndm = TRandom3(seed)
        npass = 0
        for i in xrange(n):
            x = rndm.Rndm()-0.5
            y = rndm.Rndm()-0.5
            r = (x**2 + y**2)**.5
            if r < 0.5:
                npass += 1.
        pi = npass/n*4.
        print('pi is', pi)
        return {'pi' : pi}

    def area(picache, r):
        return {'area' : picache.pi*r**2}

    for fname in 'pi.root', 'area.root':
        if os.path.exists(fname):
            os.remove(fname)

    debug = False
    printstdout = False
    cachestdout = True

    # standard access.
    picache = DataCache('pi', 'pi.root', ['pi'], calc_pi, kwargs = dict(n = 1000, seed = 1234), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    print('pi', picache.pi)
    # Check that it doesn't recaclulate anything.
    print('pi again', picache.pi)

    # A cache using another cache as input.
    areacache = DataCache('area', 'area.root', ['area'], area, kwargs = dict(picache = picache, r = 1.), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    print('area', areacache.area)

    # Update the input cache, check that the dependent cache updates.
    picache.update()
    areacache = DataCache('area2', 'area.root', ['area'], area, kwargs = dict(picache = picache, r = 1.), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    print('area after update', areacache.area)

    # Change the arguments of the input cache, but don't immediately access it.
    picache = DataCache('pi2', 'pi.root', ['pi'], calc_pi, kwargs = dict(n = 2000, seed = 1234), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    # Accessing the dependent cache should trigger an update of the input cache.
    areacache = DataCache('area3', 'area.root', ['area'], area, kwargs = dict(picache = picache, r = 1.), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    print('area after 2nd update', areacache.area)
    
    # Cause a crash.
    picache = DataCache('pi3', 'pi.root', ['pi'], calc_pi, kwargs = dict(n = 2000, seed = '1234'), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    #picache.pi
    try:
        picache.pi
    except Exception as error:
        print('Caught exception:')
        print(error)

    # Cause a crash in the input cache when calculating the dependent cache
    areacache = DataCache('area4', 'area.root', ['area'], area, kwargs = dict(picache = picache, r = 1.), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    #areacache.area
    try:
        areacache.area
    except Exception as error:
        print('Caught exception:')
        print(error)

    # Check the original still works.
    picache = DataCache('pi4', 'pi.root', ['pi'], calc_pi, kwargs = dict(n = 2000, seed = 1234), debug = debug, printstdout = printstdout, cachestdout = cachestdout)
    print('pi4', picache.pi)

