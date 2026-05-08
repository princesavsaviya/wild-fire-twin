from kafka import KafkaConsumer, TopicPartition
import os

def count_messages(topic_name, bootstrap_servers):
    consumer = KafkaConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=None,
        auto_offset_reset='earliest'
    )
    
    partitions = consumer.partitions_for_topic(topic_name)
    if partitions is None:
        print(f"Topic {topic_name} not found.")
        return 0

    total_count = 0
    for partition in partitions:
        tp = TopicPartition(topic_name, partition)
        # Get beginning and end offsets
        beginning_offsets = consumer.beginning_offsets([tp])
        end_offsets = consumer.end_offsets([tp])
        
        start = beginning_offsets[tp]
        end = end_offsets[tp]
        count = end - start
        total_count += count
        print(f"Partition {partition}: {count} messages (Offsets {start} to {end})")
    
    return total_count

if __name__ == "__main__":
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    topic = "fire_events"
    print(f"Counting messages in topic '{topic}' on {bootstrap}...")
    try:
        total = count_messages(topic, [bootstrap])
        print(f"Total messages in '{topic}': {total}")
        
        # Also check at_risk_assets if it exists
        print("\nChecking 'at_risk_assets' topic...")
        total_alerts = count_messages("at_risk_assets", [bootstrap])
        print(f"Total messages in 'at_risk_assets': {total_alerts}")
    except Exception as e:
        print(f"Error: {e}")
