'''
Created on Dec 4, 2014

@author: Minh Ngoc Le
'''
import unittest
import os
import evaluation
from evaluation import eval_file, eval_dir, write_reports
from tempfile import mkdtemp

sample_dir = os.path.join(os.path.dirname(__file__), "sample")
sample_gold_dir = os.path.join(os.path.dirname(__file__), "sample.gold")

class Test(unittest.TestCase):


    def setUp(self):
        evaluation.records = []


    def test_eval_file(self):
        fname = '1_CEL01.naf'
        tar = os.path.join(sample_dir, fname)
        ref = os.path.join(sample_gold_dir, fname)
        eval_file(tar, ref, 'reranker')
        self.assertEqual(1, len(evaluation.records))
        self.assertEqual((fname, 3, 2, 5, 0, 6), evaluation.records[0])


    def test_eval_dir(self):
        eval_dir(sample_dir, sample_gold_dir, 'reranker')
        self.assertEqual(2, len(evaluation.records))
        
        
    def test_write_report(self):
        d = mkdtemp(prefix='test_eval_')
        eval_dir(sample_dir, sample_gold_dir, 'reranker')
        write_reports(d)
        files = os.listdir(d)
        self.assertTrue("details.tsv" in files)
        self.assertTrue("summary.tsv" in files)
        print "Reports written to %s" %d
        


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test_eval_file']
    unittest.main()