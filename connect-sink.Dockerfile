FROM confluentinc/cp-kafka-connect:7.6.1
RUN confluent-hub install --no-prompt jcustenborder/kafka-connect-redis:latest