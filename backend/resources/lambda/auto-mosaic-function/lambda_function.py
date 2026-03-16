from __future__ import annotations
import boto3
import cv2
import numpy as np
import math
import sys
import urllib
import os
import json
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta

rekognition = boto3.client("rekognition")
dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")

PHOTO_TABLE_NAME = os.environ["EXPERIENCE_PHOTO_PROCESSING_TABLE_NAME"]
PHOTO_REVIEW_QUEUE_URL = os.environ["PHOTO_REVIEW_QUEUE_URL"]

STATUS_CREATED = "CREATED"
STATUS_PROCESSING = "PROCESSING"
STATUS_AUTO_MOSAICED = "AUTO_MOSAICED"


class ImageData:
    """
    画像データのバイト列や幅、高さなどを持つ

    Attributes:
        img_bytes: bytes
        img_ndarray: ndarray
        height: int
        width: int
        channel: int
    """

    def __init__(self, image_path: str):
        with open(image_path, "rb") as image_file:
            self.img_bytes = image_file.read()

        nparr = np.frombuffer(self.img_bytes, np.uint8)
        self.img_ndarray = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        self.height, self.width, self.channel = self.img_ndarray.shape


class Point:
    """
    座標を持つ

    Attributes:
        x: float
        y: float
    """

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def distance(self, other: Point) -> float:
        """
        other座標との距離を返す
        """
        return math.hypot(self.x - other.x, self.y - other.y)


class BoundingBox:
    """
    バウンディングボックスの左上座標、右下座標、幅、高さ、中心座標を持つ

    Attributes:
        top_left: Point
        bottom_right: Point
        width: float
        height: float
        center: Point
    """

    def __init__(self, top: float, left: float, height: float, width: float):
        self.top_left = Point(left, top)
        self.bottom_right = Point(left + width, top + height)
        self.width = width
        self.height = height
        self.center = Point(left + width / 2, top + height / 2)

    def contains(self, other: BoundingBox) -> bool:
        """
        otherがこのバウンディングボックスの内部にある場合、Trueを返す
        """
        return (
            self.top_left.x <= other.top_left.x
            and self.top_left.y <= other.top_left.y
            and self.bottom_right.x >= other.bottom_right.x
            and self.bottom_right.y >= other.bottom_right.y
        )


def get_person_bounding_boxes(image_data: ImageData) -> list[BoundingBox]:
    """
    rekognitionで人のバウンディングボックスを取得
    return [BoundingBox]
    """
    res = rekognition.detect_labels(
        Image={"Bytes": image_data.img_bytes},
        # MaxLabels=50,
        MinConfidence=80.0,
        Features=["GENERAL_LABELS"],
        Settings={"GeneralLabels": {"LabelInclusionFilters": ["Person"]}},
    )

    bounding_boxes = []

    for face_detail in res["Labels"][0]["Instances"]:
        # rekognitionからは比率が返るため、高さや幅を掛けて座標を得る
        top = face_detail["BoundingBox"]["Top"] * image_data.height
        left = face_detail["BoundingBox"]["Left"] * image_data.width
        height = face_detail["BoundingBox"]["Height"] * image_data.height
        width = face_detail["BoundingBox"]["Width"] * image_data.width
        bounding_boxes.append(BoundingBox(top, left, height, width))

    return bounding_boxes


def find_main_person(
    image_data: ImageData, person_bounding_boxes: [BoundingBox]
) -> int:
    """
    画像の中心に最も近いバウンディングボックスのインデックスを返す
    インデックスは0ベース
    """
    # 画像の中心座標
    center_point = Point(image_data.width / 2, image_data.height / 2)

    min_distance = sys.maxsize
    main_box_index = None
    for index, bounding_box in enumerate(person_bounding_boxes):
        # 中心からバウンディングボックスの中心までの距離
        distance = center_point.distance(bounding_box.center)
        if distance < min_distance:
            min_distance = distance
            main_box_index = index
    return main_box_index


def get_face_bounding_boxes(image_data: ImageData) -> list[BoundingBox]:
    """
    rekognitionで顔のバウンディングボックスを取得
    return [BoundingBox]
    """
    res = rekognition.detect_faces(Image={"Bytes": image_data.img_bytes})

    bounding_boxes = []

    for face_detail in res["FaceDetails"]:
        # rekognitionからは比率が返るため、高さや幅を掛けて座標を得る
        top = face_detail["BoundingBox"]["Top"] * image_data.height
        left = face_detail["BoundingBox"]["Left"] * image_data.width
        height = face_detail["BoundingBox"]["Height"] * image_data.height
        width = face_detail["BoundingBox"]["Width"] * image_data.width
        bounding_boxes.append(BoundingBox(top, left, height, width))

    return bounding_boxes


def find_main_face(
    main_person_box: BoundingBox, face_bounding_boxes: [BoundingBox]
) -> int:
    """
    メイン人物の顔のインデックスを返す
    インデックスは0ベース

    メイン人物の顔の判定方法:
        main_person_boxの内部にある and 顔の面積が最大
    """
    max_face_size = 0
    main_face_index = None
    for index, face_box in enumerate(face_bounding_boxes):
        if main_person_box.contains(face_box):
            # メイン人物の身体バウンディングボックスの内部に顔がある場合
            face_size = face_box.width * face_box.height
            if max_face_size < face_size:
                # 顔の面積が最大の場合
                max_face_size = face_size
                main_face_index = index

    if main_face_index is None:
        # 顔が見つからなかった場合
        raise Exception("The Main face was not found.")

    return main_face_index


def apply_mosaic_to_other_faces(
    image_data: ImageData, face_bounding_boxes: [BoundingBox], main_face_box_index: int
) -> np.ndarray:
    """
    メイン人物以外の顔にモザイク処理を施したnumpy配列を返す
    """
    mosaiced_ndarray = image_data.img_ndarray.copy()
    for index, face_box in enumerate(face_bounding_boxes):
        if index == main_face_box_index:
            # メイン人物の顔はスキップ
            continue

        # モザイク処理する領域
        # バウンディングボックスの座標が画像内に納まっていない場合は0とする
        x1 = max(0, min(image_data.width, int(face_box.top_left.x)))
        x2 = max(0, min(image_data.width, int(face_box.bottom_right.x)))
        y1 = max(0, min(image_data.height, int(face_box.top_left.y)))
        y2 = max(0, min(image_data.height, int(face_box.bottom_right.y)))

        # 対象領域
        region = mosaiced_ndarray[y1:y2, x1:x2]

        # 顔の領域を縮小して再度拡大することでモザイク処理する
        scale = 0.05  # 小さいほど粗いモザイク
        roi_small = cv2.resize(region, (0, 0), fx=scale, fy=scale)
        noise = cv2.resize(
            roi_small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST
        )

        # 上書き
        mosaiced_ndarray[y1:y2, x1:x2] = noise

    return mosaiced_ndarray


def apply_bounding_boxes(
    image_data: ImageData,
    bounding_boxes: [BoundingBox],
    target_index: int | None = None,
) -> np.ndarray:
    """
    バウンディングボックスを線で表示した画像（numpy配列）を返す
    target_indexが設定されている場合、そのボックスのみ異なる色で表示する
    """
    copy_ndarray = image_data.img_ndarray.copy()
    for index, box in enumerate(bounding_boxes):
        # coler = (0, 0, 255)
        # coler = (255, 0, 0)
        coler = (0, 255, 0)
        if index == target_index:
            # coler = (255, 0, 0)
            coler = (0, 0, 255)
        cv2.rectangle(
            copy_ndarray,
            (int(box.top_left.x), int(box.top_left.y)),
            (int(box.bottom_right.x), int(box.bottom_right.y)),
            coler,
            thickness=5,
        )

    return copy_ndarray


def debug_bounding_boxes(
    image_data: ImageData,
    bounding_boxes: [BoundingBox],
    target_index: int | None = None,
):
    """
    バウンディングボックスのデバッグ用画像を出力する
    target_indexが設定されている場合、そのボックスのみ異なる色で表示する
    """
    image_ndarray = apply_bounding_boxes(image_data, bounding_boxes, target_index)
    cv2.imwrite("output.png", image_ndarray)


def acquire_lock(photo_id):
    """
    DynamoDBのステータスを更新して処理ロックを取得する。
    S3イベント通知をトリガーとしてこのLambda関数が実行されるため、
    ロックを取得することで、同じ写真に対して処理が重複実行されることを防ぐ。

    ロック取得条件:
        status が CREATED
        または
        status が PROCESSING かつ processingExpiresAt が現在時刻より過去

    ロック取得時は status を PROCESSING に更新し、
    processingExpiresAt に15分後の期限を設定する
    """
    now_dt = datetime.now(timezone.utc)
    now = int(now_dt.timestamp())
    expires = int((now_dt + timedelta(minutes=15)).timestamp())
    now_jst_str = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

    try:
        dynamodb.update_item(
            TableName=PHOTO_TABLE_NAME,
            Key={"photoId": {"S": photo_id}},
            UpdateExpression="""
                SET #status = :processing,
                    updatedAt = :now_jst_str,
                    processingExpiresAt = :expires
            """,
            ConditionExpression="""
                #status = :created
                OR (#status = :processing AND processingExpiresAt < :now)
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":created": {"S": STATUS_CREATED},
                ":processing": {"S": STATUS_PROCESSING},
                ":expires": {"N": str(expires)},
                ":now": {"N": str(now)},
                ":now_jst_str": {"S": now_jst_str},
            },
        )

        print("lock acquired:", photo_id)
        return True

    except dynamodb.exceptions.ConditionalCheckFailedException:
        print("lock denied:", photo_id)
        return False


def complete(photo_id):
    """
    DynamoDBのステータスを更新して画像処理を完了状態にする。
    ロック取得の条件から、ロックの解放を兼ねてる。

    status を AUTO_MOSAICED に更新し、
    processingExpiresAt を削除する
    updatedAt を現在時刻に更新する
    """
    now = datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

    dynamodb.update_item(
        TableName=PHOTO_TABLE_NAME,
        Key={"photoId": {"S": photo_id}},
        UpdateExpression="""
            SET #status = :done,
                updatedAt = :now
            REMOVE processingExpiresAt
        """,
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":done": {"S": STATUS_AUTO_MOSAICED},
            ":now": {"S": now},
        },
    )


def lambda_handler(event, context):
    print(event)
    print(context)
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        print("bucket:", bucket)
        print("key:", key)

        # PhotoIDとUserIdの取得
        # S3キーの後ろが /<user_id>/<photo_id>.png となっている
        filename = key.split("/")[-1]
        photo_id = filename.split(".")[0]
        user_id = key.split("/")[-2]

        # 重複処理を防止するためにロック取得
        if not acquire_lock(photo_id):
            print("lock not acquired:", photo_id)
            continue

        # 画像データをS3から取得
        local_input_path = f"/tmp/{photo_id}.png"
        s3.download_file(bucket, key, local_input_path)
        image_data = ImageData(local_input_path)

        # 人間を検出
        person_bounding_boxes: [BoundingBox] = get_person_bounding_boxes(image_data)

        # 主要人物の身体バウンディングボックスを特定する
        main_person_box_index: int = find_main_person(image_data, person_bounding_boxes)

        # 顔を検出
        face_bounding_boxes: [BoundingBox] = get_face_bounding_boxes(image_data)

        # 主要人物の顔バウンディングボックスを特定する
        main_face_box_index: int = find_main_face(
            person_bounding_boxes[main_person_box_index], face_bounding_boxes
        )

        # debug_bounding_boxes(image_data, face_bounding_boxes, main_face_box_index)

        # 主要人物以外の顔をモザイク処理
        mosaiced_image_ndarray: np.ndarray = apply_mosaic_to_other_faces(
            image_data, face_bounding_boxes, main_face_box_index
        )

        # 確認用画像書き出し
        # cv2.imwrite("output.png", mosaiced_image_ndarray)

        # 画像保存
        output_key = f"auto_mosaiced/{user_id}/{photo_id}.png"
        success, encoded_image = cv2.imencode(".png", mosaiced_image_ndarray)
        if not success:
            raise Exception("Failed to encode mosaiced image to PNG.")

        s3.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=encoded_image.tobytes(),
            ContentType="image/png",
        )

        # SQSキューへメッセージ送信
        sqs.send_message(
            QueueUrl=PHOTO_REVIEW_QUEUE_URL,
            MessageBody=json.dumps(
                {
                    "photo_id": photo_id,
                    "user_id": user_id,
                    "bucket": bucket,
                    "s3_key": output_key,
                }
            ),
        )

        # ステータス更新（ロック解放を兼ねる）
        complete(photo_id)

