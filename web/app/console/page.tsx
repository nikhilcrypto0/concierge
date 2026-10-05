import { LoginForm } from "@/components/console/login-form";
import { SupportConsole } from "@/components/console/support-console";
import { DemoBar } from "@/components/demo-bar";
import { isOperator } from "@/lib/operator-session";

export const metadata = {
  title: "Support console · Concierge demo",
};

export default async function ConsolePage() {
  const signedIn = await isOperator();
  return (
    <>
      <DemoBar />
      {signedIn ? <SupportConsole /> : <LoginForm />}
    </>
  );
}
