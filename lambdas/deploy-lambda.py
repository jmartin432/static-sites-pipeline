import boto3
import zipfile
import mimetypes
import os
import io
import logging
from string import Template
import json
import time

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


def publish_cache_invalidation_sns(topic, project, message, event_id):
    sns_message = {
        'project': project,
        'message': message,
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


def handler(event, context):
    sns = boto3.resource('sns')
    status_topic = sns.Topic(os.environ['StatusTopicArn'])
    invalidate_topic = sns.Topic(os.environ['CacheInvalidationTopicArn'])

    s3 = boto3.resource('s3')
    artifacts_bucket = s3.Bucket(os.environ['ArtifactBucket'])
    deployment_bucket = s3.Bucket(os.environ['DeployBucket'])
    event_id = event['id']
    project = event['detail']['project-name']
    app_name = project.replace('-codebuild', '')

    message = Template('Starting Deploy Lambda for $app. Event ID: $event_id') \
        .safe_substitute(app=app_name, event_id=event_id)
    publish_slack_sns(status_topic, app_name, 'IN_PROGRESS', message, event_id)
    logger.info(Template('Received event from CodeBuild, project: $project, id: $event_id')
                .safe_substitute(project=project, event_id=event_id))
    artifact_path = project.replace('-codebuild', '-artifacts')
    artifact_name = project.replace('-codebuild', '.zip')
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
        publish_slack_sns(status_topic, app_name, 'FAILED', message, event_id)
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
                deployment_bucket.upload_fileobj(this_object, upload_key,
                                                 ExtraArgs={'ContentType': mimetypes.guess_type(object_name)[0]})
    except Exception:
        message = Template('There was an error uploading the objects. Event ID: $event_id') \
            .safe_substitute(event_id=event_id)
        logger.exception(message)
        publish_slack_sns(status_topic, app_name, 'FAILED', message, event_id)
        return

    message = Template('Uploading $app complete. Event ID: $event_id') \
        .safe_substitute(app=app_name, event_id=event_id)
    logger.info(message)
    publish_slack_sns(status_topic, app_name, 'SUCCEEDED', message, event_id)
    publish_cache_invalidation_sns(invalidate_topic, app_name, message, event_id)
    return


