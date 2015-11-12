#!/usr/bin/env python

'''
Created on Mar 12, 2015

@author: Filip Ilievski
'''

import sys, time, os
from KafNafParserPy import *
import urllib
import re, urlparse

host="localhost"
port=9000
lang="en"

def urlEncodeNonAscii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

def iriToUri(iri):
    parts= urlparse.urlparse(iri)
    return urlparse.urlunparse(
        part.encode('idna') if parti==1 else urlEncodeNonAscii(part.encode('utf-8'))
        for parti, part in enumerate(parts)
    )

def test_phrase(query):
    url = "http://%s:%d/text/%s/%s" %(host, port, lang, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        synsets = f.read().strip().split("\n")
        return synsets
    else:
        return None

def get_entity_mention(ent, my_parser):

    for ref in ent.get_references():
        target_ids = ref.get_span().get_span_ids()
        words = []
        for tid in target_ids:
            words.append(my_parser.get_token(tid.replace("t", "w")).get_text())
        res=(" ").join(words)
        return res

def get_nouns(parser):
    nouns=[]
    for token in parser.get_tokens():
        term = parser.get_term(token.get_id().replace("w", "t"))
        term_pos=term.get_pos()
        if term_pos in ["N", "R"]:
            nouns.append(token.get_id())
#            print token.get_id() + " " + term.get_lemma()
    return nouns

def get_tokens_size(parser):
    n=0
    for token in parser.get_tokens():
        n+=1
    return n

def test_fragments_with_length(l, noun_token, max_value, parser):
    min_value=1
    t=int(noun_token.replace("w", "").strip())
    left=t-l+1
    right=t
    ret=None
    while left<=t:
        f=[]
        temp=left
        if left<min_value:
            left+=1
            right+=1
            continue
        if right>max_value:
            break
        while temp<=right:
            f.append("t" + str(temp))
            temp+=1
        
        # Fragment is OK. Test it on BabelNet now:
        phrase=""
        fragment=[]
        for word in f:
            fragment.append(parser.get_term(word).get_lemma())
        phrase=" ".join(fragment)
        result=test_phrase(phrase)
        if result:
            ret = phrase, result, "-".join(f)
#            print ret
        left+=1
        right+=1
    return ret

def get_textual_fragments(parser):
    nouns=get_nouns(parser)
    #print nouns
    fragments=[]
    max_token=get_tokens_size(parser)
    #print max_token
    for l in xrange(1,6):
        for f in get_fragments_with_length(l, nouns, max_token, parser):
            fragments.append(f)
    print len(fragments)
#    parser

def identify_candidates(filename):
    my_parser = KafNafParser(filename)
    #get_textual_fragments(my_parser)
    max_token=get_tokens_size(my_parser)
    joint_json = {}
    s=[]
    for noun in get_nouns(my_parser):
    #    found=False
        l=5
        while l>0:
            result=test_fragments_with_length(l, noun, max_token, my_parser)
            if result is not None:
                phrase, senses, key = result
		for sense in senses:
		    s.append(sense)
            l-=1
    return s

if __name__ == '__main__':
    all_senses=[]
    path="../../kore50.naf/"
    for filename in os.listdir(path):
#     filename = "evaluation/kore50-naf/26_BUS06.naf"
	senses = identify_candidates(path + filename)
	for s in senses:
	    if s not in all_senses:
	        all_senses.append(s)
	print filename
    w = open("synsets_kore50.txt", "w")
    w.write("\n".join(all_senses))
    w.close()
