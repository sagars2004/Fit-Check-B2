"use client";

import { useCallback, useState } from "react";

import { type OutfitPlan } from "../lib/api";
import { TodayPlanner } from "./today-planner";
import { TryOnStudio } from "./try-on-studio";

export function TodayAndPreview() {
  const [selectedOutfit, setSelectedOutfit] = useState<OutfitPlan | null>(null);

  const selectOutfitForPreview = useCallback((outfit: OutfitPlan) => {
    setSelectedOutfit(outfit);
    window.requestAnimationFrame(() => {
      const studio = document.getElementById("try-on-studio");
      studio?.scrollIntoView({ behavior: "smooth", block: "start" });
      studio?.focus({ preventScroll: true });
    });
  }, []);

  return (
    <>
      <TodayPlanner
        onPreviewOutfit={selectOutfitForPreview}
        selectedPreviewOutfitId={selectedOutfit?.id ?? null}
      />
      <TryOnStudio onClearSelection={() => setSelectedOutfit(null)} outfit={selectedOutfit} />
    </>
  );
}
