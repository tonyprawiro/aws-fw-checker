# -*- coding: UTF-8 -*-
import requests
import os
import sys
import check_ec2
import check_rds


def main():
    """The main flow"""

    # Retrieve all required environment variables
    try:
        account_name = os.environ["FWCHECK_ACCOUNT_NAME"]
        aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
        aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
        region_name = os.environ["AWS_REGION_NAME"]
        telegram_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
        telegram_chat_id = os.environ["TELEGRAM_CHATGROUP_ID"]
    except:
        print "The script requires the following environment variables:"
        print "FWCHECK_ACCOUNT_NAME"
        print "AWS_ACCESS_KEY_ID"
        print "AWS_SECRET_ACCESS_KEY"
        print "AWS_REGION_NAME"
        sys.exit(1)

    exclusion_path = "%s/exclude.%s.json" % (os.path.dirname(os.path.realpath(__file__)), account_name)

    alerted_path = "%s/alerted.%s.json" % (os.path.dirname(os.path.realpath(__file__)), account_name)

    # Get security groups from EC2, and then cache group/ports information for easy lookup later
    secgroups, secgroups_with_0000_0, secgroups_public_ports = \
        check_ec2.get_secgroups(aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key,
                                region_name=region_name)

    # Get exposed machines
    machines = check_ec2.check_ec2(aws_access_key_id=aws_access_key_id,
                                   aws_secret_access_key=aws_secret_access_key,
                                   region_name=region_name,
                                   secgroups_with_0000_0=secgroups_with_0000_0,
                                   secgroups_public_ports=secgroups_public_ports,
                                   exclusion_path=exclusion_path,
                                   alerted_path=alerted_path)

    # Get exposed RDS instances
    databases = check_rds.check_rds(aws_access_key_id=aws_access_key_id,
                                    aws_secret_access_key=aws_secret_access_key,
                                    region_name=region_name,
                                    secgroups_with_0000_0=secgroups_with_0000_0,
                                    secgroups_public_ports=secgroups_public_ports,
                                    exclusion_path=exclusion_path,
                                    alerted_path=alerted_path)

    # Generate the output, fancy stuff..
    total_machines = len(machines)
    total_databases = len(databases)
    total_all = total_machines + total_databases
    if total_machines > 0 or total_databases > 0:

        output = u'\U0001F525' + "*Account: %s.*" % account_name + u'\U0001F525' + "\n\n"

        for machine in machines:
            output += "Instance: %s (%s)\n" % (machine["Name"], machine["InstanceId"])
            output += "IP address: %s\n" % machine["IpAddress"]
            output += "Open port(s): %s\n" % (", ".join(machine["Ports"]))
            output += "\n"

        for database in databases:
            output += "RDS Instance Name/Schema (Engine): %s/%s (%s)\n" % (database["DBInstanceIdentifier"],
                                                                           database["DBName"],
                                                                           database["Engine"])
            output += "Endpoint: %s\n" % database["Endpoint"]
            output += "\n"

        output += "Total = %d item(s)" % total_all

        # Send result via Telegram
        try:
            requests.post(url="https://api.telegram.org/bot%s/sendMessage" % telegram_bot_token,
                          data={
                              "parse_mode": "Markdown",
                              "chat_id": telegram_chat_id,
                              "text": output
                          })
        except:
            pass

        # Send result to stdout
        print output.encode('utf-8')


if __name__ == "__main__":
    main()

