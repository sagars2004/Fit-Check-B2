import { MilestoneZeroConsole } from "../components/milestone-zero-console";
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
        <span className="nav-stage">Private closet prototype</span>
      </nav>

      <section className="hero" id="top">
        <p className="eyebrow">Private, provenance-aware wardrobe copilot</p>
        <h1>What to wear today, from clothes you actually own.</h1>
        <p className="hero-copy">
          Fit Check turns outfit photos into a reviewable closet, creates useful weather-aware
          looks, and generates a selected AI preview—with the evidence trail visible at every step.
        </p>
      </section>

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
        <p className="eyebrow">Next milestone</p>
        <h2>Owned-only recommendations, then one selected preview.</h2>
        <p>
          Weather-aware options will use approved wardrobe items only. A virtual try-on will remain
          opt-in, visibly labeled as an AI preview, and linked back to its source evidence.
        </p>
      </section>
    </main>
  );
}
