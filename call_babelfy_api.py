'''
Created on Apr 28, 2015

@author: Minh Ngoc Le
'''
from ConfigParser import ConfigParser
from StringIO import StringIO
from collections import defaultdict
import gzip
import json
import os
import re
import urllib
import urllib2
import numpy as np
from evaluation.convert import decode_yago
import sys


assert os.path.exists('config.cfg')
config = ConfigParser()
config.read('config.cfg')

data_path='evaluation/AIDA.tsv'
# data_path='evaluation/AIDA-YAGO2-dataset.tsv'
assert os.path.exists(data_path)
continue_from_doc_id=None
# continue_from_doc_id='126 Ukraine'
raw_babelfy_path='AIDA-babelfy.out'
# raw_babelfy_path='AIDA-YAGO2-babelfy.out'

service_url = 'https://babelfy.io/v1/disambiguate'

lang = 'EN'
key  = config.get('babelnet', 'key')


def process_document(text, out):
    params = {
        'text' : text,
        'lang' : lang,
        'match' : 'PARTIAL_MATCHING',
#         'cands': 'ALL', 
        'key'  : key,
    }
    url = service_url + '?' + urllib.urlencode(params)
    request = urllib2.Request(url)
    request.add_header('Accept-encoding', 'gzip')
    response = urllib2.urlopen(request)
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO( response.read())
        f = gzip.GzipFile(fileobj=buf)
        out.write(text)
        out.write('\n')
        out.write(f.read())
        out.write('\n')
        out.write('\n')
#         # retrieving data
#         for result in data:
#                     # retrieving token fragment
#                     tokenFragment = result.get('tokenFragment')
#                     tfStart = tokenFragment.get('start')
#                     tfEnd = tokenFragment.get('end')
#                     print str(tfStart) + "\t" + str(tfEnd)
#     
#             # retrieving char fragment
#                     charFragment = result.get('charFragment')
#                     cfStart = charFragment.get('start')
#                     cfEnd = charFragment.get('end')
#                     print str(cfStart) + "\t" + str(cfEnd)
#     
#                     # retrieving BabelSynset ID
#                     synsetId = result.get('babelSynsetID')
#                     print synsetId
                    
if __name__ == '__main__':
    # obtain BabelFy annotations
    if (not os.path.exists(raw_babelfy_path)) or (continue_from_doc_id is not None):
        with open(raw_babelfy_path, 'a') as out:
            with open(data_path) as f:
                doc_id = None
                doc = []
                enabled = (continue_from_doc_id is None)
                for line in f:
                    line = line.strip()
                    if line.startswith('-DOCSTART-'):
                        if enabled and len(doc) > 0:
                            out.write("%s\n" %doc_id)
                            process_document(" ".join(doc), out)
                        doc_id = re.search('-DOCSTART- \\((.+)\\)', line).group(1)
                        if doc_id == continue_from_doc_id: 
                            enabled = True
                        doc = []
                    else:
                        if len(line) > 0:
                            doc.append(line.split('\t')[0])
                if len(doc) > 0 and enabled:
                    sys.stderr.write("Processing %s...\n" %doc_id)
                    out.write("%s\n" %doc_id)
                    process_document(" ".join(doc), out) # last one
    
    # obtain gold standard
    gs = defaultdict(dict)
    with open(data_path) as f:
        doc_id = None
        doc = ''
        for line in f:
            line = line.strip()
            if line.startswith('-DOCSTART-'):
                doc_id = re.search('-DOCSTART- \\((.+)\\)', line).group(1)
                doc = ''
            else:
                if len(line) > 0:
                    fields = line.split('\t')
                    start = len(doc)
                    doc += fields[0] + ' '
                    end = len(doc)-1
                    if len(fields) >= 2 and fields[1] == 'B':
                        if len(fields) > 4:
                            yago_entity = fields[4]
                            yago_entity = yago_entity.replace('http://en.wikipedia.org/wiki/', '') 
                        else:
                            yago_entity = decode_yago(fields[3])
                        gs[doc_id][(start, end)] = yago_entity
    
    # measure performance
    with open(raw_babelfy_path) as f:
        print "document\tcorrect\ts.correct\ttotal_tar\ttotal_gs\tP\tR\tF1\ts.P\ts.R"
        records = []
        while True:
            doc_id = f.readline().strip()
            if not doc_id: break
            doc_text = f.readline().strip()
            babelfy_output = f.readline()
            f.readline() # blank line
            
            anns = json.loads(babelfy_output)
            total_gs = len(gs[doc_id])
            total_tar = 0
            correct = 0
            span_correct = 0
            for ann in anns:
                boundaries = (ann['charFragment']['start'], ann['charFragment']['end']+1)
                entity = ann['DBpediaURL'].replace('http://dbpedia.org/resource/', '')
                bnId = ann['babelSynsetID']
                url = "http://%s:%d/synset/%s/type" %('localhost', 9000, bnId)
                bnType = urllib.urlopen(url).read().strip()
#                 print bnType
                if bnType != 'NAMED_ENTITY':
                    continue
                total_tar += 1
                if boundaries in gs[doc_id]:
                    span_correct += 1
                    print '<tar>', entity, '<gs>', gs[doc_id][boundaries]
                    if gs[doc_id][boundaries] == entity:
                        correct += 1
                else:
                    print '<tar>', entity
            p = correct/float(total_tar) if total_tar != 0 else 0
            r = correct/float(total_gs)
            sp = span_correct/float(total_tar) if total_tar != 0 else 0
            sr = span_correct/float(total_gs)
            f1 = 2/(1/p+1/r) if p!=0 and r!=0 else 0
            print "%s\t%d\t%d\t%d\t%d\t%f\t%f\t%f\t%f\t%f" %\
                (doc_id, correct, span_correct, total_tar, total_gs, p, r, f1, sp, sr)
            records.append((correct, span_correct, total_tar, total_gs))
        records = np.array(records)    
        correct = sum(records[:,0])
        span_correct = sum(records[:,1])
        total_tar = sum(records[:,2])
        total_gs = sum(records[:,3])
        micro_p = correct/float(total_tar)
        micro_r = correct/float(total_gs)
        micro_sp = span_correct/float(total_tar)
        micro_sr = span_correct/float(total_gs)
        print "Micro\t%d\t%d\t%d\t%d\t%f\t%f\t%f\t%f" %\
            (correct, span_correct, total_tar, total_gs, 
             micro_p, micro_r, micro_sp, micro_sr)
        macro_p = np.nan_to_num(records[:,0].astype(float)/records[:,2]).mean()
        macro_r = np.nan_to_num(records[:,0].astype(float)/records[:,3]).mean()
        macro_sp = np.nan_to_num(records[:,1].astype(float)/records[:,2]).mean()
        macro_sr = np.nan_to_num(records[:,1].astype(float)/records[:,3]).mean()
        print "Macro\t\t\t\t\t%f\t%f\t%f\t%f" %\
            (macro_p, macro_r, macro_sp, macro_sr)
