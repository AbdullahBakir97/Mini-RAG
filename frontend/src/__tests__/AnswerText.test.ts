import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AnswerText from "@/components/AnswerText.vue";

describe("AnswerText", () => {
  it("links the markers of cited sources", async () => {
    const wrapper = mount(AnswerText, { props: { text: "Cats purr [1] and nap [2].", cited: [1] } });

    const buttons = wrapper.findAll("button.cite");
    expect(buttons.map((button) => button.text())).toEqual(["1"]);
    expect(wrapper.find("span.cite.static").text()).toBe("2");

    await buttons[0]!.trigger("click");
    expect(wrapper.emitted("cite")).toEqual([[1]]);
  });

  it("does not link markers while streaming, and shows a caret", () => {
    const wrapper = mount(AnswerText, { props: { text: "Cats purr [1]", cited: [1], streaming: true } });

    expect(wrapper.find("button.cite").exists()).toBe(false);
    expect(wrapper.find(".caret").exists()).toBe(true);
  });

  it("renders text, never HTML", () => {
    const wrapper = mount(AnswerText, { props: { text: "<img src=x onerror=alert(1)> [1]" } });

    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("<img src=x onerror=alert(1)>");
  });

  it("formats lists and bold text", () => {
    const wrapper = mount(AnswerText, {
      props: { text: "Points:\n\n* **Use** of proceeds [1]\n* Reporting\n    1. Yearly", cited: [1] },
    });

    expect(wrapper.findAll("ul > li")).toHaveLength(2);
    expect(wrapper.find("ul li ol li").text()).toBe("Yearly");
    expect(wrapper.find("strong").text()).toBe("Use");
    expect(wrapper.find("li button.cite").text()).toBe("1");
  });

  it("puts the caret after the last text written, also inside a list", () => {
    const wrapper = mount(AnswerText, { props: { text: "* One\n* Tw", streaming: true } });

    expect(wrapper.findAll("li")[1]!.find(".caret").exists()).toBe(true);
  });

  it("renders markup inside formatting as text", () => {
    const wrapper = mount(AnswerText, { props: { text: "* **<script>alert(1)</script>**" } });

    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.find("strong").text()).toBe("<script>alert(1)</script>");
  });
});
