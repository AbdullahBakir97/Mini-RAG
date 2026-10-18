import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import WebsiteSources from "@/components/WebsiteSources.vue";

const SOURCE = {
  id: "s-1",
  kind: "website",
  url: "https://docs.example.com/guide/",
  max_pages: 50,
  sync_interval_hours: 24,
  pages_count: 3,
  syncing: false,
  last_synced_at: "2026-10-18T10:00:00Z",
  next_sync_at: "2999-01-01T00:00:00Z",
  last_error: null,
  tags: ["docs"],
  created_at: "2026-10-18T09:00:00Z",
};

afterEach(() => vi.unstubAllGlobals());

function respond(...bodies: unknown[]) {
  const fetch = vi.fn();
  for (const body of bodies) {
    fetch.mockResolvedValueOnce(body === null ? new Response(null, { status: 204 }) : Response.json(body));
  }
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("WebsiteSources", () => {
  it("lists websites with their pages, schedule and last sync", async () => {
    respond({ items: [{ ...SOURCE, last_error: "docs.example.com could not be resolved" }] });

    const wrapper = mount(WebsiteSources, { props: { project: "demo" } });
    await flushPromises();

    expect(wrapper.find(".url").text()).toBe(SOURCE.url);
    expect(wrapper.text()).toContain("3 of at most 50 pages · Every day · Synced");
    expect(wrapper.find(".error").text()).toContain("docs.example.com could not be resolved. Its pages are kept.");
    expect(wrapper.find(".tags").text()).toBe("docs");
  });

  it("adds a website with its limits, schedule and tags", async () => {
    const fetch = respond({ items: [] }, SOURCE, { items: [SOURCE] });
    const wrapper = mount(WebsiteSources, { props: { project: "demo" } });
    await flushPromises();

    await wrapper.find("input[type=url]").setValue("https://docs.example.com/guide/");
    await wrapper.find("input[type=number]").setValue(20);
    await wrapper.find("select").setValue(0);
    await wrapper.find('input[aria-label="Tags for its pages"]').setValue("Guides, v2");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    const [url, init] = fetch.mock.calls[1]!;
    expect(url).toBe("/api/v1/projects/demo/sources");
    expect(JSON.parse(init.body)).toEqual({
      url: "https://docs.example.com/guide/",
      max_pages: 20,
      sync_interval_hours: 0,
      tags: ["guides", "v2"],
    });
    expect(wrapper.emitted("synced")).toHaveLength(1);
    expect(wrapper.findAll(".item")).toHaveLength(1);
  });

  it("removes a website, keeping its pages when asked", async () => {
    const fetch = respond({ items: [SOURCE] }, null, { items: [] });
    const wrapper = mount(WebsiteSources, { props: { project: "demo" } });
    await flushPromises();

    await wrapper.find('button[aria-label="Remove https://docs.example.com/guide/"]').trigger("click");
    await wrapper.find(".keep input").setValue(true);
    await wrapper.find(".confirm .btn-danger").trigger("click");
    await flushPromises();

    const [url, init] = fetch.mock.calls[1]!;
    expect(url).toBe("/api/v1/projects/demo/sources/s-1?keep_files=true");
    expect(init.method).toBe("DELETE");
    expect(wrapper.text()).toContain("No websites yet.");
  });
});
