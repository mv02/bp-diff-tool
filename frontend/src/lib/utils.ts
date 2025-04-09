import type { ElementDefinition } from "cytoscape";

export const deduplicate = (elements: ElementDefinition[]) => {
  const seen = new Set<string>();

  return elements.filter((ele) => {
    const id = ele.data.id as string;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
};
