import boto3
import os
import json
import sys

def default(obj):
    """Default JSON serializer."""
    import calendar, datetime

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(
            calendar.timegm(obj.timetuple()) * 1000 +
            obj.microsecond / 1000
        )
        return millis
    raise TypeError('Not sure how to serialize %s' % (obj,))

# retrieve
try:
    AWS_ACCESS_KEY_ID = os.environ["FWCHECK_AWS_ACCESS_KEY_ID"]
    AWS_SECRET_KEY    = os.environ["FWCHECK_SECRET_KEY"]
except:
    print "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_KEY environment variables"
    exit(2)


ec2 = boto3.client('ec2', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_KEY)

instances = ec2.describe_instances(MaxResults = 1000)

result = []

for res in instances["Reservations"]:

    for inst in res["Instances"]:

        public_ip = ""
        try:
            public_ip = inst["PublicIpAddress"]
        except:
            pass

        if public_ip != "":

            machine = {}
            machine["PublicIpAddress"] = public_ip

print result