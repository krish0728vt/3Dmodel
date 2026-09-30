import { describe, expect, it } from "vitest";

import { convertLength, formatLength, trimNumber } from "./previewTypes";

describe("convertLength", () => {
  it("leaves millimetres untouched", () => {
    expect(convertLength(25.4, "mm")).toBe(25.4);
  });

  it("converts millimetres to inches", () => {
    expect(convertLength(25.4, "in")).toBeCloseTo(1, 10);
  });
});

describe("trimNumber", () => {
  it("drops trailing fractional zeros", () => {
    expect(trimNumber(1.5)).toBe("1.5");
  });

  it("drops the decimal point for whole values", () => {
    expect(trimNumber(12)).toBe("12");
  });

  it("keeps significant trailing digits", () => {
    expect(trimNumber(100.25)).toBe("100.25");
  });

  it("preserves integer zeros while trimming the fraction", () => {
    expect(trimNumber(100)).toBe("100");
    expect(trimNumber(1000)).toBe("1000");
  });

  it("rounds to the requested precision", () => {
    expect(trimNumber(1.23456, 3)).toBe("1.235");
  });

  it("formats zero as a single digit", () => {
    expect(trimNumber(0)).toBe("0");
  });
});

describe("formatLength", () => {
  it("formats millimetres to two decimals with the unit suffix", () => {
    expect(formatLength(12.5, "mm")).toBe("12.5 mm");
  });

  it("formats inches to three decimals", () => {
    expect(formatLength(25.4, "in")).toBe("1 in");
    expect(formatLength(10, "in")).toBe("0.394 in");
  });

  it("labels whole millimetre values without a decimal point", () => {
    expect(formatLength(40, "mm")).toBe("40 mm");
  });
});
