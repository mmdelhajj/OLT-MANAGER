import { FormEvent, useState } from "react";

import { submitFeedback, FeedbackCategory } from "@/api/feedback";

/**
 * Floating "Send feedback" button + modal. Mounted once in AppShell so it's
 * available on every authenticated page. Posts to /api/feedback.
 */
export default function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("idea");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback({
        category,
        message,
        page_url: window.location.pathname,
      });
      setSent(true);
      setMessage("");
      setTimeout(() => {
        setOpen(false);
        setSent(false);
      }, 1500);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail ?? "Failed to send feedback";
      setError(typeof detail === "string" ? detail : "Failed to send feedback");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 bg-brand-600 text-white px-4 py-2 rounded-full shadow-lg text-sm hover:bg-brand-700"
      >
        Send feedback
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50 p-4">
      <form
        onSubmit={onSubmit}
        className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Send feedback</h2>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-slate-400 hover:text-slate-700"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <label className="block">
          <span className="text-sm">Type</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
            className="mt-1 w-full border rounded px-3 py-2"
          >
            <option value="bug">Bug report</option>
            <option value="idea">Feature idea</option>
            <option value="praise">Praise</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label className="block">
          <span className="text-sm">Message</span>
          <textarea
            required
            minLength={3}
            maxLength={4000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={5}
            className="mt-1 w-full border rounded px-3 py-2"
            placeholder="What's on your mind?"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {sent && <p className="text-sm text-green-700">Thanks — we got it.</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="px-4 py-2 text-sm rounded border"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="bg-brand-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
          >
            {submitting ? "Sending…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
