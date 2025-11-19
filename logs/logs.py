import boto3
from datetime import datetime, timedelta

def ec2_log(build_id):
    resources = boto3.client("resourcegroupstaggingapi")


    response = resources.get_resources(
        TagFilters=[
            {
                "Key": "BuildId",
                "Values": [str(build_id)],
            }
        ],
        ResourceTypeFilters=["ec2:instance"],
    )

    ec2_instances = []
    for res in response.get("ResourceTagMappingList", []):
        arn = res["ResourceARN"] 
        if ":instance/" in arn:
            instance_id = arn.split("/")[-1]
            ec2_instances.append(instance_id)

    if not ec2_instances:
        print(f"No EC2 instances found with BuildId={build_id}")
        return {}

    cloud = boto3.client("cloudwatch", region_name="us-east-1")


    end = datetime.utcnow()
    start = end - timedelta(hours=1)


    metric_queries = []
    id_to_instance = {}

    for idx, instance in enumerate(ec2_instances):
        qid = f"cpu{idx}"         
        id_to_instance[qid] = instance

        metric_queries.append(
            {
                "Id": qid,
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [
                            {
                                "Name": "InstanceId",
                                "Value": instance,
                            },
                        ],
                    },
                    "Period": 300,   
                    "Stat": "Average",
                },
                "ReturnData": True,
            }
        )


    result = cloud.get_metric_data(
        MetricDataQueries=metric_queries,
        StartTime=start,
        EndTime=end,
        ScanBy="TimestampDescending",  
    )

    cpu_utilization = {}

    for data in result.get("MetricDataResults", []):
        qid = data["Id"]
        instance = id_to_instance[qid]

        timestamps = data.get("Timestamps", [])
        values = data.get("Values", [])


        points = [
            {"time": t.isoformat(), "value": v}
            for t, v in zip(timestamps, values)
        ]

        cpu_utilization[instance] = points

    print("cpu_utilization", cpu_utilization)
    return cpu_utilization



# ec2_log()