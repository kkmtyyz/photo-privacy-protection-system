"use client";

import { useState, useEffect } from "react";
import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";
import { useAuthenticator } from "@aws-amplify/ui-react";
import {
  FetchUserAttributesOutput,
  fetchUserAttributes,
  FetchAuthSessionOutput,
  fetchAuthSession
} from "aws-amplify/auth";
import { getUrl } from "aws-amplify/storage";
import { Button } from "@/app/components/Button";
import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";

Amplify.configure(outputs);

const client = generateClient<Schema>();

export default function Home() {
  const [user, setUser] = useState<FetchAuthSessionOutput>();
  const [userAttr, setUserAttr] = useState<FetchUserAttributesOutput>();
  const { signOut } = useAuthenticator();

  // 体験フォトの情報を持つ
  const [photos, setPhotos] =
    useState<Schema["ExperiencePhotoForUser"]["type"][]>([]);

  // 体験フォトのS3署名付きURLを持つ
  const [photoUrls, setPhotoUrls] = useState<Record<string, string>>({});

  /*
   * ユーザー情報取得
   */
  useEffect(() => {
    const load = async () => {
      const attr = await fetchUserAttributes();
      setUserAttr(attr);

      const session = await fetchAuthSession();
      setUser(session);
    };
    load();
  }, []);


  /*
   * 初回サインイン時にユーザー情報テーブルのitemを作る
   * S3上の体験フォトへのアクセスはCognito IDプールのidentityIdで認可されるが、
   * バックエンド側でユーザープールのユーザーID(Sub)と紐づけられないため。
   * ここで作成したitemは以下2箇所で使用している。
   *   - WorkSpaces Applicationsの体験フォト確認アプリがS3上へ画像を配置する際のS3キー
   *   - 体験フォト確認アプリがユーザーへ完了通知メール送信する際の送信先アドレス
   */
  useEffect(() => {
    if (!user || !userAttr) return;

    const userInit = async () => {
      await client.models.UserSubIdentityId.create(
        {
          userSub: user.userSub,
          identityId: user.identityId,
          email: userAttr.email
        },
        {
          condition: {
            userSub: { attributeExists: false }
          }
        }
      );
    };

    userInit();
  }, [user, userAttr]);

  /*
   * AppSyncから体験フォト情報を取得し、S3から体験フォトを取得する
   */
  useEffect(() => {
    if (!user) return;

    // 体験フォト情報を撮影日時で降順にして取得する
    const loadPhotos = async () => {
      const result = await client.models.ExperiencePhotoForUser.list({
        userId: user.userSub,
        sortDirection: "DESC"
      });

      const photoList = result.data;
      setPhotos(photoList);

      // 体験フォトのS3署名付きURLを取得する
      const urls: Record<string, string> = {};
      for (const photo of photoList) {
        const res = await getUrl({
          path: `experiencePhotoForUser/${user.identityId}/${photo.photoId}.png`
        });

        urls[photo.photoId] = res.url.toString();
      }

      setPhotoUrls(urls);
    };

    loadPhotos();
  }, [user]);

  return (
    <main className="p-6">
      <h2 className="mt-3 text-xl font-bold text-center">
        体験フォト一覧
      </h2>

      <div className="grid grid-cols-2 gap-4 mt-6">
        {photos.map((photo) => (
          <div
            key={photo.photoId}
            className="bg-white rounded-lg shadow overflow-hidden"
          >
            <div className="px-2 py-2 text-xl text-gray-600 text-center">
              {new Date(photo.takenAt).toLocaleString()}
            </div>
            <img
              src={photoUrls[photo.photoId]}
              alt="photo"
              className="w-full object-contain"
            />
          </div>
        ))}
      </div>

      <div className="flex justify-center mt-8">
        <Button type="button" onClick={signOut}>
          Sign out
        </Button>
      </div>
    </main>
  );
}
