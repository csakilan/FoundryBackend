import boto3 
import json
from datetime import datetime, timezone

def costs(): 

    ec2_price = 0
    dynamo_price = 0
    rds_price = 0
    s3_price = 0

    try: 


        pricing = boto3.client("pricing", region_name="us-east-1")


        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[{
    'Type': 'TERM_MATCH',
    'Field': 'instanceType',
    'Value': 't3.micro'
},
{
    'Type': 'TERM_MATCH',
    'Field': 'operatingSystem',
    'Value': 'Linux'
},
{
    'Type': 'TERM_MATCH',
    'Field': 'preInstalledSw',
    'Value': 'NA'
},
{
    'Type': 'TERM_MATCH',
    'Field': 'tenancy',
    'Value': 'Shared'
},
{
    'Type': 'TERM_MATCH',
    'Field': 'capacitystatus',
    'Value': 'Used'
},
{
    'Type': 'TERM_MATCH',
    'Field': 'location',
    'Value': 'US East (N. Virginia)'
}
],
        MaxResults=1)





        item = json.loads(response["PriceList"][0])
        terms = item["terms"]["OnDemand"]
        first_term = next(iter(terms.values()))
        price_dims = first_term["priceDimensions"]
        first_dim = next(iter(price_dims.values()))
        price_per_hour = float(first_dim["pricePerUnit"]["USD"])
        
        print("USD/hr:", price_per_hour)




        ec2 = boto3.client("ec2", region_name="us-east-1")

        instances = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": ["Fast API Server"]}])

        runtime = instances['Reservations'][0]['Instances'][0]['LaunchTime']


        now = datetime.now(timezone.utc)

        delta = now - runtime

        hours_running = delta.total_seconds() / 3600
        total_cost = hours_running * price_per_hour
        print(f"Instance has been running for {hours_running:.2f} hours.")


        print(f"Total cost for running the instance: ${total_cost:.4f}")


    


        # print("instance info",instances)


       


        
        

       
    except Exception as e: 
        print(f"Failed to get costs: {e}")








costs()