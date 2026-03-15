import { Construct } from "constructs";

export class AppConfig extends Construct {
  /*
   * general
   */
  appName = "photo-protection";

  /*
   * vpc
   */
  vpcCidr = "10.0.0.0/16";
}
