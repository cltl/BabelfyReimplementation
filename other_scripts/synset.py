'''
Created on Mar 26, 2015

@author: Minh Ngoc Le
'''
import os
from babelfy_me import identify_candidates
import sys

# paths = ['evaluation/aida-conll-naf', 'evaluation/kore50-naf']
paths = 'aida-test.naf' 

def add_synsets_from(paths):
    if not isinstance(paths, (list, tuple)):
        paths = (paths,)
    for path in paths:
        if os.path.isdir(path):
            add_synsets_from((os.path.join(path, filename)
                              for filename in os.listdir(path)))
        else:
            sys.stderr.write("Processing %s... " %path)
            candidates = identify_candidates(path)
            for key in candidates:
                synsets.update(candidates[key]['senses'])
            sys.stderr.write("Done.\n")

if __name__ == '__main__':
    synsets = set()
    add_synsets_from(paths)
    for s in synsets:
        print s
