import { PUBLIC_API_URL } from "$env/static/public";
import { PRIVATE_API_URL } from "$env/static/private";
import type { HandleFetch } from "@sveltejs/kit";

export const handleFetch: HandleFetch = async ({ request, fetch }) => {
  if (request.url.startsWith(PUBLIC_API_URL)) {
    request = new Request(request.url.replace(PUBLIC_API_URL, PRIVATE_API_URL), request);
  }

  return fetch(request);
};
