#!/usr/local/bin/python2.7
# encoding: utf-8
'''
evaluation.convert -- Convert AIDA format (as in KORE50, AIDA-CoNLL) into NAF files
'''

import codecs
import os
import re
import sys
import time
import traceback
from lxml import etree


def decode_yago(s):
    s = re.sub(u'\\\\u(.{4})', lambda match: unichr(int(match.group(1), 16)), s)
    return s


def text2naf(doc_text, gen_entities):
    # prepare NAF document
    naf = etree.Element("NAF")
    naf.append(etree.Element('nafHeader'))
    naf.attrib['{http://www.w3.org/XML/1998/namespace}lang'] = "en"
    naf.set('version', '1.0')
    naf.append(etree.Element('fileDesc', attrib={'creationtime':time.strftime('%Y-%m-%d')}))
    raw = etree.Element("raw")
    naf.append(raw)
    text = etree.Element("text")
    naf.append(text)
    terms = etree.Element("terms")
    naf.append(terms)
    entities = etree.Element("entities")
    if gen_entities:
        naf.append(entities)
    raw_text = u''
    # process sentences
    sentences = doc_text.split('\n\n')
    curr_span = None
    tok_index = 0
    for sen_index, sen in enumerate(sentences):
        token_strs = sen.strip().split('\n')
        for tok in token_strs: 
            # extract
            fields = tok.strip().split('\t')
            token = fields[0]
            if len(fields) > 1:
                label = fields[1]
                if label == 'B':
#                     full_mention = fields[2] 
                    if len(fields) > 4:
                        yago_entity = fields[4]
                        yago_entity = yago_entity.replace('http://en.wikipedia.org/wiki/',
                                                          'http://dbpedia.org/resource/') 
                    else:
                        yago_entity = decode_yago(fields[3])
#                         import urllib, urllib2
#                         try:
#                             if '--NME--' not in yago_entity:
#                                 urllib2.urlopen('http://en.wikipedia.org/wiki/' + 
#                                                 urllib.quote(yago_entity.encode('utf-8'))).read() 
#                         except:
#                             print yago_entity
            else:
                label = ''
            # construct
            wf = etree.Element("wf", attrib={'id':'w%d' % (tok_index + 1), 
                                             'offset':str(len(raw_text)), 
                                             'length':str(len(token)), 
                                             'sent':str(sen_index + 1)})
            wf.text = token
            text.append(wf)
            raw_text = raw_text + (' ' if raw_text else '') + token
            

            term_attribs = {'id': 't'+str(tok_index + 1),
#                             'lemma': wf_sem.attrib['lemma'],
#                             'pos': wf_sem.attrib['pos']'
                            }
            term = etree.Element('term',
                                 attrib=term_attribs)
            terms.append(term)
            
            term_span =  etree.Element('span')
            term.append(term_span)
            term_target = etree.Element('target', attrib={'id': wf.get('id')})
            term_span.append(term_target)
                
            target = etree.Element('target', {'id':term.get('id')})
            if label:
                if label == 'B':
                    entity = etree.Element('entity', 
                                           {'id':'t%d' %(len(entities) + 1)})
                    curr_span = etree.Element('span')
                    curr_span.append(target)
                    refs = etree.Element('references')
                    refs.append(curr_span)
                    entity.append(refs)
                    extRefs = etree.Element('externalReferences')
                    extRefs.append(etree.Element('externalRef', attrib={
                                                 'resource':'AIDA', 
                                                 'reference':yago_entity}))
                    entity.append(extRefs)
                elif label == 'I':
                    curr_span.append(target)
                else:
                    raise ValueError("Unsupported label: %s" % label)
                entities.append(entity)
            else:
                curr_span = None
            tok_index += 1
            # end for token
        # end for sentence
    raw.text = raw_text
    return naf


def get_wf_ids(entity):
    return [target.attrib['id'] for target in entity.findall('target')]
 

def convert(inpath, output_dir, gen_entities):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with codecs.open(inpath, encoding='utf-8') as f:
        content = f.read()
    documents = content.split('-DOCSTART-')
#     print documents
    for doc in documents:
        doc = doc.strip()
        if not doc: continue
        m = re.match("\\((.+?)\\)", doc)
        assert m, "Unrecognized document ID in %s" %doc
        doc_id = m.group(1).strip().replace(' ', '_')
        try:
            doc_text = doc[m.end(0):].strip()
            naf = text2naf(doc_text, gen_entities) 
            outpath = os.path.join(output_dir, doc_id + '.naf')
            with open(outpath, "wt") as out:
                out.write(etree.tostring(naf, xml_declaration=True, pretty_print=True))
                print "Written to %s" % outpath
        except:
            sys.stderr.write("Error while processing %s\n" %doc_id)
            traceback.print_exc()

if __name__ == '__main__':
    home_dir = os.path.dirname(__file__)
    conll_path = os.path.join(home_dir, 'AIDA-YAGO2-dataset.tsv')
    os.path.exists(conll_path)
    kore50_path = os.path.join(home_dir, 'AIDA.tsv') 
    os.path.exists(kore50_path)
    
    convert(conll_path, 'aida-conll-naf.gold', True)
    convert(conll_path, 'aida-conll-naf', False)
    convert(kore50_path, 'kore50-naf.gold', True)
    convert(kore50_path, 'kore50-naf', False)