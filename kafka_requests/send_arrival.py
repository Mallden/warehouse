import json

from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'], value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

message = {
    'id': 'b3b53031-e83a-4654-87f5-b6b6fb09fd99',
    'source': 'WH-3423',
    'specversion': '1.0',
    'type': 'ru.retail.warehouses.movement',
    'datacontenttype': 'application/json',
    'dataschema': 'ru.retail.warehouses.movement.v1.0',
    'time': 1737439421623,
    'subject': 'WH-3423:ARRIVAL',
    'destination': 'ru.retail.warehouses',
    'data': {
        'movement_id': 'c6290746-790e-43fa-8270-014dc90e02e0',
        'warehouse_id': 'c1d70455-7e14-11e9-812a-70106f431230',
        'timestamp': '2025-02-18T14:34:56Z',
        'event': 'arrival',
        'product_id': '4705204f-498f-4f96-b4ba-df17fb56bf55',
        'quantity': 100,
    },
}

producer.send('warehouse_movements', message)
producer.flush()
print('Сообщение успешно отправлено!')
