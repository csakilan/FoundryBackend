import boto3

def codeDeploy():
    code_deploy = boto3.client("codedeploy", region_name="us-east-1")

    try:

        # create_app = code_deploy.create_application(  #makes application on code deploy
        #     applicationName="MyApp",
        #     computePlatform="Server"
        #     )
        try: 
            create_deployment_group = code_deploy.create_deployment_group(
                applicationName=f"MyApp",        
                deploymentGroupName=f"MyDeploymentGroup",            #makes deployment group on codedeploy   
                serviceRoleArn="arn:aws:iam::575380174326:role/serviceRoleCodeDeploy", #same thing here will be parameter once cf done
                ec2TagFilters=[{'Key': 'Name','Value': 'third-cicd-test','Type': 'KEY_AND_VALUE'} ] #filters for ec2
            )

        except code_deploy.exceptions.DeploymentGroupAlreadyExistsException:
            
            update_deployment_group = code_deploy.update_deployment_group( 
                applicationName=f"MyApp",
                currentDeploymentGroupName=f"MyDeploymentGroup",
                ec2TagFilters=[{'Key': 'Name','Value': 'third-cicd-test','Type': 'KEY_AND_VALUE'} ] 
               
            )

     
        response = code_deploy.create_deployment(
            applicationName="MyApp",
            deploymentGroupName="MyDeploymentGroup",
            revision={
                'revisionType': 'S3',
                's3Location': {
                    'bucket': 'foundry-artifacts-bucket',
                    'key': 'founryCICD-05ec29e1-5ffa-48f1-a058-7ea2c6aa6983',
                    'bundleType': 'zip'
                }
            },
            deploymentConfigName='CodeDeployDefault.AllAtOnce',
            description='Deploying latest build to EC2',
             fileExistsBehavior='OVERWRITE'
        )

        print("Deployment started:", response['deploymentId'])

    except Exception as e:
        print(f"Failed to trigger CodeDeploy: {e}")


codeDeploy()