import { MilestoneZeroConsole } from "../components/milestone-zero-console";
import { TodayAndPreview } from "../components/today-and-preview";
import { WardrobeImport } from "../components/wardrobe-import";

const principles = [
  ["Owned-first", "Recommendations will be constrained to approved wardrobe items."],
  ["Evidence before aesthetics", "Unclear garments stay held instead of being silently invented."],
  ["Provenance as a feature", "Assets retain their source, transformations, provider, run, and manifest."],
];

const demoSteps = [
  {
    href: "#closet",
    title: "Start with evidence",
    copy: "Load the safe mock wardrobe or import private outfit photos. Nothing becomes owned inventory without review.",
  },
  {
    href: "#today",
    title: "Plan from what is owned",
    copy: "Generate weather- and occasion-aware options using approved garments only.",
  },
  {
    href: "#try-on-studio",
    title: "Request one clear preview",
    copy: "Select one look, consent to a separate reference photo, and review the AI visualization with its evidence.",
  },
];

export default function Home() {
  return (
    <main id="main-content" tabIndex={-1}>
      <a className="skip-link" href="#closet">Skip to the wardrobe workflow</a>
      <nav className="top-nav" aria-label="Primary">
        <a className="brand" href="#top" aria-label="Fit Check home">
          <span aria-hidden="true">✦</span> Fit Check
        </a>
        <div className="nav-links">
          <a href="#closet">Closet</a>
          <a href="#today">Today</a>
          <a href="#try-on-studio">Preview</a>
        </div>
        <span className="nav-stage">Private wardrobe copilot</span>
      </nav>

      <section className="hero" id="top">
        <p className="eyebrow">Private, provenance-aware wardrobe copilot</p>
        <h1>What to wear today, from clothes you actually own.</h1>
        <p className="hero-copy">
          Fit Check turns outfit photos into a reviewable closet, creates useful weather-aware
          looks, and generates a selected AI preview—with the evidence trail visible at every step.
        </p>
        <div className="hero-actions">
          <a className="primary-link" href="#closet">Start the demo</a>
          <a className="text-link" href="#demo-journey">See the three-step flow</a>
        </div>
      </section>

      <section className="demo-journey" id="demo-journey" aria-labelledby="demo-journey-heading">
        <div>
          <p className="eyebrow">Three-minute judge flow</p>
          <h2 id="demo-journey-heading">From a trusted closet to one accountable preview.</h2>
        </div>
        <ol>
          {demoSteps.map((step, index) => (
            <li key={step.href}>
              <span aria-hidden="true" className="demo-step-number">{index + 1}</span>
              <div>
                <a href={step.href}>{step.title}</a>
                <p>{step.copy}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <WardrobeImport />

      <TodayAndPreview />

      <details className="foundation-details">
        <summary>Inspect the foundation provenance demo</summary>
        <MilestoneZeroConsole />
      </details>

      <section className="principles" aria-label="Product principles">
        {principles.map(([title, description]) => (
          <article key={title}>
            <h2>{title}</h2>
            <p>{description}</p>
          </article>
        ))}
      </section>

      <section className="next-up">
        <p className="eyebrow">Private by design</p>
        <h2>Choose one owned look, then review one clear AI preview.</h2>
        <p>
          Personal reference photos require explicit consent, remain separate from your wardrobe,
          and can be removed independently. Every preview stays visibly linked to its source evidence.
        </p>
      </section>
    </main>
  );
}
