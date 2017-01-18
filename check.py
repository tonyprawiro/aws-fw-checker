import boto3
import requests
import os
import json


def get_instance_tag_value(arr, tag_name = "Name"):
    """Return instance tag value"""
    result = ""
    try:
        for member in arr:
            if member["Key"] == "Name":
                result = member["Value"]
    except:
        pass
    return result

# Load exclusion list, exclude.json, which must be in the same directory as this file
exclusion_json = ""
with open("%s/exclude.json" % (os.path.dirname(os.path.realpath(__file__)))) as f:
    exclusion_json = f.read()
exclusions = json.loads(exclusion_json)

# Create boto3 EC2 client
ec2 = boto3.client('ec2',
                   aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                   aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                   region_name=os.environ["AWS_REGION_NAME"])

# Get security groups and cache group/ports information
secgroups = ec2.describe_security_groups()
secgroups_scrutiny = []
secgroups_public_ports = {}
for secgroup in secgroups["SecurityGroups"]:
    calc = []
    for ingress in secgroup["IpPermissions"]:
        if ingress["IpProtocol"] == "tcp":
            for ip_range in ingress["IpRanges"]:
                cidr = ""
                try:
                    cidr = ip_range["CidrIp"]
                except:
                    pass
                if cidr == "0.0.0.0/0":
                    s = "%s" % ingress["FromPort"]
                    if ingress["ToPort"] != ingress["FromPort"]:
                        s = "%s to %s" % (ingress["FromPort"], ingress["ToPort"])
                    calc.append(s)
                    secgroups_scrutiny.append(secgroup["GroupId"])
    secgroups_public_ports[secgroup["GroupId"]] = calc

# Get machines
instances = ec2.describe_instances(MaxResults=1000)
machines = []
for res in instances["Reservations"]:
    for inst in res["Instances"]:
        public_ip = ""
        try:
            public_ip = inst["PublicIpAddress"]
        except:
            pass
        if public_ip != "" and inst["State"]["Code"] == 16:
            machine = {}
            machine["State"] = inst["State"]["Name"]
            machine["InstanceId"] = inst["InstanceId"]
            machine["Name"] = get_instance_tag_value(arr=inst["Tags"], tag_name="Name")
            if machine["Name"] == "":
                machine["Name"] = inst["InstanceId"]
            machine["IpAddress"] = public_ip
            machine["Ports"] = []
            for grp in inst["SecurityGroups"]:
                if grp["GroupId"] in secgroups_scrutiny:
                    for secgroup in secgroups["SecurityGroups"]:
                        if secgroup["GroupId"] == grp["GroupId"]:
                            for ps in secgroups_public_ports[grp["GroupId"]]:
                                if ps not in machine["Ports"]:  # not already added
                                    try:
                                        if ps not in exclusions[inst["InstanceId"]]:
                                            machine["Ports"].append(ps)
                                    except:
                                        machine["Ports"].append(ps)
            if len(machine["Ports"]) > 0:
                machines.append(machine)

# Generate the output
output = "_~Daily EC2 SecGroup Sanity Check~_\n"
if len(machines)>0:
    output += "The following EC2 instances are running and are publicly accessible (0.0.0.0/0) at the following port(s). "
    output += "Please review and ensure appropriate access control is in place. "
    output += "To add machine:port into exclusion list, please inform @tonyhadimulyono.\n"
    output += ""
    output += "\n"
    for machine in machines:
        output += "Name: %s (%s)\n" % (machine["Name"], machine["InstanceId"])
        output += "IP address: %s\n" % machine["IpAddress"]
        output += "Port(s): %s\n" % (", ".join(machine["Ports"]))
        output += "\n"
else:
    output += "\nEverything seems to be in order. See you tomorrow~"

print output

# Send result via Telegram
print "Sending result via Telegram... "
try:
    requests.post(url = "https://api.telegram.org/bot%s/sendMessage" % os.environ["TELEGRAM_GDS_CHATOPS_BOT_TOKEN"],
                  data={
                        "parse_mode": "Markdown",
                        "chat_id": os.environ["TELEGRAM_FWCHECK_CHATGROUP_ID"],
                        "text": output
                  })
    print "done!"
except:
    print "failed!"
