import { SampleConsole } from "@/components/console/sample-console";
import { DemoBar } from "@/components/demo-bar";

export const metadata = {
  title: "Support console tour · Concierge demo",
};

// Public on purpose: it shows made-up data only and calls no API, so it needs no login.
export default function ConsoleSamplePage() {
  return (
    <>
      <DemoBar />
      <SampleConsole />
    </>
  );
}
