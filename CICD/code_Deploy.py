import boto3

async def codeDeploy(owner, repo, bucket_name, object_key,tag):
   

    print("tag",tag)

    code_deploy = boto3.client("codedeploy", region_name="us-east-1")
    application_name = f"{owner}-{repo}"
    deployment_group_name = repo
    service_role_arn = "arn:aws:iam::575380174326:role/serviceRoleCodeDeploy"  # Update if needed

    try:
        # Ensure application exists
        try:
            code_deploy.get_application(applicationName=application_name)
            print(f"Application '{application_name}' exists.")
        except code_deploy.exceptions.ApplicationDoesNotExistException:
            code_deploy.create_application(
                applicationName=application_name,
                computePlatform="Server"
            )
            print(f"Created CodeDeploy application '{application_name}'.")

        # Create or update deployment group
        try:
            code_deploy.create_deployment_group(
                applicationName=application_name,
                deploymentGroupName=deployment_group_name,
                serviceRoleArn=service_role_arn,
                ec2TagFilters=[{'Key': 'BuildId', 'Value': tag, 'Type': 'KEY_AND_VALUE'}]
            )
            print(f"Created deployment group '{deployment_group_name}'.")
        except code_deploy.exceptions.DeploymentGroupAlreadyExistsException:
            code_deploy.update_deployment_group(
                applicationName=application_name,
                currentDeploymentGroupName=deployment_group_name,
                ec2TagFilters=[{'Key': 'BuildId', 'Value': tag, 'Type': 'KEY_AND_VALUE'}]
            )
            print(f"Updated deployment group '{deployment_group_name}'.")

        # Start deployment
        response = code_deploy.create_deployment(
            applicationName=application_name,
            deploymentGroupName=deployment_group_name,
            revision={
                'revisionType': 'S3',
                's3Location': {
                    'bucket': bucket_name,
                    'key': object_key,
                    'bundleType': 'zip'
                }
            },
            deploymentConfigName='CodeDeployDefault.AllAtOnce',
            description='Deploying latest build to EC2',
            fileExistsBehavior='OVERWRITE'
        )

        print("Deployment started:", type(response['deploymentId']))

        deployment_identity= response['deploymentId']

        print("deployment id",deployment_identity)

        
         


        while True:

            deploy_response = code_deploy.get_deployment(deploymentId=deployment_identity) 

            deployment_info = deploy_response['deploymentInfo']

            


            status =  deployment_info['status']
            
            print("status",status)

            

            if status in ["Succeeded", "Failed", "Stopped", "TimedOut"]:
                break

            await asyncio.sleep(2)

            


    except Exception as e:
        print(f"Failed to trigger CodeDeploy: {e}")
