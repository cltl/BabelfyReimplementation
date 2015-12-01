#!/usr/bin/env python
# -- coding: utf-8 --

'''
Created on Apr 22, 2015

@author: Filip Ilievski
'''

from collections import defaultdict
import sys, time, os
from KafNafParserPy import *
import urllib
from pymongo import MongoClient
import re, urlparse
import nltk
import re
from nltk.tag import StanfordPOSTagger

host="localhost"
port=9000
lang="en"

st=StanfordPOSTagger('/scratch/fii800/BabelfyReimplementation/stanford-postagger-2014-06-16/models/english-bidirectional-distsim.tagger', path_to_jar='/scratch/fii800/BabelfyReimplementation/stanford-postagger-2014-06-16/stanford-postagger-3.4.jar')

def init_db():
    global db, adjct_coll, adjctr_coll, adjctw_coll, semsig_coll, name_coll
    db = client['semsig-db']
    adjct_coll = db['adjct-coll']
    adjctr_coll = db['adjctr-coll']
    adjctw_coll = db['adjctw-coll']
    semsig_coll = db['semsig-coll']
    name_coll = db['name-coll']

def urlEncodeNonAscii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

def iriToUri(iri):
    parts= urlparse.urlparse(iri)
    return urlparse.urlunparse(
        part.encode('idna') if parti==1 else urlEncodeNonAscii(part.encode('utf-8'))
        for parti, part in enumerate(parts)
    )

def get_id_not_used(used_ids):
    n = 1
    while True:
        possible_id = 'e'+str(n)
        if possible_id not in used_ids:
            return possible_id
        n += 1

def create_bn_synset(v):
    if len(v)>10:
	return v
    l=len(v)
    while l<9:
	v="0" + v
	l+=1
    v="bn:" + v
    return v

def test_phrase(query, t):
    print query
    url = "http://%s:%d/text/%s/%s/%s" %(host, port, lang, query,t)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        synsets = f.read().strip().split("\n")
        return synsets
    else:
        return None

def partial_test_phrase(query, t):
    query=query.replace(" ", "_")
    results = name_coll.find({'$text': {'$search': query}})
    ret=[]
#    regex = re.compile('\(.+?\)')
    for r in results:
	x=0.0
	for sense in r["senses"]:
#	    out_s = regex.sub('', sense)
#	    out_s=out_s.split(',')[0]
 	    if query in sense:
		x+=1.0
	if x/len(r["senses"])>=0.5:
	    ret.append(r["_id"])
    return ret

def is_entity(query):
    url = "http://%s:%d/%s/type" %(host, port, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        lines = f.read().strip().split("\n")
        return lines[0]=="ENTITY"
    else:
	print "error"
        return None   

def get_dbpedia_url(query):
    url = "http://%s:%d/synset/%s/dbpedia_uri/en" %(host, port, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        lines = f.read().strip().split("\n")
        l = lines[0].replace("Dbpedia", "dbpedia").replace("DBpedia", "dbpedia")
        return l
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

def get_nouns(raw_text):
    nouns={}
    tokens=raw_text.split()
    tags = st.tag(tokens)
    tags2 = {}
    words={}
    c=0
    for t in tags:
	c+=1
	words[str(c)]=t[0]
	tags2[str(c)]=t[1]
        if t[1] in ["NN", "NNP", "NNS", "NNPS"]:
            nouns[str(c)]=t[0]
	    
    return c, words, nouns, tags2

def get_adjectives_and_verbs(raw_text, wt):
    tokens=nltk.word_tokenize(raw_text)
    tags = nltk.pos_tag(tokens)
    c=0
    adj={}
    verbs={}
    for t in tags:
	c+=1
        if 'a' in wt and t[1] in ["JJ", "JJS", "JJR"]:
            adj[str(c)]=lmtzr.lemmatize(t[0], pos='a')
	elif 'v' in wt and "VB" in t[1]:
	    verbs[str(c)]=lmtzr.lemmatize(t[0], pos='v')
    return adj,verbs

def test_fragments_with_length(l, noun_token, max_value, words, tags, my_tag):
    t = int(noun_token)
    min_value=1
    left=t-l+1
    right=t
    ret=[]
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
            f.append(str(temp))
            temp+=1
        
        # Fragment is OK. Test it on BabelNet now:
        phrase=""
        fragment=[]
	e=True
        for word in f:
	    if tags[str(word)] not in ["NNP", "NNPS"]:
		e=False
	    if "NN" in tags[str(word)]: # noun or proper noun
		x='n'
	    elif "VB" in tags[str(word)]: # verb
		x='v'
	    elif "JJ" in tags[str(word)]: # adjective
		x='a'
	    elif "RB" in tags[str(word)]: # adverb
		x='r'
	    else:
		x=None
	    if x:
                fragment.append(lmtzr.lemmatize(words[str(word)], x))
	    else:
		fragment.append(lmtzr.lemmatize(words[str(word)]))
        phrase=" ".join(fragment)
#        result=test_phrase(phrase, my_tag)
	if e==True: # NE
		print "NE", phrase
		result=partial_test_phrase(phrase, my_tag)
        	if result or l==1:
            	    ret.append({'phrase': phrase, 'senses': result, 'fkey': "-".join(f), 'wtype': 'e'})
	else: # Noun
		result=test_phrase(phrase, my_tag)
		if result:
		    ret.append({'phrase': phrase, 'senses': result, 'fkey': "-".join(f), 'wtype': 'n'})
        left+=1
        right+=1
    return ret

def get_candidates(raw_text):
    joint_json = {}
    max_token, words, nouns, tags = get_nouns(raw_text)
    print nouns
    sys.exit(0)
    for noun in nouns:
        l=5
        while l>0:
            result=test_fragments_with_length(l, noun, max_token, words, tags, "n")
            if len(result)>1:
		for r in result:
                	joint_json[r["fkey"]]={"phrase": r['phrase'], "senses": r['senses'], "type": r['wtype']}
	    l-=1
    return joint_json

def get_graph_node_for_sense_fragment_combination(Gr, v, f):
    h2 = list(n for n,d in Gr.nodes_iter(data=True) if d['sense']==v and d['fragment']==f)
    if len(h2):
        return h2[0]	
    else:
	print v, f, "error with getting node"
	return None

if __name__ == '__main__':
    #client = MongoClient()
    #init_db()
    all_senses=[]
    path="../kore50.naf/"
    for filename in os.listdir(path):
	my_parser = KafNafParser(path + filename)
        F = get_candidates(my_parser.get_raw()) # Second argument is a string of characters. Add 'e' for entities (always there), 'n' for nouns, 'v' for verbs, 'a' for adjectives
#	print F
        for f in F:
            for sense in F[f]["senses"]:
	        sense=create_bn_synset(sense)
                if sense not in all_senses:
                    all_senses.append(sense)
#	break
    w = open("remaining_kore50.txt", "w")
    w.write("\n".join(all_senses))
    w.close()
