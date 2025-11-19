import boto3
from datetime import datetime, timedelta

def get_price(build_id):
    resources = boto3.client("resourcegroupstaggingapi")

    response = resources.get_resources(
        TagFilters=[
            {
                "Key": "aws:cloudformation:stack-name",
                "Values": [f"foundry-stack-{build_id}"],
            }
        ],
        ResourceTypeFilters=["s3"]
    )

    bucket_names = []
    for res in response.get("ResourceTagMappingList", []):
        arn = res["ResourceARN"]
        if ":s3:::" in arn:
            bucket_name = arn.split(":::")[1]
            bucket_names.append(bucket_name)
    # print("bucket_names",bucket_names)
    if not bucket_names:
        return 0.0

    cloud = boto3.client("cloudwatch", region_name="us-east-1")

    end = datetime.utcnow()
    start = end - timedelta(days=30)

    metric_queries = []
    for idx, bucket_name in enumerate(bucket_names):
        metric_queries.append(
            {
                "Id": f"b{idx}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/S3",
                        "MetricName": "BucketSizeBytes",
                        "Dimensions": [
                            {"Name": "BucketName", "Value": bucket_name }, 
                            {"Name": "StorageType", "Value": "StandardStorage"},
                        ],
                    },
                    "Period": 86400,  
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

    total_gb = 0.0

    for metric in result.get("MetricDataResults", []):
        values = metric.get("Values", [])

        print("values",values)
        if not values:
            continue
        latest_bytes = values[0]   
        print("latest_bytes", latest_bytes)       
        total_gb += latest_bytes / (1024 * 1024 * 1024)

    total_cost = total_gb * 0.023  

    # print("total_cost", total_cost)
    return total_cost

    

    


# get_price(build_id="82622067")

       


    

