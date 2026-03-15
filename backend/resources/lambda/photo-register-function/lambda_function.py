import boto3
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import json

dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")

PHOTO_TABLE_NAME = os.environ["EXPERIENCE_PHOTO_PROCESSING_TABLE_NAME"]
PHOTO_BUCKET_NAME = os.environ["EXPERIENCE_PHOTO_BUCKET_NAME"]
PRESIGNED_URL_EXPIRES = int(os.environ["PRESIGNED_URL_EXPIRES_SECONDS"])

# statusは次のどれか CREATED PROCESSING AUTO_MOSAICED REVIEWED
STATUS_CREATED = "CREATED"


def lambda_handler(event, context):
    print(event)
    print(context)
    body = json.loads(event["body"])
    print(body)

    photo_id = body["photo_id"]
    user_id = body["user_id"]
    taken_at = body["taken_at"]

    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

    # 体験フォト管理テーブルにアイテム作成
    dynamodb.put_item(
        TableName=PHOTO_TABLE_NAME,
        Item={
            "photoId": {"S": photo_id},
            "userId": {"S": user_id},
            "status": {"S": STATUS_CREATED},
            "takenAt": {"S": taken_at},
            "createdAt": {"S": now},
            "updatedAt": {"S": now},
        },
    )

    # S3キー
    object_key = f"original/{user_id}/{photo_id}.png"

    # 署名付きURL生成（PUT）
    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": PHOTO_BUCKET_NAME,
            "Key": object_key,
            "ContentType": "image/png",
        },
        ExpiresIn=PRESIGNED_URL_EXPIRES,
    )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "uploadUrl": upload_url,
            }
        ),
    }
