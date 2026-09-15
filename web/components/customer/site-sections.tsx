import { Pill } from "@/components/ui/pill";

const SERVICES = [
  { name: "Standard cleaning", price: "from $120", note: "Kitchens, baths, floors" },
  { name: "Deep cleaning", price: "from $240", note: "Cabinets, oven, baseboards" },
  { name: "Handyman", price: "$95 first hour", note: "Mounting, assembly, repairs" },
  { name: "Plumbing", price: "$135 call-out", note: "Licensed, parts at cost" },
  { name: "Electrical", price: "$150 call-out", note: "Licensed electrician" },
  { name: "AC tune-up", price: "$110 per unit", note: "Filter, coils, pressure" },
] as const;

const TRUST = [
  {
    title: "Answers you can check",
    body: "Every answer cites the help-center article it came from. If the answer isn't there, the assistant says so instead of guessing.",
  },
  {
    title: "Refunds go to a person",
    body: "The assistant applies the written refund policy, then waits. A support lead approves before any money moves, and it can only be paid once.",
  },
  {
    title: "Your bookings stay yours",
    body: "Bookings are looked up by the account you're signed into. Another customer's booking simply isn't visible.",
  },
] as const;

export function ServicesSection() {
  return (
    <section aria-labelledby="services-heading" className="mx-auto w-full max-w-7xl px-4 sm:px-6">
      <div className="flex items-end justify-between gap-6 border-b border-sand-300 pb-4">
        <h2 id="services-heading" className="font-display text-2xl text-ink-950">
          What we do
        </h2>
        <p className="hidden text-sm text-ink-500 sm:block">
          Prices the assistant quotes come from these same articles
        </p>
      </div>
      <ul className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
        {SERVICES.map((service) => (
          <li key={service.name} className="border-t border-sand-200 pt-4">
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="font-medium text-ink-900">{service.name}</h3>
              <span className="font-mono text-sm text-tide-700">{service.price}</span>
            </div>
            <p className="mt-1 text-sm text-ink-500">{service.note}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TrustSection() {
  return (
    <section
      aria-labelledby="trust-heading"
      className="mx-auto w-full max-w-7xl px-4 pb-20 sm:px-6"
    >
      <div className="rounded-3xl bg-ink-950 px-6 py-10 text-sand-50 sm:px-10">
        <Pill tone="ink" className="ring-sand-50/25">
          How the assistant is kept honest
        </Pill>
        <h2 id="trust-heading" className="mt-4 max-w-2xl font-display text-2xl sm:text-3xl">
          The AI answers. It never moves money on its own.
        </h2>
        <ul className="mt-8 grid gap-8 md:grid-cols-3">
          {TRUST.map((item) => (
            <li key={item.title}>
              <h3 className="text-sm font-semibold text-tide-100">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-sand-200">{item.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-sand-300 bg-sand-50">
      <div className="mx-auto w-full max-w-7xl px-4 py-6 text-xs text-ink-500 sm:px-6">
        Tidewell Home Services is a fictional company built to demo Concierge, an AI support
        agent. No real bookings, payments, or customers.
      </div>
    </footer>
  );
}
