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


def handler(event, context):
    logger.info(event)
    sns = boto3.resource('sns')
    status_topic = sns.Topic(os.environ['StatusTopicArn'])
    distribution_id = os.environ['StaticSitesCdnId']
    sns_message = json.loads(event['Records'][0]['Sns']['Message'])
    project = sns_message['project']

    path = ['/' + project + '/*']
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
        invalidation_request_id = invalidation['ResponseMetadata']['RequestId']
        invalidation_id = invalidation['Invalidation']['Id']
        if invalidation_http_code == 201:
            message = Template('Cache Invalidation sent to CloudFront. Invalidation ID: $id Request ID: $request_id') \
                .safe_substitute(id=invalidation_id, request_id=invalidation_request_id)
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
    publish_slack_sns(status_topic, project, status, message)

    return
