import boto3
import os
from datetime import datetime, timedelta


class CloudWatchReader:
    def __init__(self):
        self.client = boto3.client(
            "cloudwatch",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

    def get_ec2_cpu(self, instance_id: str):
        end = datetime.utcnow()
        start = end - timedelta(minutes=5)

        response = self.client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[
                {"Name": "InstanceId", "Value": instance_id}
            ],
            StartTime=start,
            EndTime=end,
            Period=300,
            Statistics=["Average"]
        )

        datapoints = response.get("Datapoints", [])

        if not datapoints:
            return 0.0

        latest = sorted(datapoints, key=lambda x: x["Timestamp"])[-1]
        return float(latest["Average"])