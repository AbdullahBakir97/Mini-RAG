import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import FilePicker from "@/components/FilePicker.vue";

const FILES = [
  { file_id: "a_guide.pdf", original_name: "guide.pdf" },
  { file_id: "b_notes.txt", original_name: "notes.txt" },
];

describe("FilePicker", () => {
  it("says which documents are used", () => {
    expect(mount(FilePicker, { props: { files: FILES, modelValue: [] } }).text()).toContain("All documents");
    expect(mount(FilePicker, { props: { files: FILES, modelValue: ["b_notes.txt"] } }).text()).toContain("notes.txt");
    expect(mount(FilePicker, { props: { files: FILES, modelValue: ["a_guide.pdf", "b_notes.txt"] } }).text()).toContain(
      "2 documents",
    );
  });

  it("chooses documents, and all of them again", async () => {
    const wrapper = mount(FilePicker, { props: { files: FILES, modelValue: ["a_guide.pdf"] } });

    await wrapper.find("button.trigger").trigger("click");
    const [all, guide, notes] = wrapper.findAll("button.option");
    await notes!.trigger("click");
    await guide!.trigger("click");
    await all!.trigger("click");

    expect(wrapper.emitted("update:modelValue")).toEqual([[["a_guide.pdf", "b_notes.txt"]], [[]], [[]]]);
  });

  it("cannot be opened without documents", () => {
    const wrapper = mount(FilePicker, { props: { files: [], modelValue: [] } });

    expect(wrapper.find("button.trigger").attributes("disabled")).toBeDefined();
  });
});
