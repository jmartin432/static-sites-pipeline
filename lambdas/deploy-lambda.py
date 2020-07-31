import boto3
import zipfile
import mimetypes
import os
import io
import logging
from string import Template
import json
import time
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def publish_slack_sns(topic, project, status, message, event_id):
    sns_message = {
        'project': project,
        'status': status,
        'message': message,
        'event_id': event_id,
        'timestamp': time.strftime("%a, %d %b %Y %H:%M:%SZ", time.localtime())
    }

    response = topic.publish(
        Message=json.dumps(sns_message),
        Subject='Deploy Status Update',
    )

    logger.info(Template('status sns response: $response')
                .safe_substitute(response=response))
    return


def publish_cache_invalidation_sns(topic, app_name, environment, event_id):
    sns_message = {
        'app-name': app_name,
        'environment': environment,
        'event_id': event_id,
        'timestamp': time.strftime("%a, %d %b %Y %H:%M:%SZ", time.localtime())
    }

    response = topic.publish(
        Message=json.dumps(sns_message),
        Subject='Cache Invalidation Request from Deploy Lambda',
    )

    logger.info(Template('cache invalidation sns response: $response')
                .safe_substitute(response=response))
    return


# noinspection PyUnresolvedReferences
def handler(event, context):
    logger.info(Template('Received event: $event').safe_substitute(event=event))

    sns = boto3.resource('sns')
    status_topic = sns.Topic(os.environ['StatusTopicArn'])
    invalidate_topic = sns.Topic(os.environ['CacheInvalidationTopicArn'])

    if 'id' in event:
        event_id = event['id']
        project = event['detail']['project-name']
        app_name = project.replace('-codebuild', '')
        artifact_path = project.replace('-codebuild', '-artifacts')
        artifact_name = project.replace('-codebuild', '.zip')
        environment = 'dev'
        message = Template('Deploy Lambda received CodeBuild trigger for $app to DEV. Event ID: $event_id') \
            .safe_substitute(app=app_name.upper(), event_id=event_id.upper())
    else:
        event_id = str(uuid.uuid4())
        app_name = event['app-name']
        artifact_path = app_name + '-artifacts'
        artifact_name = app_name + '.zip'
        environment = event['environment']
        message = Template('Deploy Lambda received manual trigger for $app to $env Event ID: $event_id') \
            .safe_substitute(app=app_name.upper(), env=environment.upper(), event_id=event_id)

    publish_slack_sns(status_topic, app_name.upper(), 'IN_PROGRESS', message, event_id)

    s3 = boto3.resource('s3')
    artifacts_bucket = s3.Bucket(os.environ['ArtifactBucket'])
    if environment == 'dev':
        deployment_bucket = s3.Bucket(os.environ['DeployBucketDev'])
    else:
        deployment_bucket = s3.Bucket(os.environ['DeployBucketProd'])

    artifact_key = artifact_path + '/' + artifact_name
    artifact_zip = io.BytesIO()

    logger.info(Template('Downloading $artifact from $bucket')
                .safe_substitute(artifact=artifact_key, bucket=artifacts_bucket))
    try:
        artifacts_bucket.download_fileobj(artifact_key, artifact_zip)
    except Exception:
        message = Template('There was an error downloading $artifact. Event ID: $event_id') \
            .safe_substitute(artifact=artifact_key, event_id=event_id)
        logger.exception(message)
        publish_slack_sns(status_topic, app_name.upper(), 'FAILED', message, event_id)
        return

    logger.info(Template('Uploading $app to $bucket')
                .safe_substitute(app=app_name, bucket=deployment_bucket))
    try:
        with zipfile.ZipFile(artifact_zip) as this_zip:
            for object_name in this_zip.namelist():
                if 'src/' in object_name:
                    upload_key = app_name + '/' + object_name.replace('src/', '', 1)
                elif 'dist/' in object_name:
                    upload_key = app_name + '/' + object_name.replace('dist/', '', 1)
                this_object = this_zip.open(object_name)
                if mimetypes.guess_type(object_name)[0] is not None:
                    mime_type = mimetypes.guess_type(object_name)[0]
                else:
                    mime_type = 'application/octet-stream'
                deployment_bucket.upload_fileobj(this_object, upload_key,
                                                 ExtraArgs={'ContentType': mime_type})
    except Exception:
        message = Template('There was an error uploading the objects. Event ID: $event_id') \
            .safe_substitute(event_id=event_id)
        logger.exception(message)
        publish_slack_sns(status_topic, app_name.upper(), 'FAILED', message, event_id)
        return

    slack_message = Template('Uploading $app complete. Event ID: $event_id') \
        .safe_substitute(app=app_name.upper(), event_id=event_id)
    logger.info(slack_message)
    publish_slack_sns(status_topic, app_name.upper(), 'SUCCEEDED', message, event_id)
    publish_cache_invalidation_sns(invalidate_topic, app_name, environment, event_id)
    return


