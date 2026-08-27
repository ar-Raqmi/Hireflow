import { marked } from 'marked';

marked.setOptions({ gfm: true, breaks: true });

function sanitize(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    .replace(/href="javascript:/gi, 'href="#"');
}

export function mdToHtml(src) {
  if (!src) return '';
  try {
    return sanitize(marked.parse(src));
  } catch {
    return '<p></p>';
  }
}
