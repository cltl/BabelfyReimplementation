#!/usr/bin/env python
# -- coding: utf-8 --

'''
Created on Apr 22, 2015

@author: Filip Ilievski
'''

import networkx as nx
import sys, time, os
from KafNafParserPy import *
import urllib
from pymongo import MongoClient
import re, urlparse
from nltk.tag.stanford import POSTagger

host="localhost"
port=9000
lang="en"

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
    l=len(v)
    while l<9:
	v="0" + v
	l+=1
    v="bn:" + v
    return v

def test_phrase(query, t):
    url = "http://%s:%d/text/%s/%s/%s" %(host, port, lang, query,t)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        synsets = f.read().strip().split("\n")
        return synsets
    else:
        return None

def partial_test_phrase(query):
    query=query.replace(" ", "_")
    results = name_coll.find({'$text': {'$search': query}})
    ret=[]
    for r in results:
#        x=0.0
#        for sense in r["senses"]:
#            if query in sense:
#                x+=1.0
#        if x/len(r["senses"])>=0.5:
         ret.append(r["_id"])
    return ret

def is_entity(query):
    url = "http://%s:%d/synset/%s/type" %(host, port, query)
    url = iriToUri(url)
    f = urllib.urlopen(url)
    if f.getcode() == 200:
        lines = f.read().strip().split("\n")
	print lines
        return lines[0]=="NAMED_ENTITY"
    else:
	print query, "error"
        return False  

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

def get_nouns(parser):
    nouns={}
    terms=[]
    for term in parser.get_terms():
	target_ids=term.get_span().get_span_ids()
    	term_text=[]
	for tid in target_ids:
            term_text.append(parser.get_token(tid).get_text())
        res=(" ").join(term_text)
	terms.append(res)
    tags = st.tag(terms)
    c=0
    words={}
    for t in tags[0]:
        c+=1
        words[str(c)]=t[0]
        if t[1] in ["NN", "NNP", "NNS", "NNPS"]:
            nouns[str(c)]=t[0]
    return c, words, nouns

def test_fragments_with_length(l, noun_token, max_value, words):
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
        for word in f:
        	fragment.append(words[str(word)])
        phrase=" ".join(fragment)
        result=partial_test_phrase(phrase)
	if result:
		ret.append({'phrase': phrase, 'senses': result, 'fkey': "-".join(f)})
        left+=1
        right+=1
    return ret

# Deprecated
"""
def identify_candidates(my_parser):
    raw_text = my_parser.get_raw()
    joint_json = {}
    max_token, words, nouns, tags = get_nouns(raw_text)
    for noun in nouns:
        l=5
        while l>0:
            result=test_fragments_with_length(l, noun, max_token, words, tags)
            if result is not None:
                phrase, senses, key, ent_bool = result
                joint_json[key]={"phrase": phrase, "senses": senses, "entity": ent_bool}
            l-=1
    return joint_json
"""

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

def get_fragments_fraction(n, Gr):
    adj_num=0.0
    succ=Gr.neighbors(n)
    pred=Gr.predecessors(n)
    adjs=list(set(succ) | set(pred))
    frags=[]
    for adj in adjs:
	fragment=G.node[adj]["fragment"]
	if fragment not in frags:
	    frags.append(fragment)
	    adj_num+=1.0
#    for f2 in F:
#	connected=False
#	for s2 in F[f2]['senses']:
#	    n2=get_graph_node_for_sense_fragment_combination(Gr, s2, f2)
#	    if Gr.has_edge(n, n2) or Gr.has_edge(n2, n):
#		connected=True
#	if connected:
#	    adj_num+=1.0
    return adj_num

def compute_total_score(f, F, Gr):
    senses=F[f]["senses"]
    total=0.00000001
    for s in senses:
	#print "sense, fragment", s, f
	n=get_graph_node_for_sense_fragment_combination(Gr, s, f)
	degree=Gr.degree(n)
	weight=get_fragments_fraction(n, Gr)/(len(F)-0.9999999)
	total+=weight*degree
    return total

def compute_all_scores(F, Gr):
    for f in F:	
	#total_senses_fraction = compute_total_score(f, F, Gr)
	for v in F[f]["senses"]:
	    sense_scores[f][v]=compute_score(f, F, Gr, v)

def compute_score(f, F, Gr, sense):
    n=get_graph_node_for_sense_fragment_combination(Gr, sense, f)
    degree=Gr.degree(n)
    lenF=len(F)
    weight=get_fragments_fraction(n, Gr)/(lenF-0.9999999)
    sense_score=weight*degree
    return sense_score

def min_score_for_f(f, F, Gr):
    min_sense=None
    min_score=1000000.0
    for vkey in F[f]["senses"]:
	score=sense_scores[f][vkey]
	if score<min_score:
	    min_score=score
	    min_sense=vkey
    return min_sense

def max_score_for_f(f, F, Gr):
    max_sense=None
    max_score=-0.01
    total_senses_fraction = compute_total_score(f, F, Gr)
    for v in F[f]["senses"]:
	score=compute_score(f, F, Gr, v)/total_senses_fraction
	if score>max_score:
	    max_score=score
	    max_sense=v
    return max_sense, max_score

def update_scores(F, G, node_del):
    succ=G.neighbors(node_del)
    pred=G.predecessors(node_del)
    adjs=list(set(succ) | set(pred))
    for adj in adjs:
	f = G.node[adj]["fragment"]
	v = G.node[adj]["sense"]
	sense_scores[f][v]=compute_score(f, F, G, v)

def avg_degree(Gr):
    return 2.0*Gr.number_of_edges()/len(Gr)

def densest_subgraph(F, G, mu):
    G_star = G.copy()
    G_temp = G_star.copy()
    F_star = F
    compute_all_scores(F, G) # Pre-compute all scores and only update where relevant!
    while True:
	fmax, amb = get_max_ambiguity(F)
	if amb<=mu:
	    break
	v_min=min_score_for_f(fmax, F, G_temp)
	F[fmax]["senses"].remove(v_min)
	graph_node = get_graph_node_for_sense_fragment_combination(G_temp, v_min, fmax)    
	update_scores(F, G_temp, graph_node)
	G_temp.remove_node(graph_node) #remove_node_and_all_its_edges(G_temp, v_min) 
	if avg_degree(G_temp)>avg_degree(G_star):
	    G_star=G_temp.copy()
	    F_star=F
    return G_star, F_star

def get_candidates(parser):
    joint_json = {}
    max_token, words, nouns = get_nouns(parser)
    for noun in nouns:
        l=5
        while l>0:
            result=test_fragments_with_length(l, noun, max_token, words)
            if len(result):
                for r in result:
                        joint_json[r["fkey"]]={"phrase": r['phrase'], "senses": r['senses']}
            l-=1
    return joint_json

#sense_weights={} # past: sense_scores
#sense_degrees={} # past: sense_scores
#fragment_total_scores={} # this is the divisor in the scores computation equation
sense_scores={}
st = POSTagger('stanford-postagger-2014-06-16/models/english-bidirectional-distsim.tagger', 'stanford-postagger-2014-06-16/stanford-postagger.jar')

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

    path="/home/fii800/kore50-naf/"
    out_path="/home/fii800/proc_kore50/"
    all_senses=[]
    for filename in os.listdir(path):
	
	my_parser = KafNafParser(path + filename)
	print filename
	output = out_path + filename
	init_db()

	F = get_candidates(my_parser) # Second argument is a string of characters. Add 'e' for entities (always there), 'n' for nouns, 'v' for verbs, 'a' for adjectives
	for f in F:
		for sense in F[f]["senses"]:
			if sense not in all_senses:
				all_senses.append(sense)		
	continue
        G=nx.DiGraph() # Create empty networkx Graph


	sense_scores={}
	
	# Add vertices (lines 4-8, alg. 2)
	count=1
	for f in F: # Iterate through the mentions
	    new_senses=[]

	    sense_scores[f]={}
	    for sense in F[f]['senses']: # Iterate through the senses of the mention
	        # First add all nodes, with information on the mention (fragment)
		if "bn:" in sense:
	        	sense=sense[3:].strip("0")
	        G.add_node(count, sense=sense, fragment=f)
	        new_senses.append(sense)
	        count+=1
	    F[f]['senses']=new_senses
	#print count
	# Now add all the edges
	for f in F: # Iterate through the mentions
	    for v in F[f]['senses']: # Iterate through the senses of the mention
	        my_node=get_graph_node_for_sense_fragment_combination(G, v, f)
		#sense = create_bn_synset(v)
		#print v
	        entry_v = semsig_coll.find_one({'_id': v})
	        semsig_v = entry_v['semsig']
	        for f2 in F:
		    for v2 in F[f2]['senses']:
		        if f!=f2 and v2 in semsig_v:
			    node2 = get_graph_node_for_sense_fragment_combination(G, v2, f2)
			    G.add_edge(my_node, node2)

	G_star, F_star = densest_subgraph(F, G, mu) # Algorithm 2
	used_ids = set()
    	for existing_entity in my_parser.get_entities():
            used_ids.add(existing_entity.get_id())
	for f in F_star:
	    len_senses = len(F_star[f]["senses"])
	    term_ids = []
	    for t in f.split("-"):
		term_ids.append("t" + t)
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
	    max_v=None
	    if len_senses: 
	        max_v, max_score = max_score_for_f(f, F_star, G_star)
	        if max_score>=theta:
		    bn_res = create_bn_synset(max_v)
		    dbpedia_url = get_dbpedia_url(bn_res)
            	    ext_ref.set_reference(dbpedia_url.decode("ISO-8859-1")[28:])
            	else:
		    ext_ref.set_reference("--NME--")
	    else:
		ext_ref.set_reference("--NME--")
	    if max_v and is_entity(create_bn_synset(max_v)):
		ext_ref.set_confidence("1.0")
                new_entity.add_external_reference(ext_ref)
	        my_parser.add_entity(new_entity)
	my_parser.dump(output)

    w=open("all_synsets.txt", "w")
    for s in all_senses:
	w.write("%s\n" % s)
    w.close()
