# encoding: utf-8
'''
evaluation.tests.evaluation -- Evaluate the performance of some system based on the output it makes
'''

import os
from evaluation import eval_dir, write_reports
from logging.config import fileConfig

#fileConfig('logging.cfg')

#aida_path = 'evaluation/CATNAFCROMER_airbus'
#assert os.path.exists(aida_path)
#kore50_path = '../../..//kore50.naf'
#assert os.path.exists(kore50_path)
# ref = (None, 
#        aida_path, 
#        kore50_path)
ref = ('AIDA', '/home/fii800/kore50-naf.gold.raw')

# put your targets here
# each target should be a *TUPLE* of a resource label and directories storing
# NAF files, for example:
# targets = (('spotlight_v1', 
#             'aida-conll-naf.evaluation.spotlight', 
#             'kore50-naf.evaluation.spotlight'),
#            (...))
# targets = (('AIDA', 
#             'evaluation/aida-conll-naf.gold', 
#             'evaluation/kore50-naf.gold'),)
targets = (('babelfy', '/home/fii800/proc_kore50'),)
assert targets

for tar in targets:
    for tar_dir, ref_dir in zip(tar[1:], ref[1:]):
        eval_dir(tar_dir, ref_dir, tar[0], ref[0])
write_reports('evaluation')
