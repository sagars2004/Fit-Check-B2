import os
import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("B2_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("B2_KEY_ID"),
    aws_secret_access_key=os.getenv("B2_APP_KEY"),
    region_name=os.getenv("B2_REGION"),
)

cors_configuration = {
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
            "AllowedOrigins": ["http://localhost:3000"],
            "ExposeHeaders": [],
            "MaxAgeSeconds": 3600,
        }
    ]
}

try:
    s3.put_bucket_cors(
        Bucket=os.getenv("B2_BUCKET"), CORSConfiguration=cors_configuration
    )
    print("SUCCESS: CORS rules updated for Backblaze B2.")
except Exception as e:
    print(f"FAILED to update CORS rules: {e}")
