import boto3
import zipfile
import mimetypes
import os
import io
import logging
from string import Template
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def publish_sns(topic, project, status, message, event_id):
    sns_message = {
        'project': project,
        'status': status,
        'message': message,
        'event_id': event_id
    }

    response = topic.publish(
        # TargetArn=os.environ['SlackRouterLambdaArn'],
        Message=json.dumps(sns_message),
        Subject='Deploy Status Update',
    )

    logger.info(Template('deploy lambda sns response: $response')
                .safe_substitute(response=response))
    return


def handler(event, context):
    sns = boto3.resource('sns')
    status_topic = sns.Topic(os.environ['StatusTopicArn'])
    s3 = boto3.resource('s3')
    artifacts_bucket = s3.Bucket(os.environ['ArtifactBucket'])
    deployment_bucket = s3.Bucket(os.environ['DeployBucket'])
    event_id = event['id']
    project = event['detail']['project-name']
    logger.info(Template('received event from CodeBuild, project: $project, id: $event_id')
                .safe_substitute(project=project, event_id=event_id))
    app_name = project.replace('-codebuild', '')
    artifact_path = project.replace('-codebuild', '-artifacts')
    artifact_name = project.replace('-codebuild', '.zip')
    artifact_key = artifact_path + '/' + artifact_name
    artifact_zip = io.BytesIO()

    logger.info(Template('downloading $artifact from $bucket')
                .safe_substitute(artifact=artifact_key, bucket=artifacts_bucket))
    try:
        artifacts_bucket.download_fileobj(artifact_key, artifact_zip)
    except:
        message = Template('There was an error downloading $artifact. Event ID: $event_id') \
            .safe_substitute(artifact=artifact_key, event_id=event_id)
        logger.error(message)
        publish_sns(status_topic, app_name, 'FAILED', message, event_id)
        return

    logger.info(Template('uploading $app to $bucket')
                .safe_substitute(app=app_name, bucket=deployment_bucket))
    try:
        with zipfile.ZipFile(artifact_zip) as this_zip:
            for object_name in this_zip.namelist():
                upload_key = app_name + '/' + object_name.replace('src/', '', 1)
                this_object = this_zip.open(object_name)
                deployment_bucket.upload_fileobj(this_object, upload_key,
                                                 ExtraArgs={'ContentType': mimetypes.guess_type(object_name)[0]})
    except:
        message = Template('There was an error uploading the objects. Event ID: $event_id') \
            .safe_substitute(event_id=event_id)
        logger.error(message)
        publish_sns(status_topic, app_name, 'FAILED', message, event_id)
        return

    message = Template('uploading $app complete. Event ID: $event_id') \
        .safe_substitute(app=app_name, event_id=event_id)
    logger.info(message)
    publish_sns(status_topic, app_name, 'SUCCEEDED', message, event_id)
    return


