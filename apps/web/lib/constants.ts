export const FALLBACK_GARMENT_SVG =
  "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='500' viewBox='0 0 400 500' fill='none'><rect width='400' height='500' fill='%23F4F1EC'/><path d='M200 170L160 210H185V310H215V210H240L200 170Z' fill='%23111111'/><text x='50%25' y='68%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='14' font-weight='500' fill='%23666666'>Fit Check Item</text></svg>";

export function handleImgError(e: React.SyntheticEvent<HTMLImageElement, Event>) {
  e.currentTarget.onerror = null;
  e.currentTarget.src = FALLBACK_GARMENT_SVG;
}
