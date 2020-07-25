import boto3
import json
import logging
import os

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

webhookBase = "https://hooks.slack.com/services"
webhookPath = os.environ['SlackWebHookPath']
slackMessage = {
    	"text": "Root Activity Detected",
    	"attachments": [
    		{
    			"text": "message",
    			"color": "#000000"
    		}
    	]
    }

apiColor = "#345643"
loginColor = "#abcdef"
unknownColor = "#cc0606"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):

    if event['detail-type'] == "AWS API Call via CloudTrail":
        slackDetails = "{}\n{}\n{}\n{}\n{}\n{}".format(event['detail']['awsRegion'],event['detail']['eventTime'],event['detail']['eventSource'],event['detail']['eventType'],event['detail']['eventName'],event['detail']['eventID'])
        slackMessage['attachments'][0]['text'] = slackDetails
        slackMessage['attachments'][0]['color'] = apiColor
    elif event['detail-type'] == "AWS Console Sign In via CloudTrail":
        slackDetails = "{}\n{}\n{}\n{}\n{}\n{}".format(event['detail']['awsRegion'],event['detail']['eventTime'],event['detail']['eventSource'],event['detail']['eventType'],event['detail']['eventName'],event['detail']['eventID'])
        slackMessage['attachments'][0]['text'] = slackDetails
        slackMessage['attachments'][0]['color'] = loginColor
    else:
        logger.info(event)
        slackMessage['attachments'][0]['text'] = "RootActivityMonitorLambda was triggered but cause could not be determined"
        slackMessage['attachments'][0]['color'] = unknownColor

    req = Request("{}{}".format(webhookBase, webhookPath), json.dumps(slackMessage).encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.info("Message posted to slack channel")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
