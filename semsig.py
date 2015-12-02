'''
Created on Mar 10, 2015

@author: Minh Ngoc Le
'''
from collections import defaultdict
from collections import deque
from itertools import islice
import logging
from logging.config import fileConfig
import os
import re
import sys
from time import time
import traceback

from psutil._compat import lru_cache
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

import numpy as np

_log = logging.getLogger('semsig')
 
relations_path = '/home/fii800/BabelNet/semsig_files/relations.txt'
relations_path = '/home/minh/scistor/relations.txt'
synsets_of_interest_path = 'synsets_kore50.txt'

# for debugging
# dir_ = os.path.dirname(__file__)
# relations_path = os.path.join(dir_, 'data/relations.txt')
# synsets_of_interest_path = os.path.join(dir_, 'data/synsets.txt')

alpha = 0.85
n = 10**6
eta= 100
#TODO: what are the optimal sizes?
bulk_insert_size = 10000
bulk_fetch_size = 1000

db_name = 'semsig-db'
adjct_coll = None
adjctr_coll = None
adjctw_coll = None
semsig_coll = None
vertices = []

def progress(it, ticks=10**6, total=None):
    start = time()
    for i, v in enumerate(it):
        yield v
        if (i+1) % ticks == 0: 
            if total is None:
                _log.info('%d (%.2f s) ...' %(i+1, time()-start))
            else:
                _log.info('%d of %d (%.2f s) ...' %(i+1, total, time()-start))
            
            
@lru_cache(maxsize=1000000)
def get_adjacents_and_probs(u):
    doc = adjctw_coll.find_one({'_id': u})
    if doc is None: return [], []
    adjctw = doc['adjacents']
    s = float(sum(adjctw[v] for v in adjctw))
    probs = [adjctw[v]/s for v in adjctw]
    return list(adjctw), probs


@lru_cache(maxsize=2)
def get_adjacents(u):
    doc = adjct_coll.find_one({'_id': u})
    if doc is None: return []
    return doc['adjacents']


def get_adjacents_many(ids):
    cursor = adjct_coll.find({'_id': {'$in': ids}})
    return defaultdict(dict, ((doc['_id'], doc['adjacents']) for doc in cursor))


def get_reverse_adjacents_many(ids):
    cursor = adjctr_coll.find({'_id': {'$in': ids}})
    return defaultdict(dict, ((doc['_id'], doc['reverse_adjacents']) 
                              for doc in cursor))


@lru_cache(maxsize=1000000)
def get_step_cache(u):
    return dict()


def choice(arr, size=None, p=None):
    if not isinstance(size, (tuple, list)): 
        size = (size,)
    if len(arr) <= 0:
        raise ValueError('Nothing to choose from.')
    cdf = np.zeros_like(p)
    cdf[0] = p[0]
    for i in range(1, len(p)):
        cdf[i] = cdf[i-1] + p[i]
    assert abs(cdf[-1] - 1) < 0.00001
    num = np.random.rand(*size)
    ind = np.searchsorted(cdf, num)
#     print repr(ind.flatten())
    return np.asarray(arr)[ind.flatten()].reshape(size)


def next_steps(v):
    cache = get_step_cache(v)
    if not cache or (len(cache['choices']) > 0 and 
                     cache['curr'] >= len(cache['choices'])-1):
        adjcts, probs = get_adjacents_and_probs(v)
        cache['curr'] = -1
        cache['choices'] = choice(adjcts, size=1000, p=probs) if adjcts else []
    if len(cache['choices']) > 0:
        cache['curr'] += 1
        return cache['choices'][cache['curr']]
    else:
        return None


class InsertStream(object):
    
    def __init__(self, coll):
        self.coll = coll
        self.cache = []
    
    def insert(self, doc):
        self.cache.append(doc)
        if len(self.cache) >= bulk_insert_size:
            start = time()
            try: 
                self.coll.insert(self.cache)
            except KeyboardInterrupt:
                raise
            except:
                traceback.print_exc()
                _log.error("Bulk insertion fails, try individual insertion.")
                self._insert_cached_documents_individually()
            self.cache = []
            
            
    def _insert_cached_documents_individually(self):
        for doc in progress(self.cache, ticks=1000):
            try:
                self.coll.insert(doc)
            except DuplicateKeyError:
                pass # it was already there
            except:
                _log.error("Failed for document: " + str(doc))
                traceback.print_exc()


    def __enter__(self):
        return self
    
    def __exit__(self, type_, value, traceback):
        if self.cache:
            self.coll.insert(self.cache)


class LocalIterable(object):
    
    def __init__(self, vertices):
        self.tbd = set(vertices)
        self.queue = deque()
        
    def __iter__(self):
        return self
    
    def next(self):
        while self.tbd:
            if not self.queue:
                self.queue.append(iter(self.tbd).next())
            while self.queue:
                v = self.queue.popleft()
                if v in self.tbd:
                    self.queue.extend(get_adjacents(v))
                    self.tbd.remove(v)
                    return v
        raise StopIteration
    
_LEADING_PART = re.compile('^bn:0+')

def get_edge(line):
    fields = line.strip().split('\t')
    if len(fields) != 3: return None, None
    u, _, v = fields
    u = _LEADING_PART.sub('', u)
    v = _LEADING_PART.sub('', v)
    return u, v


def store_forward_edges():
    global vertices
    vertices = []
    destinations = set()
    _log.info("Storing edges...")
    with InsertStream(adjct_coll) as coll:
        with open(relations_path) as f:
            curr_node = None
            curr_adjs = None
            for line in progress(f):
                u, v = get_edge(line)
                if u is None: continue
                destinations.add(v)
                if curr_node is None or curr_node != u:
                    if curr_node:
                        coll.insert({'_id': curr_node, 'adjacents': curr_adjs})
                        vertices.append(curr_node)
                    curr_node = u
                    curr_adjs = defaultdict(int)
                curr_adjs[v] += 1
            coll.insert({'_id': curr_node, 'adjacents': curr_adjs})
            vertices.append(curr_node)
    _log.info("Storing edges... Done.")
    _log.info('Number of vertices '
                     'with at least one out-going edge: %d' %len(vertices))
    deadends = destinations.difference(vertices)
    _log.info('Number of dead-end vertices: %d' %len(deadends))


def store_reverse_edges():
    adjctr_coll.drop()
    num_splits = 4
    with InsertStream(adjctr_coll) as coll:
        for i in range(num_splits):
            _log.info("Storing reverse edges (split #%d)..." %i)
            reverse_adjacents = defaultdict(lambda: defaultdict(int))
            with open(relations_path) as f:
                for line in progress(f):
                    u, v = get_edge(line)
                    if u is None: continue
                    if hash(v) % num_splits == i:
                        reverse_adjacents[v][u] += 1
                for v in reverse_adjacents:
                    coll.insert({'_id': v, 'reverse_adjacents': reverse_adjacents[v]})
            _log.info("Storing reverse edges (split #%d)... Done." %i)


def store_graph():    
    _log.info("Reading graph from %s..." %relations_path)
    store_forward_edges()
    store_reverse_edges()
    _log.info('Reading graph from %s... Done.' %relations_path)


def read_vertices():
    global vertices
    _log.info("Reading vertices from %s..." %relations_path)
    vertices = set()
    with open(relations_path) as f:
        for line in progress(f):
            u, _ = get_edge(line)
            if u is None: continue
            vertices.add(u)
    _log.info("Reading vertices from %s... Done." %relations_path)


def weight_edges():
    adjctw_coll.drop()
    try:
        _log.info("Finding triangles and weight edges...")    
        with InsertStream(adjctw_coll) as coll:
            it = iter(progress(vertices, ticks=10000, total=len(vertices)))
            while True:
                us = list(islice(it, bulk_fetch_size))
                if len(us) <= 0: break
                
#                 start = time()
#                 _log.info("Fetching adjacent lists... ")
                adjct_us = get_adjacents_many(us)
                reverse_adjct_us = get_reverse_adjacents_many(us)
#                 _log.info("Done (%.2f)." %(time()-start))
                
#                 start = time()
#                 _log.info("Weighting edges...")
                vs = list(set(v for u in adjct_us for v in adjct_us[u]))
                adjct_vs = get_adjacents_many(vs)
                for u in us:
                    adjctw = dict()
                    for v in adjct_us[u]:
                        if len(adjct_vs[v]) < len(reverse_adjct_us[u]):
                            smaller = adjct_vs[v]  
                            bigger = reverse_adjct_us[u]
                        else:
                            bigger = adjct_vs[v]  
                            smaller = reverse_adjct_us[u]
                        adjctw[v] = sum(adjct_vs[v][b] * reverse_adjct_us[u][b] 
                                        for b in smaller if b in bigger) + 1
                    coll.insert({'_id': u, 'adjacents': adjctw})
#                 _log.info("Weighting edges... Done (%.2f)." %(time()-start))
        _log.info("Finding triangles and weight edges... Done.")
    finally:
        _log.info("Adjacent cache info: %s" %str(get_adjacents.cache_info()))
#         _log.info("Reverse adjacent cache info: %s" %str(get_reverse_adjacents.cache_info()))


def semantic_signature(ignore_existing=False):
    '''
    ignore_existing: ignore existing synsets (otherwise an error will be raised)
    '''
    with open(synsets_of_interest_path) as f:
        synsets = [_LEADING_PART.sub('', line.strip()) for line in f]
    try:
        _log.info("Running random walk with restart...")
        with InsertStream(semsig_coll) as coll:
            for u in progress(LocalIterable(synsets), ticks=100, total=len(synsets)):
                if ignore_existing and semsig_coll.find_one({'_id': u}):
                    continue
                rands = np.random.rand(n)
                count = defaultdict(int)
                v = u
                for i in xrange(n):
                    if rands[i] > alpha:
                        v = next_steps(v) or u
                    else:
                        v = u
                    if v != u:
                        count[v] += 1
                semsig_u = dict(item for item in count.iteritems()
                                if item[1] >= eta)
                doc = {'_id': u, 'semsig': semsig_u}
                coll.insert(doc)
        _log.info("Running random walk with restart... Done.")
    finally:
        _log.info("Adjacent cache info: %s" %str(get_adjacents.cache_info()))
        _log.info("Adjacent-and-prob cache info: %s" %str(get_adjacents_and_probs.cache_info()))
        _log.info("Step cache info: %s" %str(get_step_cache.cache_info()))


def init(drop_db):
    global db, adjct_coll, adjctr_coll, adjctw_coll, semsig_coll
    if drop_db:
        if not(len(sys.argv) >= 2 and sys.argv[1] == '-y'):
            sys.stdout.write("Are you sure you want to drop database %s? [y/N] " %db_name)
            if sys.stdin.readline().strip() != 'y':
                sys.stdout.write("Goodbye!\n")
                sys.exit(0)
        _log.info('Dropping database... ')
        client.drop_database(db_name)
        _log.info('Dropping database... Done.')
    db = client['semsig-db']
    adjct_coll = db['adjct-coll']
    adjctr_coll = db['adjctr-coll']
    adjctw_coll = db['adjctw-coll']
    semsig_coll = db['semsig-coll']


if __name__ == '__main__':
    fileConfig('logging.cfg')
    assert os.path.exists(relations_path)
    client = MongoClient()
    try:
        command = None
        if len(sys.argv) >= 2 and not sys.argv[1].startswith('-'):
            command = sys.argv[1]
            del sys.argv[1]
        if (command == 'phase1'):
            init(drop_db=True)
            store_graph()
        elif (command == 'phase1a'):
            init(drop_db=True)
            store_forward_edges()
        elif (command == 'phase1b'):
            init(drop_db=False)
            store_reverse_edges()
        elif (command == 'phase2'):
            init(drop_db=False)
            read_vertices()
            weight_edges()
        elif (command == 'phase3'):
            init(drop_db=False)
            semantic_signature(ignore_existing=True)
        else:
            init(drop_db=True)
            store_graph()
            weight_edges()
            semantic_signature()
    finally:
        client.close()
