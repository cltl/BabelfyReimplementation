# BabelfyReimplementation

This is the Git repository of our experiment on reimplementing Babelfy.

Setup
======

1. Setup local BabelNet endpoint - Please go to https://github.com/minhlab/babelnet-lookup and setup your own BabelNet API endpoint (useful for non-Java programs).

2. Populate your local database (we use mongodb), in order to access all BabelNet data easily and perform lookups on partial matches. To do this, run semsig.sh with argument phase1. Make sure you have the path to relations.txt setup correctly.
Duration: 100 min

3. Run semsig.sh with argument phase2, to generate weights based on triangular relations. These weights are useful for the building of semantic signature later. -> Described in Section 5 of the paper
Duration: 7.5 hours

4. Generate name_coll database collection, which contains all names from BabelNet. This is essential for the process of generating candidates using partial matching. To populate this collection run ./genrel.sh (make sure you adjust the settings to your local environment).
Duration : 50 min
 
------- The steps 1-4 need to be executed once for good! --------

5. Generate candidates (run python candidates.py) -> Section 6 of the paper
Duration: 17 mins
 
6. Generate semantic signature database structure (run semsig.sh with phase3 as an argument). -> Algorithm 1 in the paper, section 5

7. Do the Babelfy disambiguation algorithm (run python disambiguate.py) -> Algorithm 2 and 3 in the paper, section 7

8. Evaluate !
