import type View from "./view.svelte";

export type GraphContext = {
  views: View[];
  viewIndex: number;
  searchQuery: string;
  compoundNodesShown: boolean;
};

export type Tree = {
  [key: string]: number | Tree;
};
