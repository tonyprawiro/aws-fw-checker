import boto3
import requests
import os
import json


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


# Get account name from environment variable
account_name = os.environ["FWCHECK_ACCOUNT_NAME"]


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

# Load exclusion list, exclude.<ACCOUNT-NAME>.json, which must be in the same directory as this file
# the exclusion works both for EC2 and RDS instances
# example:
# {
#     "i-abc12345": [
#         "80",
#         "443"
#     ],
#     "i-def54321": [
#         "8443"
#     ],
#     "rds-instance-name1",
#     "rds-instance-name2"
# }
exclusion_json = ""
with open("%s/exclude.%s.json" % (os.path.dirname(os.path.realpath(__file__)), account_name)) as f:
    exclusion_json = f.read()
exclusions = json.loads(exclusion_json)


# Create boto3 EC2 client
ec2 = boto3.client('ec2',
                   aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                   aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                   region_name=os.environ["AWS_REGION_NAME"])


# Create boto3 RDS client
rds = boto3.client('rds',
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


# Get RDS instances
rds_instances = rds.describe_db_instances()
databases = []
for db in rds_instances["DBInstances"]:

    if db["PubliclyAccessible"] and db["DBInstanceStatus"]=="available":

        dbdata = {}
        dbdata["DBInstanceIdentifier"] = db["DBInstanceIdentifier"]
        dbdata["DBName"] = db["DBName"]
        dbdata["Engine"] = db["Engine"]
        dbdata["Endpoint"] = "%s:%d" % (db["Endpoint"]["Address"], db["Endpoint"]["Port"])
        dbdata["Ports"] = []

        for grp in db["VpcSecurityGroups"]:

            if grp["VpcSecurityGroupId"] in secgroups_scrutiny:  # If the security group contains 0.0.0.0/0

                for ps in secgroups_public_ports[grp["VpcSecurityGroupId"]]: # Check the ports in this security group

                    secgroup_port = secgroups_public_ports[grp["VpcSecurityGroupId"]]

                    if " to " in secgroup_port:
                        from_port, to_port = secgroup_port.split(" to ", 2)
                    else:
                        from_port = secgroup_port
                        to_port = secgroup_port

                    if from_port <= db["Endpoint"]["Port"] <= to_port:
                        dbdata["Ports"].append(ps)

        if len(dbdata["Ports"]) > 0:  #
            databases.append(dbdata)


# Generate the output, fancy stuff..
total_machines = len(machines)
total_databases = len(databases)
if total_machines>0 or total_databases>0:

    output = "*Account: %s*\n\n" % account_name

    for machine in machines:
        output += "Name: %s (%s)\n" % (machine["Name"], machine["InstanceId"])
        output += "IP address: %s\n" % machine["IpAddress"]
        output += "Port(s): %s\n" % (", ".join(machine["Ports"]))
        output += "\n"

    for database in databases:

        output += "RDS Instance Name/Schema (Engine): %s/%s (%s)\n" % (database["DBInstanceIdentifier"],
                                                                       database["DBName"],
                                                                       database["Engine"])
        output += "Endpoint: %s\n" % database["Endpoint"]
        output += "\n"

    output += "%d EC2 and RDS instance(s) are whitelisted. " % len(exclusions)
    output += "Follow-up is needed for for %d instance(s) outside of the whitelist." % (total_machines + total_databases)

else:

    output = "*Account %s*: %d EC2 and RDS instance(s) are whitelisted. " % (account_name, len(exclusions))
    output+= "Everything is in order.\n"


# Send result to stdout
print output

# Send result via Telegram
try:
    requests.post(url = "https://api.telegram.org/bot%s/sendMessage" % os.environ["TELEGRAM_BOT_TOKEN"],
                  data={
                        "parse_mode": "Markdown",
                        "chat_id": os.environ["TELEGRAM_CHATGROUP_ID"],
                        "text": output
                  })
except:
    pass
