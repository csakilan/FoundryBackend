import boto3 
from datetime import datetime,timezone


def ec2_price(build_id): 
    

    ec2 = boto3.client("ec2")

    ec2_info = ec2.describe_instances(Filters=[
        {'Name': 'tag:BuildId',
         'Values': [f"{build_id}"]}
    ])



    instances = []


    for reservation in ec2_info["Reservations"]:
        for inst in reservation["Instances"]:
            instances.append(inst)


    grouped = {}

    for inst in instances:
        itype = inst["InstanceType"]
        grouped.setdefault(itype, []).append(inst)

    
    # print(grouped)

    cpu_price = {
        't3.micro': 0.0104,
        't3.small': 0.0208,
        'c7i-flex.large': 0.0832,
        'm7i-flex.large': 0.0768,

    }

    final_price = {
        't3.micro': 0,
        't3.small': 0,
        'c7i-flex.large': 0,
        'm7i-flex.large': 0,
    }

    for cpu in grouped:
        launch = grouped[cpu][0]["LaunchTime"]
        print(launch)

        now = datetime.now(timezone.utc)

        hours = (now - launch).total_seconds() / 3600    

        price_per_hour = cpu_price.get(cpu, 0)
        
        total_price = price_per_hour * hours * len(grouped[cpu])

        final_price[cpu] = {total_price , f"hours: {hours}", "per hour: ",price_per_hour}

    print("cpu",final_price)

    return final_price


# ec2_price(build_id="82622067")