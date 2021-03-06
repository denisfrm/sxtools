# -*- coding: utf-8 -*-
#
# Copyright 2015 Alexandre Villela (SleX) <https://github.com/sxslex/sxtools/>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Allow decorate a method with a cache to increase
# performance of costly methods
#    by sx.slex@gmail.com

import os
import pprint
import hashlib
import datetime
import platform
from functools import wraps


def _loads(s, ftype='pickle'):
    if ftype == 'pickle':
        import cPickle
        return cPickle.loads(s)
    if ftype == 'literal':
        import ast
        return ast.literal_eval(s)
    raise Exception('ftype "%s" not supported' % ftype)


def _dumps(s, ftype='pickle'):
    if ftype == 'pickle':
        import cPickle
        return cPickle.dumps(s)
    if ftype == 'literal':
        return s.__repr__()
    raise Exception('ftype "%s" not supported' % ftype)


def _getpathfiledir(path, filename, nivel=3, numc=2):
    patha = path.replace('\\', '/')
    directory = ''
    for d in patha.split('/'):
        directory += d
        if d and not os.path.exists(directory):
            os.mkdir(directory, 0775)
            os.chmod(directory, 0775)
        directory += '/'
    for i in xrange(0, nivel):
        sub = filename[i * numc:(i * numc) + numc]
        directory += '%s/' % sub
        if not os.path.exists(directory):
            os.mkdir(directory, 0775)
            os.chmod(directory, 0775)
    return directory + filename


def _getcontextfile(pathfile, minuteexpire=5, debug=False, ftype='pickle'):
    if not os.path.exists(pathfile):
        return None
    timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(pathfile))
    r = (datetime.datetime.now() - timestamp)
    horas = ((r.days * 24 * 60) + r.seconds / 60.0)
    if debug:
        print('expires in %s minutes' % str(minuteexpire - horas))
    if os.path.isdir(pathfile):
        os.rmdir(pathfile)
        return None
    if horas < minuteexpire:
        f = open(pathfile, 'rb')
        try:
            try:
                return _loads(f.read(), ftype=ftype)
            except:
                return None
        finally:
            f.close()
    os.unlink(pathfile)
    return None


def _setcontextfile(pathfile, context, ftype='pickle'):
    if os.path.exists(pathfile):
        os.unlink(pathfile)
    f = open(pathfile, 'wb')
    try:
        f.write(_dumps(context, ftype=ftype))
        return True
    finally:
        f.close()
        os.chmod(pathfile, 0664)


def _getcache(config, *args, **kwargs):
    if os.path.isdir(config.get('path', '')):
        newkwargs = kwargs.copy()
        if 'ignore_cache' in newkwargs:
            newkwargs.pop('ignore_cache')
        seed = pprint.pformat([args, newkwargs])
        pathfile = _getpathfiledir(
            config['path'],
            hashlib.md5(
                config.get('seed', '') +
                config['path'] +
                seed
            ).hexdigest(),
        )
        if config.get('debug'):
            print([pathfile, seed])
        return _getcontextfile(
            pathfile=pathfile,
            minuteexpire=config.get(
                'minuteexpire',
                60 * 24 * 7
            ),
            debug=config.get('debug'),
            ftype=config.get('ftype', 'pickle')
        )
    return None


def _setcache(config, context, *args, **kwargs):
    newkwargs = kwargs.copy()
    if 'ignore_cache' in newkwargs:
        newkwargs.pop('ignore_cache')
    seed = pprint.pformat([args, newkwargs])
    pathfile = _getpathfiledir(
        config['path'],
        hashlib.md5(
            config.get('seed', '') + config['path'] + seed
        ).hexdigest(),
    )
    if config.get('debug'):
        print([pathfile, seed])
    return _setcontextfile(
        pathfile=pathfile,
        context=context,
        ftype=config.get('ftype', 'literal')
    )


class _CacheDef(object):

    """
        Decorator responsible for making a cache of the results
        of calling a method in accordance with the reported.

        Arguments:
            seed -- string to differentiate the caches
            path -- path to store the cache
            minuteexpire -- time in minutes for validity of cache
            debug -- bool active debug mode
            ftype -- so that to store the cache ('pickle', 'literal')

    """

    def __init__(self, seed, path=None, minuteexpire=60, debug=False,
                 ftype='pickle'):

        if not path:
            path = '/tmp/cachedef'
            if platform.system() == 'Windows':
                path = 'c:/tmp/cachedef'
        self.__config = {
            'seed': seed,
            'path': path + '/' + seed,
            'debug': debug,
            'minuteexpire': minuteexpire,
            'ftype': ftype
        }

    def __call__(self, call, *args, **kwargs):
        self.config = self.__config.copy()
        self.config['path'] = self.config['path'] + '/' + call.func_name

        @wraps(call)
        def newdef(*args, **kwargs):
            resp = None
            if not kwargs.get('ignore_cache'):
                resp = _getcache(
                    self.config,
                    *args,
                    **kwargs
                )
            if resp is None:
                if self.config.get('debug'):
                    print('not cache')
                if (
                    'ignore_cache' not in call.func_code.co_varnames
                ) and (
                    'ignore_cache' in kwargs
                ):
                    kwargs.pop('ignore_cache')
                resp = call(*args, **kwargs)
                _setcache(
                    self.config,
                    resp,
                    *args,
                    **kwargs
                )
                if self.config.get('debug'):
                    print('save cache')
            else:
                if self.config.get('debug'):
                    print('get cache')
            return resp
        return newdef


def cache_def(seed, path=None, minuteexpire=60, debug=False, ftype='pickle'):
    """
        Decorator responsible for making a cache of the results
        of calling a method in accordance with the reported.

        Arguments:
            seed -- string to differentiate the caches
            path -- path to store the cache
            minuteexpire -- time in minutes for validity of cache
            debug -- bool active debug mode
            ftype -- so that to store the cache ('pickle', 'literal')

    """
    return _CacheDef(
        seed=seed,
        path=path,
        minuteexpire=minuteexpire,
        debug=debug,
        ftype=ftype
    )


# if __name__ == '__main__':
#     # example of use
#     @cachedef(seed='foo')
#     def foo(a, b):
#         import time
#         time.sleep(1)
#         return a + b

#     start = datetime.datetime.now()

#     # it takes three seconds
#     print 'test 1: %d ' % foo(1, 2)
#     print 'cost: %s' % str(datetime.datetime.now() - start)

#     # should return quickly
#     start = datetime.datetime.now()
#     print 'test 2: %d ' % foo(1, 2)
#     print 'cost: %s' % str(datetime.datetime.now() - start)

#     start = datetime.datetime.now()
#     print 'test 3: %d ' % foo(1, 2)
#     print 'cost: %s' % str(datetime.datetime.now() - start)

#     # ignore cache
#     start = datetime.datetime.now()
#     print 'test 4: %d ' % foo(1, 2, ignore_cache=True)
#     print 'cost: %s' % str(datetime.datetime.now() - start)

#     # it takes three seconds
#     start = datetime.datetime.now()
#     print 'test 5: %d ' % foo(2, 3)
#     print 'cost: %s' % str(datetime.datetime.now() - start)
