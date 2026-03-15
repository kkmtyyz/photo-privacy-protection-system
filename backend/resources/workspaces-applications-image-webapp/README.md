# WorkSpaces Applications Image 作成方法

## ファイル説明
- webapp
  - WorkSpaces Applicationsで実行する「体験フォト確認アプリ」
- SessionScripts/config.json
  - WorkSpaces ApplicationsのSessionScript設定ファイル

## 事前準備
- private subnetでイメージ作成するので、webappで `npm install` し、モジュールを全てダウンロードしておく
- アプリの実行にnodejsが必要なので、private subnetでインストールできるようにインストーラーをダウンロードしておく（node-v24.11.1-x64.msi）
- Builderインスタンスにファイルを持っていくため、webapp, SessionScripts, node-v24.11.1-x64.msi をまとめてfor-ws.zipを作っておく

## Image BuilderでのImage作成手順
- WorkSpaces Applications > Image builders から Launch Image builder をクリック
- Builderインスタンスの設定
  - Base Image
    - AppStream-WinServer2022-11-10-2025
  - Instance type
    - General Purpose
    - stream.standard
    - large
  - Storage
    - 200(default)
  - IAM role
    - 必要な権限が付いたIAMロールを作成する
  - Network access
    - 作成したPrivate Subnetを選択する

- BuilderインスタンスでImage作成
  - Builderインスタンスがpendingからrunningになったら、アクションからconnectする
  - switch user画面が出るのでlocal userのadministratorで始める
  - My FilesからTemporary Filesにfor-ws.zipをアップロードする
  - for-ws.zipを解凍
  - `node-v24.11.1-x64`を実行してnodejsをインストールする
  - `C:\\App` を作成し、解凍したwebappをコピーする
    - `C:\\App\\webapp` となる
  - `C:\\AppStream\\SessionScripts\\config.json` を`SessionScripts/config.json`で置き換える
  - デスクトップのアイコンからImageAssistantを実行
  - Add Appからmsedge.exeを追加する
    - `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
    - Launch Parametersに以下を設定
      - `http://localhost:3000`
    - nextボタン押す
  - アプリ設定
    - 画面のガイドに従ってlocal userのtemplate userにswitch user
    - Edgeは最初開いたときアカウント連携設定が出るのでいいえで設定しておく
    - ImageAssistantを実行し、administratorにswitchして戻る
    - Save setting をクリックして設定を保存する
  - アプリテスト
    - test userにswitchしてテスト
    - PowerShellを起動し、`C:\\App\\webapp\\run.bat` を実行、Edgeを起動してアプリの動作確認をする
    - ImageAssistantを実行し、administratorにswitchして戻る
  - 最適化
    - Lounchボタンを押しす
      - アプリが自動で最適化される
  - イメージ設定
    - 作成するイメージ名などを設定する
  - イメージ作成

- イメージ作成後
  - Image registryでPendingとなってるのでAvailableになるまで待つ
    - AvailableになるとBuilderインスタンスは自動的に停止される
  - 作成されたイメージを指定してFleetを作成する
  - Stackを作成し、Fleetを関連付ける
  - Stackに接続してアプリを使う

