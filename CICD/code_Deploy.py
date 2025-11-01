import boto3

def codeDeploy(owner,repo,bucket_name,object_key):
    code_deploy = boto3.client("codedeploy", region_name="us-east-1")

    try:

    

#also we have to add logic to clear the buckets after deployment or something bc if we keep adding zips to the bucket it will get messy

#also we need to add overriding to the deployment group names as well so if you deploy the same project it shouldnt give an error
#"code deployment name exist"

#also this only works for next.js projects and there must be a frontend folder too for it too work
#use the testing folders if yall want to experiment with it 
#we can also create a new application so it doesnt have my name fixed "efrain-grubs-my-next-app"
#for the cf docs it has to have an the iam policy "arn:aws:iam::575380174326:role/serviceRoleCodeDeploy" its so codedeploy can talk to ec2 instances

#gotta add logic if something went wrong with upload to send to frontend

#also gotta send the frontend a url too if sucessfull 




#6 + 7 = six sevennnnn

    

        try: 
            create_deployment_group = code_deploy.create_deployment_group(
                applicationName=f"{owner}-{repo}",        
                deploymentGroupName=f"{repo}",            #makes deployment group on codedeploy   
                serviceRoleArn="arn:aws:iam::575380174326:role/serviceRoleCodeDeploy", #same thing here will be parameter once cf done
                ec2TagFilters=[{'Key': 'Name','Value': 'Fast API Server','Type': 'KEY_AND_VALUE'} ] #filters for ec2
            )

        except code_deploy.exceptions.DeploymentGroupAlreadyExistsException:
            update_deployment_group = code_deploy.update_deployment_group( 
                applicationName=f"{owner}-{repo}",
                currentDeploymentGroupName=f"{repo}",
                ec2TagFilters=[{'Key': 'Name','Value': 'Fast API Server','Type': 'KEY_AND_VALUE'} ]
               
            )
        

        response = code_deploy.create_deployment(
            applicationName=f"{owner}-{repo}",
            deploymentGroupName=repo,
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

        print("Deployment started:", response['deploymentId'])

    except Exception as e:
        print(f"Failed to trigger CodeDeploy: {e}")


