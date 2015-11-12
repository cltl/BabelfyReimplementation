# path to where to store DATA 
# (you should have writing permission and enough disk space)
DBPATH=/home/fii800/BabelNet/semsig_files/mongodb

mongod --quiet --dbpath $DBPATH > /dev/null 2>&1 &
sleep 10
python semsig.py phase3 -y 2>&1 | tee semsig.out
