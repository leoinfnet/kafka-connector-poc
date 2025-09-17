FROM confluentinc/cp-kafka-connect:7.6.1
RUN confluent-hub install --no-prompt jcustenborder/kafka-connect-redis:latest
RUN confluent-hub install --no-prompt confluentinc/kafka-connect-transform-filter:1.0.0