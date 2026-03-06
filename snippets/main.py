from __future__ import annotations
import boto3
import cv2
import numpy as np
import math
import sys


IMAGE_PATH = "../resources/sample-photo-01.png"

session = boto3.Session(profile_name="kkmtyyz_mfa")
rek_client = session.client("rekognition")


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


def get_person_bounding_boxes(image_data: ImageData) -> [BoundingBox]:
    """
    rekognitionで人のバウンディングボックスを取得
    return [BoundingBox]
    """
    res = rek_client.detect_labels(
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


def get_face_bounding_boxes(image_data: ImageData) -> [BoundingBox]:
    """
    rekognitionで顔のバウンディングボックスを取得
    return [BoundingBox]
    """
    res = rek_client.detect_faces(Image={"Bytes": image_data.img_bytes})

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
        # print(f"{x1}, {x2}, {y1}, {y2}")

        # ランダムノイズ生成（必ずサイズ一致）
        # noise = np.random.randint(0, 256, (y2 - y1, x2 - x1, channel), dtype=np.uint8)

        # 対象領域
        region = mosaiced_ndarray[y1:y2, x1:x2]

        # 平均色
        # mean_color = region.mean(axis=(0, 1))

        # ±30 のランダムノイズを入れる
        # noise = np.clip(
        #    np.random.normal(loc=mean_color, scale=30, size=region.shape), 0, 255
        # ).astype(np.uint8)

        # 顔の領域を縮小して再度拡大することでモザイク処理する
        scale = 0.05  # 小さいほど粗いモザイク
        roi_small = cv2.resize(region, (0, 0), fx=scale, fy=scale)
        noise = cv2.resize(
            roi_small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST
        )

        # 上書き
        mosaiced_ndarray[y1:y2, x1:x2] = noise

        # ランダムノイズ生成
        # noise = np.random.randint(0, 256, (int(face_bottom - face_top), int(face_right - face_left), channel), dtype=np.uint8)
        ##img[int(face_top):int(face_bottom), int(face_right):int(face_left)] = noise
        # img[int(face_top):int(face_bottom), int(face_left):int(face_right)] = noise

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
        #coler = (0, 0, 255)
        #coler = (255, 0, 0)
        coler = (0, 255, 0)
        if index == target_index:
            #coler = (255, 0, 0)
            coler = (0, 0, 255)
        cv2.rectangle(
            copy_ndarray,
            (int(box.top_left.x), int(box.top_left.y)),
            (int(box.bottom_right.x), int(box.bottom_right.y)),
            coler,
            thickness=5
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


if __name__ == "__main__":
    # 画像読み込み
    image_data = ImageData(IMAGE_PATH)

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

    #debug_bounding_boxes(image_data, face_bounding_boxes, main_face_box_index)

    # 主要人物以外の顔をモザイク処理
    mosaiced_image_ndarray: np.ndarray = apply_mosaic_to_other_faces(
        image_data, face_bounding_boxes, main_face_box_index
    )

    # 画像書き出し
    cv2.imwrite("output.png", mosaiced_image_ndarray)
