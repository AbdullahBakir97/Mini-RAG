import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ConversationList from "@/components/ConversationList.vue";

const items = [
  { id: "c-1", title: "Do cats purr?", created_at: "2026-10-18T10:00:00Z", updated_at: "2026-10-18T10:05:00Z" },
  { id: "c-2", title: null, created_at: "2026-10-18T09:00:00Z", updated_at: "2026-10-18T09:00:00Z" },
];

function mountList(props: Partial<InstanceType<typeof ConversationList>["$props"]> = {}) {
  return mount(ConversationList, { props: { items, total: 2, loading: false, error: null, active: "c-1", ...props } });
}

describe("ConversationList", () => {
  it("lists conversations and marks the open one", async () => {
    const wrapper = mountList();

    expect(wrapper.findAll(".name").map((name) => name.text())).toEqual(["Do cats purr?", "New conversation"]);
    expect(wrapper.find("[aria-current=page]").text()).toContain("Do cats purr?");

    await wrapper.findAll("button.open")[1]!.trigger("click");
    expect(wrapper.emitted("select")).toEqual([["c-2"]]);
  });

  it("asks before deleting a conversation", async () => {
    const wrapper = mountList();

    await wrapper.find("button.delete").trigger("click");
    expect(wrapper.text()).toContain("Delete this conversation?");
    expect(wrapper.emitted("remove")).toBeUndefined();

    await wrapper.find("button.btn-danger").trigger("click");
    expect(wrapper.emitted("remove")).toEqual([["c-1"]]);
  });

  it("offers more when not all are loaded", async () => {
    const wrapper = mountList({ total: 60 });

    await wrapper.find("button.more").trigger("click");
    expect(wrapper.emitted("more")).toHaveLength(1);
  });
});
