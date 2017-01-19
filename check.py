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
# example:
# {
#     "i-abc12345": [
#         "80",
#         "443"
#     ],
#     "i-def54321": [
#         "8443"
#     ]
# }
exclusion_json = ""
with open("%s/exclude.json" % (os.path.dirname(os.path.realpath(__file__)))) as f:
    exclusion_json = f.read()
exclusions = json.loads(exclusion_json)


# Create boto3 EC2 client
ec2 = boto3.client('ec2',
                   aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                   aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                   region_name=os.environ["AWS_REGION_NAME"])


# Get security groups from EC2, and then cache group/ports information for easy lookup later
secgroups = ec2.describe_security_groups()
secgroups_scrutiny = []  # Security group IDs that contains 0.0.0.0/0
secgroups_public_ports = {}  # Ports
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
instances = ec2.describe_instances(MaxResults=1000)  # Get all machines
machines = []
for res in instances["Reservations"]:

    for inst in res["Instances"]:

        """inst is a single instance"""
        public_ip = ""
        try:
            public_ip = inst["PublicIpAddress"]
        except:
            pass

        if public_ip != "" and inst["State"]["Code"] == 16:  # Only process if machine is running with public IP

            # Gather basic information about the machine
            machine = {}
            machine["State"] = inst["State"]["Name"]
            machine["InstanceId"] = inst["InstanceId"]
            machine["Name"] = get_instance_tag_value(arr=inst["Tags"], tag_name="Name")
            if machine["Name"] == "":
                machine["Name"] = inst["InstanceId"]
            machine["IpAddress"] = public_ip
            machine["Ports"] = []

            # Iterate all security groups associated with the machine
            for grp in inst["SecurityGroups"]:

                if grp["GroupId"] in secgroups_scrutiny:  # If the security group contains 0.0.0.0/0 (in scrutiny)

                    for ps in secgroups_public_ports[grp["GroupId"]]:  # Check the ports in this security group

                        if ps not in machine["Ports"]:  # If this port has not been noted before

                            # If there is exclusion for this machine, and the port is not in the list,
                            # then note this port
                            # If there is no exclusion for this machine, then note this port
                            try:
                                if ps not in exclusions[inst["InstanceId"]]:
                                    machine["Ports"].append(ps)
                            except:
                                machine["Ports"].append(ps)

            if len(machine["Ports"]) > 0:  # There are some exposed ports and not in exclusion list
                machines.append(machine)


# Generate the output, fancy stuff..
output = "_~Daily EC2 SecGroup Sanity Check~_\n\n"
if len(machines)>0:
    output += "The following EC2 instances are running, have public IP addresses, "
    output += "and are publicly accessible (0.0.0.0/0) at the following port(s). "
    output += "Please review and ensure appropriate access control is in place. "
    output += "\n\n"
    for machine in machines:
        output += "Name: %s (%s)\n" % (machine["Name"], machine["InstanceId"])
        output += "IP address: %s\n" % machine["IpAddress"]
        output += "Port(s): %s\n" % (", ".join(machine["Ports"]))
        output += "\n"
else:
    output += "Everything seems to be in order. See you tomorrow~\n"

output += "\nTo check the exclusion list, or add machine:port into the list, please inform DevOps team.\n"


# Send result to stdin
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

