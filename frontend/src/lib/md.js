import { marked } from 'marked';

// md — tiny markdown renderer for the research + draft (CV / cover letter)
// text that comes back from the backend. `marked` is dependency-free and fast;
// we sanitize the output so raw HTML / script tags from the model can't run.
marked.setOptions({ gfm: true, breaks: true });

function sanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/href="javascript:/gi, 'href="#"');
}

// mdToHtml — returns sanitized HTML for a markdown string (empty-safe).
export function mdToHtml(src) {
  if (!src) return '';
  try {
    return sanitize(marked.parse(src));
  } catch {
    return '<p></p>';
  }
}