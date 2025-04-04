<script lang="ts">
  import { onMount } from "svelte";
  import { beforeNavigate } from "$app/navigation";
  import { page } from "$app/state";
  import { Button, ButtonGroup, Checkbox, Hr, RadioButton, Search, Spinner } from "flowbite-svelte";
  import { CloseOutline } from "flowbite-svelte-icons";
  import MethodProperties from "$lib/MethodProperties.svelte";
  import TreeView from "$lib/TreeView.svelte";
  import type { GraphContext } from "$lib/types";

  let { data } = $props();

  let container: HTMLElement;

  /** All graphs identified by their name. */
  let graphs: Record<string, GraphContext> = $state({});
  /** The current graph. */
  let graph = $derived(graphs[page.params.name]);
  /** Views of the current graph. */
  let views = $derived(graph?.views ?? []);
  /** Index of the currently selected view. */
  let viewIndex = $derived(graph?.viewIndex);
  /** The currently selected view. */
  let view = $derived(views[viewIndex]);

  const closeView = (index: number) => {
    view?.detach();
    views[index].destroy();
    graphs[page.params.name].views.splice(index, 1);
    if (viewIndex > index) {
      graphs[page.params.name].viewIndex--;
    }
    if (viewIndex >= views.length) {
      graphs[page.params.name].viewIndex = Math.max(views.length - 1, 0);
    }
  };

  $effect(() => {
    // Create new graph entry if it doesn't exist
    if (!graphs[page.params.name]) {
      graphs[page.params.name] = {
        views: [],
        viewIndex: 0,
        searchQuery: "",
        compoundNodesShown: true,
      };
    }
  });

  $effect(() => {
    for (const view of views) {
      view.detach();
    }
    view?.attach(container);
  });

  onMount(() => {
    // Automatically set light/dark graph colors
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
      for (const view of views) {
        view.setColors(e.matches);
      }
    });
  });

  beforeNavigate(() => view?.detach());
</script>

<main class="flex">
  <aside
    class="flex flex-col gap-4 overflow-y-auto border-r-2 border-r-gray-200 p-4 lg:w-80 dark:border-r-gray-800"
  >
    <Button onclick={() => view?.resetLayout()}>Reset layout</Button>

    {#if graph}
      <h3>Method Tree</h3>
      <Search clearable bind:value={graphs[page.params.name].searchQuery} />
      {#await data.tree}
        <Spinner class="mx-auto" color="blue" />
      {:then result}
        <TreeView
          tree={result}
          graphName={page.params.name}
          bind:graphs
          searchQuery={graphs[page.params.name].searchQuery}
        />
      {/await}
    {/if}
  </aside>

  <div class="relative flex-grow">
    <section class="h-full w-full" bind:this={container}></section>
    <footer class="absolute bottom-0 flex flex-wrap gap-2 p-2">
      {#each views as view, i}
        <ButtonGroup size="sm">
          <RadioButton
            value={i}
            bind:group={graphs[page.params.name].viewIndex}
            color="primary"
            class="px-2 py-1"
          >
            {view.title}
          </RadioButton>
          <Button onclick={() => closeView(i)} color="primary" class="cursor-default px-1 py-0">
            <CloseOutline class="h-4 w-4" />
          </Button>
        </ButtonGroup>
      {/each}
    </footer>
  </div>

  <aside class="flex flex-col border-l-2 border-l-gray-200 p-4 lg:w-80 dark:border-l-gray-800">
    {#if graph}
      <div>
        <h3 class="mb-4">Graph Options</h3>
        <Checkbox
          bind:checked={graphs[page.params.name].compoundNodesShown}
          onchange={() => views.forEach((v) => v.toggleCompoundNodes())}
        >
          Compound nodes
        </Checkbox>
      </div>
    {/if}

    {#if view?.selectedNode}
      <Hr />

      <div class="flex flex-col gap-4">
        <h3>Method Properties</h3>
        <MethodProperties node={view.selectedNode} />
      </div>
    {/if}
  </aside>
</main>

<svelte:head>
  <title>Diff Tool</title>
</svelte:head>
