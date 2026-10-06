import { ImageResponse } from "next/og";

import { PROOF } from "@/lib/proof";

// The preview card for shared links (LinkedIn, Slack, messages). Colors are the site's tokens
// written out as hex, because the image renderer cannot read CSS variables.
const INK = "#0b2124";
const SAND = "#fcfaf6";
const SAND_MUTED = "#d9ccb6";
const TIDE = "#d3ebe3";
const TIDE_ACCENT = "#2a8a7b";

export const alt =
  "Concierge: a support agent that can't move money on its own. A refund waits for a person to approve it.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const STATS = [
  { value: `${PROOF.passed} of ${PROOF.conversations}`, label: "test conversations passed" },
  { value: `${PROOF.safetyPassed} of ${PROOF.safetyCases}`, label: "safety cases passed" },
  { value: String(PROOF.refundsWithoutHuman), label: "refunds paid without a person" },
  { value: `$${PROOF.usdPerConversation}`, label: "per conversation" },
];

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: INK,
          color: SAND,
          padding: "64px 72px",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              fontSize: 30,
              color: TIDE,
              letterSpacing: 1,
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: 7,
                background: TIDE_ACCENT,
                marginRight: 14,
              }}
            />
            Concierge · AI support agent
          </div>
          <div
            style={{
              fontSize: 76,
              lineHeight: 1.08,
              marginTop: 28,
              fontWeight: 700,
              maxWidth: 980,
            }}
          >
            A support agent that can&apos;t move money on its own.
          </div>
          <div style={{ fontSize: 30, marginTop: 24, color: SAND_MUTED, maxWidth: 900 }}>
            Every refund waits for a person to approve it.
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", width: "100%", justifyContent: "space-between" }}>
            {STATS.map((stat) => (
              <div key={stat.label} style={{ display: "flex", flexDirection: "column" }}>
                <div style={{ fontSize: 46, color: TIDE }}>{stat.value}</div>
                <div style={{ fontSize: 22, color: SAND_MUTED, marginTop: 4 }}>{stat.label}</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 20, color: SAND_MUTED, marginTop: 22 }}>
            {`Measured ${PROOF.measuredOn} with ${PROOF.model} · try it live at concierge-sand.vercel.app`}
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
