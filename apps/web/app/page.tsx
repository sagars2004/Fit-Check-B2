"use client";

import { useState } from "react";
import { WardrobeImport } from "../components/wardrobe-import";
import { TodayPlanner } from "../components/today-planner";
import { TodayAndPreview } from "../components/today-and-preview";
import { MilestoneZeroConsole } from "../components/milestone-zero-console";

export default function AppHome() {
  const [activeTab, setActiveTab] = useState<"planner" | "wardrobe" | "preview" | "zero">("wardrobe");

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
              Workbench
            </button>
            <button 
              onClick={() => setActiveTab("planner")}
              className={activeTab === "planner" ? "active" : ""}
            >
              Today
            </button>
            <button 
              onClick={() => setActiveTab("preview")}
              className={activeTab === "preview" ? "active" : ""}
            >
              Try-On Studio
            </button>
            <button 
              onClick={() => setActiveTab("zero")}
              className={activeTab === "zero" ? "active" : ""}
            >
              Provenance Lab
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

        {activeTab === "planner" && (
          <section className="today-planner">
            <header className="section-heading">
              <div>
                <h2>Outfit Copilot</h2>
                <p className="workbench-copy">
                  Contextual recommendations from your active wardrobe.
                </p>
              </div>
            </header>
            <TodayPlanner />
          </section>
        )}

        {activeTab === "preview" && (
          <section className="tryon-studio">
            <header className="section-heading">
              <div>
                <h2>Try-On Studio</h2>
                <p className="workbench-copy">
                  Virtual try-on generation and provenance verification.
                </p>
              </div>
            </header>
            <TodayAndPreview />
          </section>
        )}

        {activeTab === "zero" && (
          <section className="provenance-lab">
            <header className="section-heading">
              <div>
                <h2>Provenance Lab</h2>
                <p className="workbench-copy">
                  Under the hood look at media authenticity and metadata.
                </p>
              </div>
            </header>
            <MilestoneZeroConsole />
          </section>
        )}
      </main>
    </>
  );
}
