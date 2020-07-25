import boto3
import zipfile
import mimetypes
import os
import io
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    s3 = boto3.resource('s3')
    artifacts_bucket = s3.Bucket(os.environ['ArtifactBucket'])
    deployment_bucket = s3.Bucket(os.environ['DeployBucket'])
    event_id = event['id']
    project = event['detail']['project-name']
    logger.info('received event from CodeBuild, project: %s, id: %s' % (project, event_id))
    app_name = project.replace('-codebuild', '')
    artifact_path = project.replace('-codebuild', '-artifacts')
    artifact_name = project.replace('-codebuild', '.zip')
    artifact_key = artifact_path + '/' + artifact_name
    artifact_zip = io.BytesIO()
    logger.info('downloading %s from %s' % (artifact_key, artifacts_bucket))
    artifacts_bucket.download_fileobj(artifact_key, artifact_zip)

    logger.info('uploading %s to %s' % (app_name, deployment_bucket))
    with zipfile.ZipFile(artifact_zip) as this_zip:
        for object_name in this_zip.namelist():
            upload_key = app_name + '/' + object_name
            this_object = this_zip.open(object_name)
            deployment_bucket.upload_fileobj(this_object, upload_key,
                ExtraArgs={'ContentType': mimetypes.guess_type(object_name)[0]})

    logger.info('uploading %s complete' % app_name)


