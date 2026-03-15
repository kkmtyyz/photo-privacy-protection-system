"use client"

import { Authenticator } from "@aws-amplify/ui-react";

export default function AuthenticatorWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Authenticator formFields={{
    signIn: {
      username: {
        label: "Email",
      },
    },
    signUp: {
      username: {
        label: "Username",
        order: 1,
      },
    
      email: {
        label: "Email",
        order: 2,
      },
    
      password: {
        order: 3,
      },
    
      confirm_password: {
        order: 4,
      },
    },
  }}
  signUpAttributes={['email']}
 >{children}</Authenticator>;
}
