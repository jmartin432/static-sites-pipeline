# Static Sites Pipeline
A custom code pipeline for my collection of static websites. 
The code is built by AWS CodeBuild on every push to a GitHub 
master branch. When code is successfully built, an AWS Lambda 
function unpacks the artifacts and uploads them to AWS S3 
buckets where they can be delivered by a custom [Content Delivery
Network](https://github.com/jmartin432/static-sites-cdn). An 
additional AWS Lambda function is trigger by pipeline
steps and reports progress to a dedicated Slack channel.

# Technologies Used:
* AWS CloudFormation
* AWS CodeBuild
* AWS S3
* AWS Lambda
* AWS SNS (Simple Notification Service)
* AWS IAM (Identity Access Management)
* AWS EventBridge
* AWS CloudWatch
* Python 3
* YAML
* Slack Webhooks
* GitHub to AWS Integration
