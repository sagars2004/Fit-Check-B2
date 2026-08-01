"use client";

import { useState } from "react";
import { WardrobeImport } from "../components/wardrobe-import";
import { TodayAndPreview } from "../components/today-and-preview";
import { Gallery } from "../components/gallery";

export default function AppHome() {
  const [activeTab, setActiveTab] = useState<"wardrobe" | "studio" | "gallery">("wardrobe");

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
            <button 
              onClick={() => setActiveTab("gallery")}
              className={activeTab === "gallery" ? "active" : ""}
            >
              Gallery
            </button>
          </div>
          <div className="nav-stage">
            <span aria-hidden="true">●</span> Active Session
          </div>
        </nav>

        {activeTab === "wardrobe" && (
          <section className="wardrobe-workbench">
            <header className="section-heading polished-heading">
              <div className="heading-content">
                <h2>Wardrobe Workbench</h2>
                <p className="workbench-copy">
                  Build your digital closet on B2. Import garments, remove backgrounds, and analyze styles with GMI Vision.
                </p>
              </div>
              <div className="step-tiles">
                <div className="step-tile">
                  <div className="step-number">1</div>
                  <div className="step-text">Upload Photos</div>
                </div>
                <div className="step-arrow">→</div>
                <div className="step-tile">
                  <div className="step-number">2</div>
                  <div className="step-text">Auto-Extract & Tag</div>
                </div>
                <div className="step-arrow">→</div>
                <div className="step-tile">
                  <div className="step-number">3</div>
                  <div className="step-text">Save to B2</div>
                </div>
              </div>
            </header>
            <WardrobeImport />
          </section>
        )}

        {activeTab === "studio" && (
          <section className="tryon-studio">
            <header className="section-heading polished-heading">
              <div className="heading-content">
                <h2>Try-On Studio</h2>
                <p className="workbench-copy">
                  Your personal AI stylist. Get outfit recommendations based on weather and occasion, and generate virtual try-ons.
                </p>
              </div>
              <div className="step-tiles">
                <div className="step-tile">
                  <div className="step-number">1</div>
                  <div className="step-text">Select Occasion</div>
                </div>
                <div className="step-arrow">→</div>
                <div className="step-tile">
                  <div className="step-number">2</div>
                  <div className="step-text">Get AI Plans</div>
                </div>
                <div className="step-arrow">→</div>
                <div className="step-tile">
                  <div className="step-number">3</div>
                  <div className="step-text">Generate Try-On</div>
                </div>
              </div>
            </header>
            <TodayAndPreview />
          </section>
        )}

        {activeTab === "gallery" && (
          <section className="gallery-section">
            <header className="section-heading polished-heading">
              <div className="heading-content">
                <h2>&ldquo;I&apos;m Feeling Lucky&rdquo; Gallery</h2>
                <p className="workbench-copy">
                  A catalog of your past AI-generated previews. Hover over any look to see the exact wardrobe pieces that made it happen.
                </p>
              </div>
            </header>
            <Gallery />
          </section>
        )}
      </main>
    </>
  );
}
