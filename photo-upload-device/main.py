import requests
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo


# デプロイしたAPI GWのエンドポイントURLに置き換える
API_ENDPOINT_URL = "https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/"

# cognitoに登録したユーザーのユーザーIDに置き換える
USER_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

PHOTO_ID = str(uuid.uuid4())
PHOTO_FILE_PATH = "./sample-photo-01.png"
#PHOTO_FILE_PATH = "./sample-photo-02.png"


def main():
    """
    体験フォトアップロードAPI呼出し
    """
    body = {
        "photo_id": PHOTO_ID,
        "user_id": USER_ID,
        "taken_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
    }

    url = API_ENDPOINT_URL + "experience-photos"
    headers = {"Content-type": "application/json"}
    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        print(200)
        print(response.json())
    else:
        print("failed", response.status_code)
        print(response)
        raise

    """
    署名済みURLを用いてS3へ体験フォトをアップロード
    """
    data = response.json()
    upload_url = data["uploadUrl"]

    print("Upload URL:", upload_url)

    # S3へPUTアップロード
    with open(PHOTO_FILE_PATH, "rb") as f:
        upload_response = requests.put(
            upload_url, data=f, headers={"Content-Type": "image/png"}
        )

    print("Upload status:", upload_response.status_code)

    if upload_response.status_code == 200:
        print("Upload success")
    else:
        print(upload_response.text)
        raise


if __name__ == "__main__":
    main()
