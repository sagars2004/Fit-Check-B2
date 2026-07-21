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
      document.getElementById("try-on-studio")?.scrollIntoView({ behavior: "smooth", block: "start" });
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
