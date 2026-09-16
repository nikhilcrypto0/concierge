import { SupportConsole } from "@/components/console/support-console";
import { DemoBar } from "@/components/demo-bar";

export const metadata = {
  title: "Support console · Concierge demo",
};

export default function ConsolePage() {
  return (
    <>
      <DemoBar />
      <SupportConsole />
    </>
  );
}
