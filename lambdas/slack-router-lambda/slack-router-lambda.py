import boto3
import json
import logging
import os
from string import Template
import time
import requests

webhook_base = "https://hooks.slack.com/services"
webhook_path = os.environ['SlackWebHookPath']
slack_message = {
    "text": "CodeBuild Status Change",
    "attachments": [
        {
            "text": "",
            "color": ""
        }
    ]
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)

emoji_dict = {
    'IN_PROGRESS': '🤔',
    'SUCCEEDED': '👍',
    'FAILED': '😢'
}
color_dict = {
    'IN_PROGRESS': '#e0de43',
    'SUCCEEDED': '#30b342',
    'FAILED': '#cc2d1f'
}


def send_slack_message(this_id, header, details, color):
    slack_message['text'] = header
    slack_message['attachments'][0]['text'] = details
    slack_message['attachments'][0]['color'] = color

    url = Template('$base$path').safe_substitute(base=webhook_base, path=webhook_path)
    json_message = json.dumps(slack_message).encode('utf-8')

    try:
        response = requests.put(
            url,
            data=json_message
        )
        print('Sent Slack Message successfully: {response}'.format(response=response))
    except Exception as e:
        print('Sending to Slack failed: {e}'.format(e=e))
        raise

    return


def handler(event, context):
    received_template = Template('Received an event of type $type event id $event_id')
    logger.info(event)
    event_type = 'cloudwatch-event' if 'id' in event else 'sns-message'
    if event_type == 'cloudwatch-event':
        event_id = event['id']
        project = event['detail']['project-name']
        status = event['detail']['build-status']
        timestamp = time.strftime("%a, %d %b %Y %H:%M:%SZ", time.strptime(event['time'], "%Y-%m-%dT%H:%M:%SZ"))
        details = Template('Project: $project\nStatus: $status $emoji\nEvent ID: $event_id\nTimestamp: $time') \
            .safe_substitute(project=project, status=status, emoji=emoji_dict[status], event_id=event_id, time=timestamp)
        header = 'CodeBuild Status Change'
        logger.info(received_template.safe_substitute(type=event_type, event_id=event_id))
        send_slack_message(event_id, header, details, color_dict[status])
    else:
        message_id = event['Records'][0]['Sns']['MessageId']
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        header = event['Records'][0]['Sns']['Subject']
        project = sns_message['project']
        status = sns_message['status']
        message = sns_message['message']
        timestamp = sns_message['timestamp']
        details = Template('Project: $project\nStatus: $status $emoji\nMessage: $message\nSNS Message ID: $message_id\n'
                           'Timestamp: $time') \
            .safe_substitute(project=project, status=status, emoji=emoji_dict[status], message=message,
                             message_id=message_id, time=timestamp)
        logger.info(received_template.safe_substitute(type=event_type, event_id=message_id))
        send_slack_message(message_id, header, details, color_dict[status])

    return
