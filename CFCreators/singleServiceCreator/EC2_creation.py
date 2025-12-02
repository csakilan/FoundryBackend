# EC2_creation.py
from typing import Dict, Any, Optional
from troposphere import Template, Ref, Base64, Sub, Tags, Output, GetAtt
import troposphere.ec2 as ec2
import os
from dotenv import load_dotenv

load_dotenv()

# Mapping of friendly image names to AWS SSM Parameter Store paths
# These SSM parameters are maintained by AWS and automatically point to the latest AMI
IMAGE_NAME_TO_SSM = {
    "Amazon Linux": "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64",
    "Ubuntu": "/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id",
    "Windows": "/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base",
    # Note: macOS is not included as it requires dedicated hosts and cannot use standard SSM parameters
    # If macOS support is needed, user must provide a specific AMI ID from their dedicated host setup
}


def sanitize_ec2_name(name: str) -> str:
    """
    Sanitize a string for EC2 instance naming (used in Name tag).
    
    EC2 Name tags are more flexible than resource identifiers, but we sanitize
    to keep consistency with other AWS resources.
    
    Args:
        name: Raw name string
        
    Returns:
        Sanitized name (alphanumeric, hyphens, underscores)
    """
    # Replace invalid characters (colons, spaces, etc.) with hyphens
    valid_chars = []
    for char in name:
        if char.isalnum() or char in ['_', '-']:
            valid_chars.append(char)
        else:
            valid_chars.append('-')
    
    # Join and remove consecutive hyphens
    name = ''.join(valid_chars)
    while '--' in name:
        name = name.replace('--', '-')
    
    # Remove leading/trailing hyphens
    name = name.strip('-')
    
    # Ensure it's not empty
    if not name:
        name = 'instance'
    
    return name

def resolve_image_id(image_input: str) -> str:
    """
    Resolve image ID from either:
    1. A friendly name (Amazon Linux, Ubuntu, Windows, macOS) -> returns SSM parameter
    2. A direct AMI ID (ami-xxxxx) -> returns as-is
    
    Args:
        image_input: Either a friendly name or AMI ID
        
    Returns:
        Either an SSM parameter path or AMI ID string
    """
    # If it's already an AMI ID, return it
    if image_input.startswith("ami-"):
        return image_input
    
    # Otherwise, look up the SSM parameter for the friendly name
    ssm_param = IMAGE_NAME_TO_SSM.get(image_input)
    
    if ssm_param:
        # Return a CloudFormation resolve expression for SSM parameter
        return f"{{{{resolve:ssm:{ssm_param}}}}}"
    
    # If no mapping found, return as-is (will likely fail validation)
    return image_input


def add_ec2_instance(
    t: Template,
    node: Dict[str, Any],
    subnet_param,
    sg_param,
    *,
    logical_id: str = None,
    instance_profile: Optional[Any] = None,
    environment_variables: Optional[Dict[str, str]] = None,
    build_id: str = "default",
    key_name: Optional[str] = None,
) -> ec2.Instance:
    

    """
    Add an AWS::EC2::Instance to the given Template.
    Expects node['data'] with: name, imageId, instanceType, optional keyName, userData, storage{...}.
    The imageId can be either:
    - A friendly name: "Amazon Linux", "Ubuntu", "Windows", "macOS"
    - A direct AMI ID: "ami-xxxxx"
    
    Networking comes from Parameters: SubnetId, SecurityGroupId.
    
    Args:
        t: Troposphere Template object
        node: Node dictionary from ReactFlow canvas
        subnet_param: Parameter reference for subnet
        sg_param: Parameter reference for security group
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        instance_profile: Optional IAM instance profile for permissions
        environment_variables: Optional dict of env vars to inject into UserData
        build_id: Build ID to prefix the instance name and logical ID
        key_name: SSH key pair name for EC2 access (auto-generated or from user)
    
    Returns:
        The created EC2 Instance resource
    """
    data = node["data"]

    repositories = data.get("repos")

    github_url = f"https://github.com/csakilan/SandwichClassifier.git"

    print("repositories to send to user data",repositories)

    print("data to know heheheha",data)
    
    # Override build_id with "default" if USE_DEFAULT_BUILD_ID is true (for testing)
    if os.getenv('USE_DEFAULT_BUILD_ID', 'false').lower() == 'true':
        build_id = 'default'
    
    # Generate unique instance identifier: <build_id>-<user_name>
    user_name = sanitize_ec2_name(data["name"])  # Sanitize user name
    sanitized_build_id = sanitize_ec2_name(build_id)  # Sanitize build_id
    
    instance_name = f"{sanitized_build_id}-{user_name}"
    
    # Generate logical ID if not provided
    if logical_id is None:
        # CloudFormation logical IDs can't have hyphens, use CamelCase
        logical_id = f"EC2{build_id.replace('-', '').replace(':', '').title()}{user_name.replace('-', '').replace(':', '')}"
    
    print(f"  → Generated unique EC2 instance name: {instance_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    storage = data.get("storage") or {}
    user_data = data.get("userData", "")

    # Resolve the image ID (convert friendly name to SSM parameter or use AMI ID directly)
    resolved_image_id = resolve_image_id(data["imageId"])
    
    # Build environment variable exports for UserData
    env_var_script = ""
    if environment_variables:
        env_var_lines = []
        for key, value in environment_variables.items():
            # Add to current session and to /etc/environment for persistence
            env_var_lines.append(f'export {key}="{value}"')
            env_var_lines.append(f'echo "export {key}=\\"{value}\\"" >> /etc/environment')
        env_var_script = "\n".join(env_var_lines)
    
    # Combine environment variables with user's custom UserData
    if env_var_script:
        combined_user_data = f"""#!/bin/bash
# Auto-generated environment variables for service connections
{env_var_script}

# User-provided UserData
{user_data}
"""
    else:
        combined_user_data = user_data if user_data else ""
    
    # Root volume (locked defaults with per-node overrides)
    block_devices = [
        ec2.BlockDeviceMapping(
            DeviceName="/dev/xvda",  # common Linux HVM root; adjust per-AMI family if needed
            Ebs=ec2.EBSBlockDevice(
                VolumeSize=storage.get("rootVolumeSizeGiB", 20),
                VolumeType=storage.get("rootVolumeType", "gp3"),
                DeleteOnTermination=storage.get("deleteOnTermination", True),
            ),
        )
    ]

    # Build properties (omit optionals when None so Troposphere doesn't render them)
    props: Dict[str, Any] = dict(
        ImageId=resolved_image_id,            # resolved AMI ID or SSM parameter
        InstanceType=data["instanceType"],
        SubnetId=Ref(subnet_param),
        SecurityGroupIds=[Ref(sg_param)],
        BlockDeviceMappings=block_devices,
        Tags=Tags(
            Name=instance_name,               # Use the generated unique name
            OriginalName=data["name"],        # Keep original user-provided name as a separate tag
            ManagedBy="CloudFormation",
            BuildId=build_id,
        ),
    )
    
    # Note: MetadataOptions is not supported in Troposphere 4.9.4
    # Uncomment below when upgrading to Troposphere 4.0+ (requires newer version):
    # props["MetadataOptions"] = ec2.MetadataOptions(HttpTokens="required", HttpEndpoint="enabled")

    # Add IAM instance profile if provided (for S3, DynamoDB access)
    if instance_profile:
        props['IamInstanceProfile'] = Ref(instance_profile)
    else:
        # Fallback to ec2CodeDeploy if no custom instance profile
        props['IamInstanceProfile'] = "ec2CodeDeploy"
    
    # Add SSH key pair if provided (either from parameter or auto-generated)
    if key_name:
        props["KeyName"] = key_name
    elif data.get("keyName"):
        props["KeyName"] = data["keyName"]
    
#     props["UserData"] = Base64(f"""#!/bin/bash
# sudo apt-get update -y
# sudo apt-get install -y ruby wget
# cd /home/ubuntu
# wget https://aws-codedeploy-us-east-1.s3.us-east-1.amazonaws.com/latest/install
# chmod +x ./install
# sudo ./install auto
# sudo systemctl enable --now codedeploy-agent
# sudo systemctl status codedeploy-agent
# sudo tail -n 200 /var/log/aws/codedeploy-agent/codedeploy-agent.log
                                   
# sudo yum update -y
# git clone {repositories} /var/www/app
# cd /var/www/app
# npm install
# npm start

                            
                                   
                                
# """)
    props["UserData"] = Base64(f"""#!/bin/bash
set -xe
sudo apt-get update -y
sudo apt-get install -y ruby wget git python3 python3-pip
cd /home/ubuntu
wget https://aws-codedeploy-us-east-1.s3.us-east-1.amazonaws.com/latest/install
chmod +x ./install
sudo ./install auto
sudo systemctl enable --now codedeploy-agent
                               
sudo apt update
sudo apt install -y libgl1
sudo mkdir -p /var/www/app
sudo chown -R ubuntu:ubuntu /var/www
git clone {github_url} /var/www/app
cd /var/www/app
pip3 install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
""")


    

    instance = ec2.Instance(logical_id, **props)
    t.add_resource(instance)

    # Helpful, namespaced outputs (avoid collisions when multiple EC2s exist)
    t.add_output([
        Output(f"{logical_id}Id", Value=Ref(instance)),
        Output(f"{logical_id}PrivateIp", Value=GetAtt(instance, "PrivateIp")),
        Output(f"{logical_id}PublicIp", Value=GetAtt(instance, "PublicIp")),  # blank if no public IP
        Output(f"{logical_id}InstanceName", Value=instance_name),           # Generated unique name
        Output(f"{logical_id}OriginalName", Value=data["name"]),            # User's original name
    ])

    return instance
