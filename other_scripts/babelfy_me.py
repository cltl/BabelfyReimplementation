#!/usr/bin/env python
# -- coding: utf-8 --

'''
Created on Mar 12, 2015

@author: Filip Ilievski
'''

import networkx as nx
import sys, time, os
from KafNafParserPy import *
import urllib
from pymongo import MongoClient
import re, urlparse

host="localhost"
port=9000
lang="en"

def init_db():
    global db, adjct_coll, adjctr_coll, adjctw_coll, semsig_coll
    db = client['semsig-db']
    adjct_coll = db['adjct-coll']
    adjctr_coll = db['adjctr-coll']
    adjctw_coll = db['adjctw-coll']
    semsig_coll = db['semsig-coll']

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
    l=len(v)
    while l<9:
	v="0" + v
	l+=1
    v="bn:" + v
    return v

def test_phrase(query):
    url = "http://%s:%d/text/%s/%s" %(host, port, lang, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        synsets = f.read().strip().split("\n")
        return synsets
    else:
        return None

def get_dbpedia_url(query):
    url = "http://%s:%d/synset/%s/dbpedia_uri/en" %(host, port, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        lines = f.read().strip().split("\n")
        l = lines[0].replace("Dbpedia", "dbpedia")
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

def identify_candidates(my_parser, filename):
    #get_textual_fragments(my_parser)
    max_token=get_tokens_size(my_parser)
    joint_json = {}
    for noun in get_nouns(my_parser):
    #    found=False
        l=5
        while l>0:
            result=test_fragments_with_length(l, noun, max_token, my_parser)
            if result is not None:
                phrase, senses, key = result
                joint_json[key]={"phrase": phrase, "senses": senses}
            l-=1
    return joint_json

def get_graph_node_for_sense_fragment_combination(Gr, v, f):
    h2 = list(n for n,d in Gr.nodes_iter(data=True) if d['sense']==v and d['fragment']==f)
    if len(h2):
        return h2[0]	
    else:
	print v, f, "error with getting node"
	return None

def get_graph_nodes_for_sense(Gr, v):
    h2 = list(n for n,d in Gr.nodes_iter(data=True) if d['sense']==v)
    return h2

def get_max_ambiguity(F):
    max_amb=0
    max_f=None
    for f in F:
	if len(F[f]["senses"])>max_amb:
	    max_f=f
	    max_amb=len(F[f]["senses"])
    return max_f, max_amb

def get_fragments_fraction(n, f, s, Gr):
    adj_num=0.0
    for f2 in F:
	connected=False
	for s2 in F[f2]['senses']:
	    n2=get_graph_node_for_sense_fragment_combination(Gr, s2, f2)
	    if Gr.has_edge(n, n2) or Gr.has_edge(n2, n):
		connected=True
	if connected:
	    adj_num+=1.0
    return adj_num

def compute_total_score(f, F, Gr):
    senses=F[f]["senses"]
    total=0.00000001
    for s in senses:
	#print "sense, fragment", s, f
	n=get_graph_node_for_sense_fragment_combination(Gr, s, f)
	degree=Gr.degree(n)
	weight=get_fragments_fraction(n, f, s, Gr)/(len(F)-0.9999999)
	total+=weight*degree
    return total

def compute_score(f, F, Gr, sense, senses_score):
    n=get_graph_node_for_sense_fragment_combination(Gr, sense, f)
    degree=Gr.degree(n)
    weight=get_fragments_fraction(n, f, sense, Gr)/(len(F)-0.9999999)
    sense_score=weight*degree
    return sense_score/senses_score;

def min_score_for_f(f, F, Gr):
    min_sense=None
    min_score=1000.0
    total_senses_fraction = compute_total_score(f, F, Gr)
    for v in F[f]["senses"]:
	score=compute_score(f, F, Gr, v, total_senses_fraction)
	if score<min_score:
	    min_score=score
	    min_sense=v
    return min_sense

def max_score_for_f(f, F, Gr):
    max_sense=None
    max_score=0.0
    total_senses_fraction = compute_total_score(f, F, Gr)
    for v in F[f]["senses"]:
	score=compute_score(f, F, Gr, v, total_senses_fraction)
	if score>max_score:
	    max_score=score
	    max_sense=v
    return max_sense

def avg_degree(Gr):
    return 2.0*Gr.number_of_edges()/len(Gr)

def densest_subgraph(F, G, mu):
    G_star = G.copy()
    G_temp = G_star.copy()
    F_star = F
    while True:
	fmax, amb = get_max_ambiguity(F)
	if amb<=mu:
	    break
	#print fmax, "max fragment node"
	v_min=min_score_for_f(fmax, F, G_temp)
	F[fmax]["senses"].remove(v_min)
	graph_node = get_graph_node_for_sense_fragment_combination(G_temp, v_min, fmax)
    	G_temp.remove_node(graph_node) #remove_node_and_all_its_edges(G_temp, v_min) 
	if avg_degree(G_temp)>avg_degree(G_star):
	    G_star=G_temp.copy()
	    F_star=F
	else:
	    print avg_degree(G_temp), avg_degree(G_star)
    return G_star, F_star

if __name__ == '__main__':
    client = MongoClient()
    if len(sys.argv)<2:
	print "Too little arguments. Please add 'wsd' or 'el' to choose your task!"
	sys.exit()
    elif sys.argv[1]=='wsd': # WSD
        mu=10 # Allowed ambiguity level
        theta=0.8 # score boundary
    else: # EL
        mu=5 # Allowed ambiguity level
        theta=0.0 # score boundary

    path="../../kore50.naf/"
    out_path="../../proc_kore50/"
    for filename in os.listdir(path):
    	my_parser = KafNafParser(path + filename)
        F = identify_candidates(my_parser, path + filename)
	output = out_path + filename

    	if os.path.isfile(output):
            continue

        G=nx.DiGraph() # Create empty networkx Graph

	
	# Add vertices (lines 4-8, alg. 2)
	init_db()
	count=1
	for f in F: # Iterate through the mentions
	    new_senses=[]
	    for v in F[f]['senses']: # Iterate through the senses of the mention
	        # First add all nodes, with information on the mention (fragment)
	        sense=v[3:].strip("0")
	        G.add_node(count, sense=sense, fragment=f)
	        new_senses.append(sense)
	        count+=1
	    F[f]['senses']=new_senses
	#print count
	# Now add all the edges
	for f in F: # Iterate through the mentions
	    for v in F[f]['senses']: # Iterate through the senses of the mention
	        my_node=get_graph_node_for_sense_fragment_combination(G, v, f)
	        entry_v = semsig_coll.find_one({'_id': v})
	        semsig_v = entry_v['semsig']
	        for f2 in F:
		    for v2 in F[f2]['senses']:
		        if f!=f2 and v2 in semsig_v:
			    node2 = get_graph_node_for_sense_fragment_combination(G, v2, f2)
			    G.add_edge(my_node, node2)

	for u,v in G.edges():
	    print u,v

	G_star, F_star = densest_subgraph(F, G, mu)
	print "DENSEST SUBGRAPH FOUND!"
	
	used_ids = set()
    	for existing_entity in my_parser.get_entities():
            used_ids.add(existing_entity.get_id())
	for f in F_star:
	    len_senses = len(F_star[f]["senses"])
	    if len_senses:
	        print f, len(F_star[f]["senses"])
	        max_v = max_score_for_f(f, F_star, G_star)
	        if max_v>theta:
		    bn_res = create_bn_synset(max_v)
		    dbpedia_url = get_dbpedia_url(bn_res)
		    print dbpedia_url[28:]
		    term_ids = []
		    for t in f.split("-"):
			term_ids.append(t)
		    new_entity = Centity()
		    new_id = get_id_not_used(used_ids)
		    new_entity.set_id(new_id)
		    used_ids.add(new_id)
		    new_entity.set_comment(F_star[f]["phrase"])
			
		    ref = Creferences()
		    ref.add_span(term_ids)
		    new_entity.add_reference(ref) 
		    ext_ref = CexternalReference()
            	    ext_ref.set_resource("babelfy")
            	    ext_ref.set_reference(dbpedia_url.decode("ISO-8859-1")[28:])
            	    ext_ref.set_confidence("1.0")
            	    new_entity.add_external_reference(ext_ref)
	            my_parser.add_entity(new_entity)
	        else:
		    print max_v, "NOT ENOUGH CONFIDENCE"
	my_parser.dump(output)
