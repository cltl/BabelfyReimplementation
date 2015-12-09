# BabelfyReimplementation

This is the Git repository of our experiment on reimplementing Babelfy.

Setup
======

Steps 1-4 need to be executed once for good. Steps 5-8 need to be executed once per test set.

1. Setup local BabelNet endpoint - Please go to https://github.com/minhlab/babelnet-lookup and setup your own BabelNet API endpoint (useful for non-Java programs).

2. Run `./genrel.sh` (make sure you adjust the settings to your local environment). This script generates a text file called `relations.txt` with all triples in BabelNet. It also creates `name_coll` database collection in MongoDB which contains all names from BabelNet. This is essential for the process of generating candidates using partial matching.

3. Populate your local database (we use mongodb), in order to access all BabelNet data easily and perform lookups on partial matches. To do this, run `semsig.sh phase1`. Make sure you have the path to `relations.txt` setup correctly.
Duration: 100 min

4. Run `semsig.sh phase2` to generate weights based on triangular relations. These weights are useful for the building of semantic signature later. -> Described in Section 5 of the paper
Duration: 7.5 hours

5. Generate candidates (run python candidates.py) -> Section 6 of the paper
Duration: 17 mins
 
6. Generate semantic signature database structure (run `semsig.sh phase3`). -> Algorithm 1 in the paper, section 5
Duration: ~3 days

7. Do the Babelfy disambiguation algorithm (run python disambiguate.py) -> Algorithm 2 and 3 in the paper, section 7

8. Evaluate !
