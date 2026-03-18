#!/usr/bin/env python3
"""
APA 7 Reference Fixer
A Mac app that uses Claude AI + web search to fix and format APA 7 references.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import sys

try:
    import anthropic
except ImportError:
    print("Missing dependency. Please run: pip install anthropic")
    sys.exit(1)

SYSTEM_PROMPT = """You are an APA 7th edition citation expert. Your task is to take a \
reference list (which may be messy, incomplete, or incorrectly formatted) and return a \
perfectly formatted APA 7 reference list.

Instructions:
1. Use the web_search tool to look up any missing or uncertain information: DOIs, \
publication years, page numbers, journal names, volume/issue numbers, publishers, URLs, etc.
2. Format every reference strictly according to APA 7 guidelines.
3. Sort all references alphabetically by first author's last name (or by title if no author).
4. Return ONLY the formatted reference list — no explanations, headers, or commentary.

APA 7 Key Rules:
- Authors: Last, F. M., & Last, F. M.
- Up to 20 authors listed in full; for 21+, list first 19, then "…" then the last author.
- Journal article: Author(s). (Year). Title of article. *Journal Name*, *volume*(issue), \
start–end. https://doi.org/xxxxx
- Book: Author(s). (Year). *Title of work: Subtitle*. Publisher.
- Book chapter: Author(s). (Year). Chapter title. In E. Editor (Ed.), *Book title* \
(pp. xx–xx). Publisher.
- Website: Author(s). (Year, Month Day). Title of page. Site Name. URL
- Always include DOI as https://doi.org/xxxxx when available.
- Mark italics with *asterisks* since this is plain text output.
- Each reference begins flush left; continuation lines indented (hanging indent style)."""


class APAFixerApp:
    BG = "#f5f5f7"
    CARD = "#ffffff"
    BLUE = "#0071e3"
    BLUE_ACTIVE = "#0077ed"
    TEXT = "#1d1d1f"
    MUTED = "#6e6e73"
    BORDER = "#d2d2d7"
    SUBTLE = "#e8e8ed"

    PLACEHOLDER = (
        "Paste your reference list here — any format works...\n\n"
        "Examples:\n"
        "Smith J (2020). AI in society. J Technology 15(3):45-67.\n"
        "Johnson A & Lee B. Machine Learning Basics. MIT Press, 2019.\n"
        "https://example.com/article — Brown (2021). Neural Networks."
    )

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("APA 7 Reference Fixer")
        self.root.geometry("1150x760")
        self.root.minsize(850, 600)
        self.root.configure(bg=self.BG)

        self.client: anthropic.Anthropic | None = None
        self.api_key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready — paste references and click Fix")
        self.is_processing = False
        self._placeholder_active = False

        self._build_ui()
        self._load_env_key()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_api_row()
        self._build_content()
        self._build_status()

    def _build_header(self):
        f = tk.Frame(self.root, bg=self.BG, pady=18)
        f.pack(fill=tk.X, padx=30)
        tk.Label(f, text="APA 7 Reference Fixer",
                 font=("Helvetica Neue", 26, "bold"),
                 bg=self.BG, fg=self.TEXT).pack(anchor=tk.W)
        tk.Label(f, text="Paste messy, incomplete, or wrong references → get perfect APA 7 output "
                         "with AI-powered web search",
                 font=("Helvetica Neue", 13),
                 bg=self.BG, fg=self.MUTED).pack(anchor=tk.W, pady=(2, 0))

    def _build_api_row(self):
        f = tk.Frame(self.root, bg=self.BG, padx=30, pady=6)
        f.pack(fill=tk.X)
        tk.Label(f, text="Anthropic API Key:",
                 font=("Helvetica Neue", 12), bg=self.BG, fg=self.TEXT).pack(side=tk.LEFT)
        self.api_entry = tk.Entry(
            f, textvariable=self.api_key_var, show="•", width=46,
            font=("Helvetica Neue", 12), relief=tk.FLAT, bd=0,
            highlightthickness=1, highlightbackground=self.BORDER,
            highlightcolor=self.BLUE, bg=self.CARD,
        )
        self.api_entry.pack(side=tk.LEFT, padx=(10, 8), ipady=6, ipadx=8)
        self._btn(f, "Save Key", self._save_api_key, primary=True).pack(side=tk.LEFT)
        tk.Label(f, text="  ·  get yours at console.anthropic.com",
                 font=("Helvetica Neue", 11), bg=self.BG, fg=self.MUTED).pack(side=tk.LEFT)

    def _build_content(self):
        outer = tk.Frame(self.root, bg=self.BG, padx=30)
        outer.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # ── Input pane ──
        left = tk.Frame(outer, bg=self.BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ih = tk.Frame(left, bg=self.BG)
        ih.pack(fill=tk.X, pady=(0, 5))
        tk.Label(ih, text="Your References",
                 font=("Helvetica Neue", 13, "bold"), bg=self.BG, fg=self.TEXT).pack(side=tk.LEFT)
        tk.Label(ih, text="  (any format — messy or incomplete is fine)",
                 font=("Helvetica Neue", 11), bg=self.BG, fg=self.MUTED).pack(side=tk.LEFT)

        in_card = tk.Frame(left, bg=self.CARD, highlightthickness=1,
                           highlightbackground=self.BORDER)
        in_card.pack(fill=tk.BOTH, expand=True)

        in_scroll = ttk.Scrollbar(in_card)
        in_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.input_text = tk.Text(
            in_card, font=("Helvetica Neue", 12), wrap=tk.WORD,
            relief=tk.FLAT, padx=12, pady=12, bg=self.CARD, fg=self.TEXT,
            insertbackground=self.TEXT, selectbackground="#b3d4f5",
            yscrollcommand=in_scroll.set,
        )
        in_scroll.configure(command=self.input_text.yview)
        self.input_text.pack(fill=tk.BOTH, expand=True)
        self._install_placeholder()

        # ── Middle controls ──
        mid = tk.Frame(outer, bg=self.BG, padx=14)
        mid.pack(side=tk.LEFT, anchor=tk.CENTER)

        self.fix_btn = self._btn(mid, "Fix  →", self._start_fix, primary=True, width=9,
                                 font=("Helvetica Neue", 14, "bold"), pady=11)
        self.fix_btn.pack(pady=(0, 10))
        self._btn(mid, "Clear", self._clear_all, width=9).pack()

        # ── Output pane ──
        right = tk.Frame(outer, bg=self.BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        oh = tk.Frame(right, bg=self.BG)
        oh.pack(fill=tk.X, pady=(0, 5))
        tk.Label(oh, text="Fixed APA 7 References",
                 font=("Helvetica Neue", 13, "bold"), bg=self.BG, fg=self.TEXT).pack(side=tk.LEFT)
        self._btn(oh, "Copy All", self._copy_output).pack(side=tk.RIGHT, padx=(5, 0))
        self._btn(oh, "Save .txt", self._save_output).pack(side=tk.RIGHT, padx=(5, 0))

        out_card = tk.Frame(right, bg=self.CARD, highlightthickness=1,
                            highlightbackground=self.BORDER)
        out_card.pack(fill=tk.BOTH, expand=True)

        out_scroll = ttk.Scrollbar(out_card)
        out_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text = tk.Text(
            out_card, font=("Helvetica Neue", 12), wrap=tk.WORD,
            relief=tk.FLAT, padx=12, pady=12, bg=self.CARD, fg=self.TEXT,
            selectbackground="#b3d4f5", state=tk.DISABLED,
            yscrollcommand=out_scroll.set,
        )
        out_scroll.configure(command=self.output_text.yview)
        self.output_text.pack(fill=tk.BOTH, expand=True)

    def _build_status(self):
        f = tk.Frame(self.root, bg=self.BG, pady=8)
        f.pack(fill=tk.X, padx=30)
        tk.Label(f, textvariable=self.status_var,
                 font=("Helvetica Neue", 11), bg=self.BG, fg=self.MUTED).pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(f, mode="indeterminate", length=220)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, *, primary=False, width=None,
             font=None, pady=6, **kw):
        cfg = dict(
            text=text, command=cmd,
            font=font or ("Helvetica Neue", 11),
            bg=self.BLUE if primary else self.SUBTLE,
            fg="white" if primary else self.TEXT,
            activebackground=self.BLUE_ACTIVE if primary else "#d8d8dd",
            activeforeground="white" if primary else self.TEXT,
            relief=tk.FLAT, padx=12, pady=pady,
            cursor="hand2", bd=0,
        )
        if width:
            cfg["width"] = width
        cfg.update(kw)
        return tk.Button(parent, **cfg)

    def _install_placeholder(self):
        self.input_text.insert("1.0", self.PLACEHOLDER)
        self.input_text.configure(fg="#aaaaaa")
        self._placeholder_active = True
        self.input_text.bind("<FocusIn>", self._clear_placeholder)
        self.input_text.bind("<FocusOut>", self._restore_placeholder)

    def _clear_placeholder(self, _event=None):
        if self._placeholder_active:
            self.input_text.delete("1.0", tk.END)
            self.input_text.configure(fg=self.TEXT)
            self._placeholder_active = False

    def _restore_placeholder(self, _event=None):
        if not self.input_text.get("1.0", tk.END).strip():
            self._install_placeholder()

    def _load_env_key(self):
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            self.api_key_var.set(key)
            self.client = anthropic.Anthropic(api_key=key)
            self.status_var.set("API key loaded from environment ✓  —  paste references and click Fix")

    def _save_api_key(self):
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("No Key", "Please enter your Anthropic API key.")
            return
        os.environ["ANTHROPIC_API_KEY"] = key
        self.client = anthropic.Anthropic(api_key=key)
        self.status_var.set("API key saved ✓")

    def _get_client(self):
        if self.client:
            return self.client
        key = self.api_key_var.get().strip() or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            messagebox.showerror(
                "API Key Required",
                "Please enter your Anthropic API key above.\n\nGet one free at: console.anthropic.com",
            )
            return None
        self.client = anthropic.Anthropic(api_key=key)
        return self.client

    # ── Core fix logic ────────────────────────────────────────────────────────

    def _start_fix(self):
        if self.is_processing:
            return
        if self._placeholder_active:
            messagebox.showwarning("Empty Input", "Please paste your references first.")
            return
        refs = self.input_text.get("1.0", tk.END).strip()
        if not refs:
            messagebox.showwarning("Empty Input", "Please paste your references first.")
            return
        client = self._get_client()
        if not client:
            return

        self.is_processing = True
        self.fix_btn.configure(state=tk.DISABLED, text="Fixing…")
        self.progress.pack(side=tk.RIGHT)
        self.progress.start(10)
        self.status_var.set("Claude is analysing your references…")

        # Clear output pane
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state=tk.DISABLED)

        threading.Thread(target=self._run_fix, args=(client, refs), daemon=True).start()

    def _run_fix(self, client: anthropic.Anthropic, references: str):
        try:
            search_count = 0
            user_msg = (
                "Please fix and format the following references in perfect APA 7 style. "
                "Use web search to find any missing or uncertain information "
                "(DOIs, publication years, page numbers, journal volumes/issues, "
                "publisher names, URLs, etc.).\n\n"
                f"References to fix:\n\n{references}"
            )

            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=[{
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": 15,
                }],
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", None)

                    # Detect web searches starting
                    if etype == "content_block_start":
                        cb = getattr(event, "content_block", None)
                        if cb and getattr(cb, "type", None) == "server_tool_use":
                            search_count += 1
                            self.root.after(
                                0, self.status_var.set,
                                f"Searching the web… ({search_count} search"
                                f"{'es' if search_count != 1 else ''} done)",
                            )

                    # Stream text deltas to output pane in real time
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta and getattr(delta, "type", None) == "text_delta":
                            self.root.after(0, self._append_output, delta.text)

            self.root.after(0, self._on_done)

        except anthropic.AuthenticationError:
            self.root.after(0, self._on_error,
                            "Invalid API key. Please check your Anthropic API key and try again.")
        except anthropic.RateLimitError:
            self.root.after(0, self._on_error,
                            "Rate limit reached. Please wait a moment and try again.")
        except anthropic.BadRequestError as e:
            self.root.after(0, self._on_error, f"Bad request: {e.message}")
        except Exception as e:
            self.root.after(0, self._on_error, f"Unexpected error: {e}")

    def _append_output(self, text: str):
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _on_done(self):
        self._reset_controls()
        self.status_var.set("Done! ✓  References formatted — copy or save the result on the right.")

    def _on_error(self, msg: str):
        self._reset_controls()
        self.status_var.set("Error occurred.")
        messagebox.showerror("Error", msg)

    def _reset_controls(self):
        self.is_processing = False
        self.fix_btn.configure(state=tk.NORMAL, text="Fix  →")
        self.progress.stop()
        self.progress.pack_forget()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _copy_output(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Nothing to Copy", "Fix some references first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Copied to clipboard ✓")

    def _save_output(self):
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Nothing to Save", "Fix some references first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save APA 7 References",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.status_var.set(f"Saved ✓")

    def _clear_all(self):
        self._clear_placeholder()
        self.input_text.delete("1.0", tk.END)
        self._restore_placeholder()
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state=tk.DISABLED)
        self.status_var.set("Cleared — paste new references and click Fix")


def main():
    root = tk.Tk()
    root.resizable(True, True)

    # Opt into macOS native rendering where possible
    try:
        root.tk.call("::tk::mac::useCompatibilityMetrics", "0")
    except tk.TclError:
        pass

    APAFixerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
