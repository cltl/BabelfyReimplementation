'''
Created on Mar 14, 2015

@author: Minh Ngoc Le
'''

import sys
from operator import add
import numpy as np

input_path = 'hdfs://master.ib.cluster:8020/user/minhle/test.txt'
# input_path = 'hdfs://master.ib.cluster:8020/user/minhle/relations.txt'
alpha = 0.85
n = 10
eta = 2
# eta = 10
# n = 10*6

# from pymongo import MongoClient
# client = MongoClient()
# db = client['semsig-db']
# coll = db['semsig-coll']

def create_sample_db():
    coll.remove({}) # clear
    docs = [
            # European Union
            {'_id': 'bn:00021127n', 'synsets': ['bn:00026684n', 'bn:00013173n'], 'labels': ['E.U.', 'European Union']},
            # Peter Blackburn
            {'_id': 'bn:03862986n', 'synsets': ['bn:01286964n', 'bn:01637643n'], 'labels': ['Peter Blackbourn', 'Peter', 'P.B.']},
            # European commission
            {'_id': 'bn:03895618n', 'synsets': ['bn:00030004n', 'bn:02125329n', 'bn:02208619n'], 'labels': ['European comission']},
            # Germany
            {'_id': 'bn:00026684n', 'synsets': ['bn:00010025n'], 'labels': ['Germany', 'Deutschland']},
            # France
            {'_id': 'bn:00036202n', 'synsets': ['bn:00079820n', 'bn:00026684n', 'bn:00012208n'], 'labels': ['France']},
            # United Kingdom
            {'_id': 'bn:00013173n', 'synsets': ['bn:00058082n', 'bn:00023251n'], 'labels': ['UK', 'United Kingdom', 'U.K.']},
            # Franz Fischler
            {'_id': 'bn:03468718n', 'synsets': ['bn:03895618n', 'bn:00063277n'], 'labels': ['Franz Fischler']}
            # {'_id': '', 'synsets': []}
            ]
    coll.insert(docs)
    doc = coll.find({'_id': 'bn:00036202n'}).next()
    print "Test document:"
    print doc


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


def walk(x):    
    sources = list(x[1][0])
    if x[1][1]: 
        adjacents, weights = x[1][1]
    else: # no adjacents
        adjacents, weights = ['__NIL__'], [1]
    assert len(adjacents) > 0
    restart = np.random.rand(len(sources)) <= alpha
    neighbors = choice(adjacents, size=len(sources), p=weights)
    nextSteps = np.where(restart, sources, neighbors)
    return zip(sources, nextSteps)


def build_semantic_structure():
    from pyspark import SparkContext, SparkConf
    conf = (SparkConf().setAppName("semsig2")
            # fix MetadataFetchFailedException: Missing an output location for shuffle
#              .set("spark.yarn.executor.memoryOverhead", "7168")
#              .set("spark.yarn.driver.memoryOverhead", "7168")
#              .set("spark.shuffle.memoryFraction", "0")) 
            )
    sc = SparkContext(conf=conf)
    lines = sc.textFile(input_path)
    fields = lines.filter(lambda line: len(line.split('\t')) == 3) \
                    .map(lambda line: line.strip().split('\t'))
#     print fields.take(10)
    vcoming = fields.map(lambda f: (f[2], f[0]))
    vleaving = fields.map(lambda f: (f[0], f[2]))
    corners = vcoming.cogroup(vleaving)
#     corners.saveAsTextFile('hdfs://master.ib.cluster:8020/user/minhle/corners.out')
#     print corners.take(10)

    bridges = corners.flatMap(lambda c: [((u, c[0]), set(c[1][1])) for u in c[1][0]] +
                                        [((c[0], v), set(c[1][0])) for v in c[1][1]])
    weights = bridges.reduceByKey(lambda x, y: x.intersection(y)) \
                        .mapValues(lambda x: len(x)+1)
    weights.saveAsTextFile('hdfs://master.ib.cluster:8020/user/minhle/weights.out')
    
#     adjacents = weights.map(lambda x: (x[0][0], (x[0][1], x[1]))).groupByKey()
#     adjacents = adjacents.mapValues(lambda x: (np.array([v[0] for v in x]),
#                                                np.array([v[1] for v in x]) / float(sum(v[1] for v in x))
#                                                if x else np.array([])))
#     adjacents.persist()
# #     print adjacents.take(10)
#     visits = adjacents.map(lambda x: (x[0], x[0]))
#     edges = sc.parallelize([])
#     for _ in range(10):
#         visits = (visits.map(lambda x: (x[1], x[0])).groupByKey()
#                   .leftOuterJoin(adjacents).flatMap(walk))
# #         visits.persist()
#         edges = (edges.cogroup(visits.filter(lambda x: x[1] != '__NIL__' and x[0] != x[1])
#                                .map(lambda x: (x, 1)))
#                  .mapValues(lambda x: sum(x[0])+sum(x[1])))
#     edges = edges.filter(lambda x: x[1] >= eta).map(lambda x: x[0]).groupByKey()
#     edges.saveAsTextFile('hdfs://master.ib.cluster:8020/user/minhle/relations.out')
    sc.stop()


if __name__ == '__main__':
#     create_sample_db()
    build_semantic_structure()
