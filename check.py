import boto3
import requests
import os

# Return isntance tag value
def get_instance_tag_value(arr, tagName = "Name"):
    result = ""
    try:
        for member in arr:
            if member["Key"] == "Name":
                result = member["Value"]
    except:
        pass
    return result

# Create boto3 EC2 client
ec2 = boto3.client('ec2')

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
instances = ec2.describe_instances(MaxResults = 1000)
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
            machine["Name"] = get_instance_tag_value(inst["Tags"], "Name")
            if machine["Name"] == "":
                machine["Name"] = inst["InstanceId"]
            machine["IpAddress"] = public_ip
            machine["Ports"] = []
            is_machine_exposed = False
            for grp in inst["SecurityGroups"]:
                if grp["GroupId"] in secgroups_scrutiny:
                    is_machine_exposed = True
                    for secgroup in secgroups["SecurityGroups"]:
                        if secgroup["GroupId"] == grp["GroupId"]:
                            machine["Ports"] = secgroups_public_ports[grp["GroupId"]]
            if is_machine_exposed:
                machines.append(machine)

output  = "_~Daily EC2 SecGroup Sanity Check~_\n"
output += "The following EC2 instances are running and are publicly accessible (0.0.0.0/0) at the following port(s). "
output += "Please review and ensure appropriate access control is in place.\n"
output += ""
output += "\n"
for machine in machines:
    output += "Name: " + machine["Name"]+ "\n"
    output += "IP address: "  + machine["IpAddress"] + "\n"
    output += "Port(s): " + ", ".join(machine["Ports"]) + "\n"
    output += "\n"

print output

print "Sending result via Telegram..."
try:
    requests.post(url = "https://api.telegram.org/bot%s/sendMessage" % os.environ["TELEGRAM_GDS_CHATOPS_BOT_TOKEN"], data={
        "parse_mode": "Markdown",
        "chat_id": os.environ["TELEGRAM_FWCHECK_CHATGROUP_ID"],
        "text": output
    })
except:
    print "Failed!"

