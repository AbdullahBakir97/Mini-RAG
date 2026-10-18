import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import FeedbackList from "@/components/FeedbackList.vue";

const LIST = {
  up: 3,
  down: 1,
  total: 1,
  offset: 0,
  limit: 10,
  items: [
    {
      conversation_id: "c-1",
      message_id: 9,
      question: "Can I deploy on Friday afternoon?",
      answer: "Yes, any time [1].",
      citations: [],
      feedback: { rating: "down", comment: "It is never after noon.", created_at: "2026-10-18T10:00:00Z" },
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

function mountList() {
  return mount(FeedbackList, { props: { project: "demo" }, global: { stubs: { RouterLink: RouterLinkStub } } });
}

describe("FeedbackList", () => {
  it("shows the counts and each rated answer with its comment", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(LIST)));
    const wrapper = mountList();
    await flushPromises();

    expect(wrapper.find(".counts").text()).toBe("3 1");
    expect(wrapper.find(".question").text()).toBe("Can I deploy on Friday afternoon?");
    expect(wrapper.find(".answer").text()).toBe("Yes, any time.");
    expect(wrapper.find(".note").text()).toBe("“It is never after noon.”");
    expect(wrapper.findComponent(RouterLinkStub).props("to")).toEqual({
      name: "ask",
      params: { project: "demo", conversation: "c-1" },
    });
  });

  it("filters by rating", async () => {
    const fetch = vi.fn().mockImplementation(async () => Response.json({ ...LIST, total: 0, items: [] }));
    vi.stubGlobal("fetch", fetch);
    const wrapper = mountList();
    await flushPromises();

    await wrapper.findAll(".filters button")[2]!.trigger("click");
    await flushPromises();

    expect(fetch.mock.calls.at(-1)![0]).toBe("/api/v1/projects/demo/feedback?offset=0&limit=10&rating=down");
    expect(wrapper.text()).toContain("No answers with this rating yet.");
  });
});
