import boto3
from datetime import datetime, timezone

def ec2_price(build_id):
    ec2 = boto3.client("ec2")

    ec2_info = ec2.describe_instances(
        Filters=[
            {"Name": "tag:BuildId", "Values": [str(build_id)]}
        ]
    )

    cpu_price = {
        "t3.micro": 0.0104,
        "t3.small": 0.0208,
        "c7i-flex.large": 0.0832,
        "m7i-flex.large": 0.0768,
    }

    now = datetime.now(timezone.utc)

    result = []  

    for reservation in ec2_info["Reservations"]:
        for inst in reservation["Instances"]:
            itype = inst["InstanceType"]
            instance_id = inst["InstanceId"]
            launch = inst["LaunchTime"]

            hours = (now - launch).total_seconds() / 3600.0

            price_per_hour = cpu_price.get(itype, 0.0)
            cost = hours * price_per_hour

            result.append({
                "instance_id": instance_id,
                "instance_type": itype,
                "hours_running": hours,
                "cost": cost,
            })

    return result




