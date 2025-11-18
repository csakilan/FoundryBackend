import boto3
import asyncio
from datetime import datetime,timedelta

def get_price(build_id):


  

    resources = boto3.client("resourcegroupstaggingapi")

   
    response = resources.get_resources(TagFilters=[
            {
                'Key': 'aws:cloudformation:stack-name',
                'Values': [f"foundry-stack-{build_id}"]
            }
        ])

    # print("response",response)
        
    s3 = []
    for res in response['ResourceTagMappingList']:
        if 's3' in res['ResourceARN']:
            s3.append(res['ResourceARN'])
    


    total_bytes = []

    for bucket in s3: 
        bucket_name = bucket.split(":::")[1] 

        cloud = boto3.client('cloudwatch',region_name='us-east-1')

        s3_bytes = cloud.get_metric_statistics(
            Namespace='AWS/S3', 
            MetricName='BucketSizeBytes',
            Dimensions=[
                {'Name': 'BucketName', 'Value': 'foundry-codebuild-zip' },#hardcoded for now
                {'Name': 'StorageType', 'Value': 'StandardStorage'}
            ],
            StartTime=datetime.utcnow() - timedelta(days=30),
            EndTime=datetime.utcnow(),
            Period=86400,
            Statistics=['Average']

        ) 

        # print("s3_info",s3_bytes['Datapoints'][0]['Average'])

        total_bytes.append(s3_bytes['Datapoints'][0]['Average']/ (1024*1024*1024))


    total_gb = sum(total_bytes) * 0.023

    print("total_gb",total_gb)


    return total_gb
    

    


get_price(build_id="82622067")

       


    

