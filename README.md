# BabelfyReimplementation

This is the Git repository of our experiment on reimplementing Babelfy.

Setup
======

1. Setup local BabelNet endpoint - Please go to https://github.com/minhlab/babelnet-lookup and setup your own BabelNet API endpoint (useful for non-Java programs).

2. Populate your local database (we use mongodb), in order to access all BabelNet data easily and perform lookups on partial matches. To do this, run semsig.sh with argument phase1. Make sure you have the path to relations.txt setup correctly.
 
3. Generate candidates (run python candidates.py) -> Section 6 of the paper
 
4. Generate semantic signature and the other database structures (run semsig.sh with phase2 and phase3 as arguments). -> Algorithm 1 in the paper

5. Do the Babelfy disambiguation algorithm (run python disambiguate.py) -> Algorithm 2 and 3 in the paper

6. Evaluate !
