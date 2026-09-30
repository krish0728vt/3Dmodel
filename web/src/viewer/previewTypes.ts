import type { PreviewBoundingBox, PreviewObject, SelectionState } from "../types/api";

export type DisplayUnits = "mm" | "in";

export type ViewerSelection = SelectionState;

export type Measurement = {
  start: [number, number, number];
  end: [number, number, number];
  distanceMm: number;
};

export type ViewerPropsPreview = {
  objects: PreviewObject[];
  overall_bounding_box: PreviewBoundingBox | null;
};

export function convertLength(valueMm: number, units: DisplayUnits): number {
  return units === "in" ? valueMm / 25.4 : valueMm;
}

export function formatLength(valueMm: number, units: DisplayUnits): string {
  const value = convertLength(valueMm, units);
  const precision = units === "in" ? 3 : 2;
  return `${trimNumber(value, precision)} ${units}`;
}

export function trimNumber(value: number, precision = 2): string {
  return value.toFixed(precision).replace(/0+$/, "").replace(/\.$/, "");
}
