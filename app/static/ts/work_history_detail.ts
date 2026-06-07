import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";

declare const FlowbiteInstances: {
  getInstance: (
    type: string,
    id: string
  ) => {
    hide: () => void;
  };
};

window.addEventListener("load", function () {
  const editorContainer = this.document.getElementById("wysiwyg-typography-example");
  if (!editorContainer) return;

  const editor = new Editor({
    element: editorContainer,
    extensions: [StarterKit],
    content: `
      <p>Flowbite is an <strong>open-source library of UI components</strong> based on the utility-first Tailwind CSS framework featuring dark mode support, a Figma design system, and more.</p>
      <p>It includes all of the commonly used components that a website requires, such as buttons, dropdowns, navigation bars, modals, datepickers, advanced charts and the list goes on.</p>
      <ul>
        <li>Over 600+ open-source UI components</li>
        <li>Supports dark mode and RTL</li>
        <li>Available in React, Vue, Svelte frameworks</li>
      </ul>
      <p>Here is an example of a button component:</p>
      <pre><code>&lt;button type="button" class="...">Default&lt;/button></code></pre>
      <p>Learn more about all components from the <a href="https://flowbite.com/docs/getting-started/introduction/">Flowbite Docs</a>.</p>
    `,
    editorProps: {
      attributes: {
        class: "format lg:format-lg dark:format-invert focus:outline-none format-blue max-w-none",
      },
    },
  });

  const setupEditorCommand = (id: string, command: () => void) => {
    const button = document.getElementById(id);
    if (button) {
      button.addEventListener("click", () => {
        editor.chain().focus();
        command();
      });
    }
  };

  setupEditorCommand("toggleListButton", () => editor.chain().toggleBulletList().run());
  setupEditorCommand("toggleOrderedListButton", () => editor.chain().toggleOrderedList().run());
  setupEditorCommand("toggleBlockquoteButton", () => editor.chain().toggleBlockquote().run());
  setupEditorCommand("toggleHRButton", () => editor.chain().setHorizontalRule().run());
  setupEditorCommand("toggleCodeBlockButton", () => editor.chain().toggleCodeBlock().run());

  const typographyDropdown = FlowbiteInstances.getInstance("Dropdown", "typographyDropdown");

  const paragraphButton = document.getElementById("toggleParagraphButton");
  if (paragraphButton) {
    paragraphButton.addEventListener("click", () => {
      editor.chain().focus().setParagraph().run();
      typographyDropdown.hide();
    });
  }

  document.querySelectorAll("[data-heading-level]").forEach((button) => {
    button.addEventListener("click", () => {
      const levelAttr = (button as HTMLElement).getAttribute("data-heading-level");
      const level = levelAttr ? (parseInt(levelAttr) as 1 | 2 | 3 | 4 | 5 | 6) : 1;
      editor.chain().focus().toggleHeading({ level }).run();
      typographyDropdown.hide();
    });
  });
});
