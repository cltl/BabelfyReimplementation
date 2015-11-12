OUTPUT=/mnt/scistor1/group/home/minh/relations.txt
BABELNET_HOME=/home/minh/BabelNet-API-2.5.1/
BLOOKUP_HOME=/home/minh/babelnet-lookup
FROM=bn:05125775n

cd $BLOOKUP_HOME
mvn clean package
cd $BABELNET_HOME
java -cp lib/*:$BLOOKUP_HOME:$BLOOKUP_HOME/target/lib/*:$BLOOKUP_HOME/target/babelnet-lookup-0.0.1-SNAPSHOT.jar spinoza.util.TripletGenerator -r -from $FROM > $OUTPUT
