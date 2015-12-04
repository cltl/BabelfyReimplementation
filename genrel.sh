BABELNET_HOME=/scratch/fii800/BabelNet/BabelNet-API-2.5.1/
BLOOKUP_HOME=/scratch/fii800/BabelNet/babelnet-lookup

cd $BLOOKUP_HOME
mvn clean package
cd $BABELNET_HOME
#java -cp lib/*:$BLOOKUP_HOME:$BLOOKUP_HOME/target/lib/*:$BLOOKUP_HOME/target/babelnet-lookup-0.0.1-SNAPSHOT.jar spinoza.util.TripletGenerator -r -from $FROM > $OUTPUT

# to build name collection
java -cp lib/*:$BLOOKUP_HOME:$BLOOKUP_HOME/target/lib/*:$BLOOKUP_HOME/target/babelnet-lookup-0.0.1-SNAPSHOT.jar spinoza.util.BabelNet2MongoDB
