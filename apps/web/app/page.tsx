"use client";

import { useState } from "react";
import { WardrobeImport } from "../components/wardrobe-import";
import { TodayPlanner } from "../components/today-planner";
import { TodayAndPreview } from "../components/today-and-preview";

export default function AppHome() {
  const [activeTab, setActiveTab] = useState<"wardrobe" | "studio">("wardrobe");

  return (
    <>
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <main id="main-content">
        <nav className="top-nav">
          <div className="brand">
            Fit <span>Check</span>
          </div>
          <div className="nav-links">
            <button 
              onClick={() => setActiveTab("wardrobe")}
              className={activeTab === "wardrobe" ? "active" : ""}
            >
              Wardrobe
            </button>
            <button 
              onClick={() => setActiveTab("studio")}
              className={activeTab === "studio" ? "active" : ""}
            >
              Studio
            </button>
          </div>
          <div className="nav-stage">
            <span aria-hidden="true">●</span> Active Session
          </div>
        </nav>

        {activeTab === "wardrobe" && (
          <section className="wardrobe-workbench">
            <header className="section-heading">
              <div>
                <h2>Wardrobe Workbench</h2>
                <p className="workbench-copy">
                  Import garments, analyze with GMI Vision, and build your digital closet on B2.
                </p>
              </div>
            </header>
            <WardrobeImport />
          </section>
        )}

        {activeTab === "studio" && (
          <section className="tryon-studio">
            <header className="section-heading">
              <div>
                <h2>Studio</h2>
                <p className="workbench-copy">
                  Outfit copilot and virtual try-on generation.
                </p>
              </div>
            </header>
            <TodayAndPreview />
          </section>
        )}
      </main>
    </>
  );
}
