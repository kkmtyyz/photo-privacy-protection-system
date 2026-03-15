import { SignatureV4 } from "@aws-sdk/signature-v4";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { Sha256 } from "@aws-crypto/sha256-js";
import { HttpRequest } from "@aws-sdk/protocol-http";

const endpoint = process.env.APPSYNC_ENDPOINT_URL!;
const region = process.env.AWS_REGION!;

/*
 * AppSyncへのGraphQLクエリをプロキシする関数
 *
 * 今回のAppSync GraphQL APIはPublic APIなので、VPC内からVPCエンドポイント経由で呼び出せない。
 * そのため、クエリをプロキシするLambda関数が必要となる。
 * AppSyncへのクエリはIAM認証が必要なので、API Gatewayのプロキシ統合ではシンプルに実現できない。
 */
export const handler = async (event: any) => {
  console.log(event);
  const { query, variables } = event;
  if (!query) {
    throw new Error("query is required");
  }

  const url = new URL(endpoint);

  const body = JSON.stringify({
    query,
    variables
  });

  const request = new HttpRequest({
    method: "POST",
    hostname: url.hostname,
    path: url.pathname,
    headers: {
      "Content-Type": "application/json",
      host: url.hostname
    },
    body
  });

  const signer = new SignatureV4({
    credentials: defaultProvider(),
    region,
    service: "appsync",
    sha256: Sha256
  });

  const signedRequest = await signer.sign(request);

  const response = await fetch(endpoint, {
    method: "POST",
    headers: signedRequest.headers as any,
    body
  });

  const result = await response.json();
  console.log(result);

  if (!response.ok || result.errors) {
    console.error("AppSync error:", result);
    throw new Error("AppSync request failed");
  }

  return result.data;
};
