import { MilestoneZeroConsole } from "../components/milestone-zero-console";
import { TodayAndPreview } from "../components/today-and-preview";
import { WardrobeImport } from "../components/wardrobe-import";

const principles = [
  ["Owned-first", "Recommendations will be constrained to approved wardrobe items."],
  ["Evidence before aesthetics", "Unclear garments stay held instead of being silently invented."],
  ["Provenance as a feature", "Assets retain their source, transformations, provider, run, and manifest."],
];

export default function Home() {
  return (
    <main>
      <nav className="top-nav" aria-label="Primary">
        <a className="brand" href="#top" aria-label="Fit Check home">
          <span aria-hidden="true">✦</span> Fit Check
        </a>
        <span className="nav-stage">Private wardrobe copilot</span>
      </nav>

      <section className="hero" id="top">
        <p className="eyebrow">Private, provenance-aware wardrobe copilot</p>
        <h1>What to wear today, from clothes you actually own.</h1>
        <p className="hero-copy">
          Fit Check turns outfit photos into a reviewable closet, creates useful weather-aware
          looks, and generates a selected AI preview—with the evidence trail visible at every step.
        </p>
      </section>

      <TodayAndPreview />

      <WardrobeImport />

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
