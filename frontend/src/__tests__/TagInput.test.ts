import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TagInput from "@/components/TagInput.vue";
import { normalizeTag } from "@/lib/tags";

function mountInput(modelValue: string[] = []) {
  const wrapper = mount(TagInput, {
    props: {
      modelValue,
      suggestions: ["guides", "handbook"],
      "onUpdate:modelValue": (value: string[]) => wrapper.setProps({ modelValue: value }),
    },
  });
  return wrapper;
}

describe("normalizeTag", () => {
  it("lowercases and turns spaces and underscores into hyphens, like the server", () => {
    expect(normalizeTag("  Release Notes ")).toBe("release-notes");
    expect(normalizeTag("v2_beta")).toBe("v2-beta");
    expect(normalizeTag("Über")).toBe("über");
  });

  it("refuses what cannot be a tag", () => {
    expect(normalizeTag("")).toBeNull();
    expect(normalizeTag("a/b")).toBeNull();
    expect(normalizeTag("x".repeat(33))).toBeNull();
  });
});

describe("TagInput", () => {
  it("adds tags on Enter and comma, without duplicates", async () => {
    const wrapper = mountInput(["guides"]);
    const input = wrapper.find("input");
    await input.setValue("Release Notes, guides");
    await input.trigger("keydown", { key: "Enter" });

    expect(wrapper.props("modelValue")).toEqual(["guides", "release-notes"]);
    expect(wrapper.findAll(".chip").map((chip) => chip.text())).toEqual(["guides", "release-notes"]);
    expect((input.element as HTMLInputElement).value).toBe("");
  });

  it("removes a tag with its button, and the last one with Backspace", async () => {
    const wrapper = mountInput(["a", "b", "c"]);
    await wrapper.find('button[aria-label="Remove tag a"]').trigger("click");
    expect(wrapper.props("modelValue")).toEqual(["b", "c"]);

    await wrapper.find("input").trigger("keydown", { key: "Backspace" });
    expect(wrapper.props("modelValue")).toEqual(["b"]);
  });

  it("explains a tag it cannot take, and commit() reports it", async () => {
    const wrapper = mountInput();
    await wrapper.find("input").setValue("a/b");

    expect((wrapper.vm as unknown as { commit: () => boolean }).commit()).toBe(false);
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[role="alert"]').text()).toContain('"a/b" is not a tag');
    expect(wrapper.props("modelValue")).toEqual([]);
  });

  it("offers the project's tags it does not have yet", () => {
    const wrapper = mountInput(["guides"]);
    expect(wrapper.findAll("option").map((option) => option.attributes("value"))).toEqual(["handbook"]);
  });
});
