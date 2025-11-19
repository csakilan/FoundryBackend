import boto3
from datetime import datetime, timedelta


def dynamoCost(build_id):
    tag = boto3.client("resourcegroupstaggingapi")

    dynamo = tag.get_resources(
        TagFilters=[
            {
               "Key": "BuildId",
               "Values": [f"{build_id}"]
            }
        ],
        ResourceTypeFilters=[
            "dynamodb:table"
        ]
    )

    dynamo_arn = [res['ResourceARN'] for res in dynamo['ResourceTagMappingList']]
    print("dynamo", dynamo_arn)

    total_bytes = []
    read_count = []
    write_count = []

    dynamodb = boto3.client("dynamodb")
    cloud = boto3.client("cloudwatch", region_name="us-east-1")

    for table in dynamo_arn:
        table_val = table.split(":table/")[1]

        table_info = dynamodb.describe_table(TableName=table_val)
        bytes_used = table_info['Table']['TableSizeBytes']
        total_bytes.append(bytes_used)

        reads = cloud.get_metric_statistics(
            Namespace='AWS/DynamoDB',
            MetricName='ConsumedReadCapacityUnits',
            Dimensions=[
                {'Name': 'TableName', 'Value': table_val}
            ],
            StartTime=datetime.utcnow() - timedelta(days=30),
            EndTime=datetime.utcnow(),
            Period=86400,
            Statistics=['Sum']
        )

        if reads['Datapoints']:
            read_sum = sum(dp['Sum'] for dp in reads['Datapoints'])
        else:
            read_sum = 0
        
        read_count.append((read_sum / 1_000_000) * 0.25)



        writes = cloud.get_metric_statistics(
            Namespace='AWS/DynamoDB',
            MetricName='ConsumedWriteCapacityUnits',
            Dimensions=[
                {'Name': 'TableName', 'Value': table_val}
            ],
            StartTime=datetime.utcnow() - timedelta(days=30),
            EndTime=datetime.utcnow(),
            Period=86400,
            Statistics=['Sum']
        )

        if writes['Datapoints']:
            write_sum = sum(dp['Sum'] for dp in writes['Datapoints'])
        else:
            write_sum = 0
        write_count.append((write_sum / 1000000)* 1.25)

     

    storage_cost = sum(total_bytes) / (1024 * 1024 * 1024) * 0.25

    print("storage_cost", storage_cost)
    print("read_units", read_count)
    print("write_units", write_count)


    final_cost = storage_cost + sum(read_count) + sum(write_count)
    
    
    
    return {
        "storage_cost": storage_cost,
        "read_units": sum(read_count),
        "write_units": sum(write_count),
        "final_cost": final_cost
    }


    


dynamoCost(build_id="65382566")





