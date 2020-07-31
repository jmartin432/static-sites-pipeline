import boto3
import time
import logging
import json
from string import Template
import os
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def publish_slack_sns(topic, project, status, message):
    sns_message = {
        'project': project,
        'status': status,
        'message': message,
        'timestamp': time.strftime("%a, %d %b %Y %H:%M:%SZ", time.localtime())
    }

    response = topic.publish(
        Message=json.dumps(sns_message),
        Subject='Cache Invalidation Status Update',
    )

    logger.info(Template('Status sns response: $response')
                .safe_substitute(response=response))
    return


# noinspection PyUnresolvedReferences
def handler(event, context):
    logger.info(event)
    sns = boto3.resource('sns')
    status_topic = sns.Topic(os.environ['StatusTopicArn'])
    sns_message = json.loads(event['Records'][0]['Sns']['Message'])
    app_name = sns_message['app-name']
    environment = sns_message['environment']
    if environment == 'prod':
        distribution_id = os.environ['CdnProdId']
    else:
        distribution_id = os.environ['CdnDevId']

    path = ['/' + app_name + '/*']
    client = boto3.client('cloudfront')
    status = ''
    try:
        invalidation = client.create_invalidation(DistributionId=distribution_id,
                                                  InvalidationBatch={
                                                      'Paths': {
                                                          'Quantity': 1,
                                                          'Items': path
                                                      },
                                                      'CallerReference': str(time.time())
                                                  })
        logger.info(invalidation)
        invalidation_http_code = invalidation['ResponseMetadata']['HTTPStatusCode']
        invalidation_id = invalidation['Invalidation']['Id']
        if invalidation_http_code == 201:
            message = Template('Cache Invalidation sent to CloudFront. Environment: $environment, Distribution ID: '
                               '$distribution_id, Invalidation ID: $invalidation_id Path: $path') \
                .safe_substitute(environment=environment.upper(), distribution_id=distribution_id,
                                 invalidation_id=invalidation_id, path=path)
            status = 'IN_PROGRESS'
        else:
            message = Template('Cache Invalidation was sent. Status is unknown') \
                .safe_substitute()
            status = 'FAILED'
    except Exception:
        logger.exception('Error sending cache invalidation request.')
        message = Template('Error sending cache invalidation request. Check the logs') \
            .safe_substitute()
        status = 'FAILED'

    publish_slack_sns(status_topic, app_name.upper(), status, message)

    return
